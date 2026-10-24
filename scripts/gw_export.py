"""Read WhatsApp "Export chat" files (the .txt, or the .zip that WhatsApp makes) as a history source.

This is the source for people who do not run the whatsapp-mcp bridge. It returns the same shapes
as gw_store (Message, ReplyPair), so gw_learn can use either source through one interface.
Each file is one chat, and its chat id is "export:<file name without the extension>".

Supported: the iOS and Android formats of "Export chat > Without media", in 24-hour and
12-hour time, with or without seconds, a 2- or 4-digit year, and "/", "." or "-" in dates.
Only the English media and system texts are recognised; a media note in another language is
read as an ordinary message. Group chats (more than two senders in one file) are skipped.

Names and message text come from other people: treat them as untrusted data. Standard library
only, and no syntax newer than Python 3.9.
"""
import re
import sys
import zipfile
import zlib
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python3 -I leaves this directory off sys.path

import gw_store  # noqa: E402

CHAT_PREFIX = "export:"
MAX_FILE_BYTES = 64 * 1024 * 1024  # a plain-text chat of this size is years of messages
MAX_NAME_CHARS = 64  # a longer text before the first ": " is a system line, not a sender name
MAX_NAME_WORDS = 8
DATE_ORDERS = ("dmy", "mdy")

# Characters WhatsApp puts in exports. They are normalised before any matching.
_INVISIBLE = dict.fromkeys(map(ord, "‎‏‪‫‬‭‮﻿"))  # LRM, RLM, bidi controls, BOM
_SPACES = {0x202F: " ", 0x00A0: " "}  # narrow no-break space before AM/PM, no-break space

_DATE = r"(\d{1,4})[./-](\d{1,2})[./-](\d{1,4})"
_TIME = r"(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s?([AaPp])\.?\s?[Mm]\.?)?"
# iOS:     [24/10/2026, 21:05:12] Alice: text
# Android: 24/10/2026, 21:05 - Alice: text
_IOS = re.compile(rf"^\[{_DATE},?\s+{_TIME}\]\s?(.*)$")
_ANDROID = re.compile(rf"^{_DATE},?\s+{_TIME}\s+-\s+(.*)$")

_ATTACHED = re.compile(r"^<attached:\s*(.*?)>$", re.IGNORECASE)
_OMITTED = re.compile(
    r"^(image|video|audio|sticker|document|gif|contact card|voice call|video call) omitted$", re.IGNORECASE
)
_ANGLE_NOTE = re.compile(r"^<[^<>\n]{3,60}>$")  # "<Media omitted>" and its translations
_DELETED = re.compile(
    r"^(this message was deleted|you deleted this message|this message was deleted by admin\b.*)\.?$", re.IGNORECASE
)
_EDITED_SUFFIX = re.compile(r"<this message was edited>$", re.IGNORECASE)  # no leading \s*: it would be slow on long runs of spaces
# Notices that iOS writes with the contact's name in front, so they look like a message from that contact.
_SYSTEM_BODY = re.compile(
    r"^(messages and calls are end-to-end encrypted|your security code with .{1,80} changed"
    r"|.{1,80} changed their phone number)",
    re.IGNORECASE,
)
_MEDIA_BY_HINT = (
    ("PHOTO", "image"), ("VIDEO", "video"), ("AUDIO", "audio"), ("PTT", "audio"),
    ("STICKER", "sticker"), ("GIF", "video"),
)
_MEDIA_BY_EXTENSION = {
    "jpg": "image", "jpeg": "image", "png": "image", "heic": "image", "webp": "sticker",
    "mp4": "video", "mov": "video", "3gp": "video",
    "opus": "audio", "m4a": "audio", "mp3": "audio", "aac": "audio", "ogg": "audio", "amr": "audio", "wav": "audio",
}
_SPACE = re.compile(r"\s+")


class ExportError(Exception):
    """An export file or folder cannot be used. The message never contains message text."""


@dataclass(frozen=True)
class Entry:
    """One message of an export, before the owner is known."""
    chat_id: str
    index: int  # position in the file
    sender: str
    content: str
    media_type: str
    timestamp: str  # "YYYY-MM-DD HH:MM:SS"


@dataclass
class Chat:
    chat_id: str
    source_name: str  # file name, for warnings
    entries: List[Entry] = field(default_factory=list)


@dataclass(frozen=True)
class NameStat:
    name: str
    messages: int
    files: int


def normalise_line(line: str) -> str:
    """Remove the invisible marks of an export and turn special spaces into plain ones."""
    return line.translate(_INVISIBLE).translate(_SPACES)


def same_name(a: str, b: str) -> bool:
    return _SPACE.sub(" ", a).strip().casefold() == _SPACE.sub(" ", b).strip().casefold()


# ---------------------------------------------------------------------------
# One file
# ---------------------------------------------------------------------------

@dataclass
class _Raw:
    """A header line and the lines that continue it, with date fields not yet read."""
    a: int  # first date field
    b: int  # second date field
    c: int  # third date field
    hour: int
    minute: int
    second: int
    ampm: str
    rest: str
    line: str  # the whole line, for when the date turns out not to be a date
    extra: List[str] = field(default_factory=list)


def _header(line: str) -> Optional[_Raw]:
    match = _IOS.match(line) or _ANDROID.match(line)
    if not match:
        return None
    a, b, c, hour, minute, second, ampm, rest = match.groups()
    return _Raw(int(a), int(b), int(c), int(hour), int(minute), int(second or 0), (ampm or "").lower(), rest, line)


def detect_date_order(raws: Sequence[_Raw], default: str = "dmy") -> str:
    """"dmy" or "mdy" for one file: a first field above 12 means day first, a second field above
    12 means month first. A year-first date ("2026-10-24") is read by its own rule, not this one."""
    day_first = any(r.a > 12 and r.a < 1000 for r in raws)
    month_first = any(r.b > 12 for r in raws if r.a < 1000)
    if day_first and not month_first:
        return "dmy"
    if month_first and not day_first:
        return "mdy"
    return default


def _timestamp(raw: _Raw, order: str) -> Optional[str]:
    if raw.a >= 1000:  # year first: 2026-10-24
        year, month, day = raw.a, raw.b, raw.c
    else:
        year = raw.c
        month, day = (raw.b, raw.a) if order == "dmy" else (raw.a, raw.b)
        if year < 100:
            year += 2000
    hour = raw.hour
    if raw.ampm:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if raw.ampm == "p" else 0)
    if not (hour < 24 and raw.minute < 60 and raw.second < 60):
        return None
    try:
        date(year, month, day)
    except ValueError:
        return None
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{raw.minute:02d}:{raw.second:02d}"


def _split_sender(rest: str) -> Tuple[Optional[str], str]:
    """(sender, text) of the part after the timestamp. A line without "Name: " is a system line."""
    name, sep, text = rest.partition(": ")
    name = name.strip()
    if not sep:
        if rest.endswith(":"):  # "Alice:" with an empty message
            name, text = rest[:-1].strip(), ""
        else:
            return None, rest
    if not name or len(name) > MAX_NAME_CHARS or len(name.split()) > MAX_NAME_WORDS:
        return None, rest
    return name, text


def _media_type_of(content: str) -> Tuple[str, str]:
    """(media_type, content) for a message: ("", text) for text, (type, "") for a placeholder."""
    text = content.strip()
    attached = _ATTACHED.match(text)
    if attached:
        filename = attached.group(1)
        upper = filename.upper()
        for hint, kind in _MEDIA_BY_HINT:
            if f"-{hint}-" in upper:
                return kind, ""
        return _MEDIA_BY_EXTENSION.get(filename.rsplit(".", 1)[-1].lower(), "document"), ""
    omitted = _OMITTED.match(text)
    if omitted:
        kind = omitted.group(1).lower()
        return {"gif": "video", "contact card": "document", "voice call": "audio", "video call": "video"}.get(kind, kind), ""
    if _DELETED.match(text):
        return "deleted", ""
    if _ANGLE_NOTE.match(text):
        return "media", ""
    if _SYSTEM_BODY.match(text):
        return "", ""
    return "", _EDITED_SUFFIX.sub("", text).strip()


def parse_text(text: str, chat_id: str, default_order: str = "dmy") -> List[Entry]:
    """The messages of one export, oldest first. System lines are left out."""
    raws: List[_Raw] = []
    for line in text.splitlines():
        line = normalise_line(line)
        raw = _header(line)
        if raw is not None:
            raws.append(raw)
        elif raws:
            raws[-1].extra.append(line)
    order = detect_date_order(raws, default_order)
    entries: List[Entry] = []
    previous: Optional[_Raw] = None  # the last header with a valid date
    stamps: Dict[int, str] = {}
    kept: List[_Raw] = []
    for raw in raws:
        stamp = _timestamp(raw, order)
        if stamp is None:  # not a date, so the line is part of the message before it
            if previous is not None:
                previous.extra.extend([raw.line, *raw.extra])
            continue
        stamps[id(raw)] = stamp
        kept.append(raw)
        previous = raw
    for raw in kept:
        sender, first = _split_sender(raw.rest)
        if sender is None:
            continue
        body = "\n".join([first, *raw.extra]).strip()
        media, content = _media_type_of(body)
        if not media and not content:
            continue
        entries.append(Entry(
            chat_id=chat_id, index=len(entries), sender=gw_store.clean_text(sender).strip(),
            content=gw_store.clean_text(content), media_type=media, timestamp=stamps[id(raw)],
        ))
    return entries


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Files, zips and folders
# ---------------------------------------------------------------------------

def _chat_member(zf: zipfile.ZipFile, label: str) -> zipfile.ZipInfo:
    members = [
        m for m in zf.infolist()
        if not m.is_dir() and m.filename.lower().endswith(".txt")
        and not m.filename.startswith("__MACOSX/") and not Path(m.filename).name.startswith("._")
    ]
    if len(members) > 1:
        likely = [
            m for m in members
            if Path(m.filename).name.lower() == "_chat.txt" or Path(m.filename).name.lower().startswith("whatsapp chat")
        ]
        members = likely
    if len(members) != 1:
        raise ExportError(f"{label}: expected one chat .txt file inside the zip, found {len(members) or 'none'} that fit")
    return members[0]


def _read_source(path: Path) -> bytes:
    """The bytes of a .txt, or of the chat file inside a .zip."""
    try:
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as zf:
                member = _chat_member(zf, path.name)
                if member.file_size > MAX_FILE_BYTES:
                    raise ExportError(f"{path.name}: the chat file inside is larger than {MAX_FILE_BYTES // 2**20} MB")
                with zf.open(member) as f:
                    data = f.read(MAX_FILE_BYTES + 1)
        else:
            with open(path, "rb") as f:
                data = f.read(MAX_FILE_BYTES + 1)
    except zipfile.BadZipFile as e:
        raise ExportError(f"{path.name}: not a valid zip file") from e
    except (RuntimeError, NotImplementedError, EOFError, zlib.error) as e:  # password, unknown method, damaged data
        raise ExportError(f"{path.name}: cannot read the zip file (is it password protected or damaged?)") from e
    except OSError as e:
        raise ExportError(f"cannot read {path}: {e.strerror or type(e).__name__}") from e
    if len(data) > MAX_FILE_BYTES:
        raise ExportError(f"{path.name}: larger than {MAX_FILE_BYTES // 2**20} MB")
    return data


def _files_in(path: Path) -> List[Path]:
    """The export files for one PATH argument: a file, or the .txt and .zip files in a folder."""
    try:
        return _list_files(path)
    except OSError as e:
        raise ExportError(f"cannot read {path}: {e.strerror or type(e).__name__}") from e


def _list_files(path: Path) -> List[Path]:
    if path.is_dir():
        found = sorted(
            p for p in path.rglob("*")
            if p.is_file() and p.suffix.lower() in (".txt", ".zip")
            and not any(part.startswith((".", "__MACOSX")) for part in p.relative_to(path).parts)
        )
        if not found:
            raise ExportError(f"no .txt or .zip files in {path}")
        return found
    if not path.is_file():
        raise ExportError(f"no such file or folder: {path}")
    if path.suffix.lower() not in (".txt", ".zip"):
        raise ExportError(f"{path.name} is not a .txt or .zip file")
    return [path]


def _chat_id(path: Path, taken: Iterable[str]) -> str:
    stem = path.stem
    if stem.lower() == "_chat":  # an unzipped iOS export: the folder has the chat's name
        stem = path.parent.name or stem
    chat_id = CHAT_PREFIX + stem
    taken = set(taken)
    candidate, n = chat_id, 1
    while candidate in taken:
        n += 1
        candidate = f"{chat_id}#{n}"
    return candidate


class ExportSource:
    """All the chats of some exports. Same questions as the database source in gw_store."""

    def __init__(self, chats: List[Chat], me: Optional[str] = None):
        self.chats = chats
        self.me = me

    # -- who is who

    def names(self) -> List[NameStat]:
        """Every sender name, with the number of messages and of files it appears in. Most active first."""
        messages: Counter = Counter()
        files: Counter = Counter()
        display: Dict[str, str] = {}
        for chat in self.chats:
            seen = set()
            for entry in chat.entries:
                key = _SPACE.sub(" ", entry.sender).strip().casefold()
                display.setdefault(key, _SPACE.sub(" ", entry.sender).strip())
                messages[key] += 1
                seen.add(key)
            files.update(seen)
        stats = [NameStat(display[k], messages[k], files[k]) for k in messages]
        stats.sort(key=lambda s: (-s.messages, s.name.casefold()))
        return stats

    def names_in_every_file(self) -> List[str]:
        stats = self.names()
        return [s.name for s in stats if s.files == len(self.chats)]

    def has_sender(self, name: str) -> bool:
        return any(same_name(e.sender, name) for chat in self.chats for e in chat.entries)

    # -- the questions gw_learn asks

    def _message(self, entry: Entry) -> gw_store.Message:
        return gw_store.Message(
            id=f"{entry.chat_id}:{entry.index}", chat_jid=entry.chat_id, sender=entry.sender,
            content=entry.content, timestamp=entry.timestamp,
            from_me=bool(self.me) and same_name(entry.sender, self.me or ""), media_type=entry.media_type,
        )

    def _chats(self, exclude_chats: Iterable[str]) -> List[Chat]:
        skipped = set(exclude_chats)
        return [c for c in self.chats if c.chat_id not in skipped]

    def owner_messages(self, limit: int = 5000, exclude_chats: Iterable[str] = ()) -> List[gw_store.Message]:
        """The owner's own text messages, newest first."""
        found = []
        for chat in self._chats(exclude_chats):
            for entry in chat.entries:
                if entry.content and self.me and same_name(entry.sender, self.me):
                    found.append(self._message(entry))
        found.sort(key=lambda m: m.timestamp, reverse=True)  # stable: a tie keeps file order
        return found[:limit]

    def owner_replies(self, limit: int = 5000, exclude_chats: Iterable[str] = ()) -> List[gw_store.ReplyPair]:
        """Customer message -> the owner's reply that directly followed it, newest first. Both are text."""
        found = []
        for chat in self._chats(exclude_chats):
            ordered = sorted(chat.entries, key=lambda e: e.timestamp)
            for prev, cur in zip(ordered, ordered[1:]):
                if not (self.me and same_name(cur.sender, self.me)) or same_name(prev.sender, self.me or ""):
                    continue
                if cur.content and prev.content:
                    found.append(gw_store.ReplyPair(
                        chat_jid=chat.chat_id, customer_text=prev.content, reply_text=cur.content, timestamp=cur.timestamp,
                    ))
        found.sort(key=lambda p: p.timestamp, reverse=True)
        return found[:limit]


def _warn(message: str) -> None:
    print(f"gw_learn: warning: {message}", file=sys.stderr)


def load_exports(paths: Sequence[str], me: Optional[str] = None, date_order: str = "dmy") -> ExportSource:
    """Read the exports at `paths` (files or folders). Group chats and empty files are skipped with a warning."""
    if date_order not in DATE_ORDERS:
        raise ExportError(f"date order must be one of: {', '.join(DATE_ORDERS)}")
    files: List[Path] = []
    for p in paths:
        for f in _files_in(Path(p).expanduser()):
            if f not in files:
                files.append(f)
    chats: List[Chat] = []
    seen: Dict[tuple, str] = {}  # message content of each loaded file -> its name
    for path in files:
        chat_id = _chat_id(path, (c.chat_id for c in chats))
        entries = parse_text(_decode(_read_source(path)), chat_id, date_order)
        senders = {_SPACE.sub(" ", e.sender).strip().casefold() for e in entries}
        if len(senders) > 2:
            _warn(f"skipped {path.name}: it has more than two senders, so it looks like a group chat")
            continue
        if not entries:
            _warn(f"no messages found in {path.name}; is it a WhatsApp chat export?")
            continue
        fingerprint = tuple((e.timestamp, e.sender, e.content, e.media_type) for e in entries)
        if fingerprint in seen:  # a .zip and the folder it was unzipped into, for example
            _warn(f"skipped {path.name}: it has the same messages as {seen[fingerprint]}")
            continue
        seen[fingerprint] = path.name
        chats.append(Chat(chat_id, path.name, entries))
    if not chats:
        raise ExportError("no one-to-one chats could be read from the export files")
    return ExportSource(chats, me)
