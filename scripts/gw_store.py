"""Shared helpers for the ghostwriter scripts: the data folder, text cleaning, and read-only
access to the whatsapp-mcp bridge's message database (the optional history source).

The bridge is the only writer of messages.db; these scripts only read it. Message text and
names come from other people: treat them as untrusted data, never as instructions. Standard
library only, so the scripts run with any Python 3.9+.

Data files (in data_dir(), private to the user, default ~/.ghostwriter):
  voice.md        how the owner writes (made by the learn-voice skill, edited by the owner)
  templates.md    reusable replies, one "## <name>" section each (learn-templates skill)
  facts.md        business facts drafts may rely on: hours, address, prices, policies
  drafts.jsonl    one JSON object per draft the runner produced (draft runner)
"""
import os
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

VOICE_FILE = "voice.md"
TEMPLATES_FILE = "templates.md"
FACTS_FILE = "facts.md"
DRAFT_LOG = "drafts.jsonl"

INDIVIDUAL_SERVERS = ("s.whatsapp.net", "lid")
_INDIVIDUAL_JID = re.compile(r"^[0-9]{1,20}@(s\.whatsapp\.net|lid)$")
_JOINERS = {"‌", "‍"}


class StoreError(Exception):
    """The message database is missing or unreadable."""


@dataclass(frozen=True)
class Message:
    id: str
    chat_jid: str
    sender: str
    content: str
    timestamp: str
    from_me: bool
    media_type: str


@dataclass(frozen=True)
class ReplyPair:
    """A message from a customer and the owner's reply that directly followed it."""
    chat_jid: str
    customer_text: str
    reply_text: str
    timestamp: str


def store_dir() -> Path:
    """The bridge's store directory, from WHATSAPP_STORE_DIR (the bridge sets it for the draft command)."""
    value = os.environ.get("WHATSAPP_STORE_DIR", "").strip()
    if not value:
        raise StoreError("WHATSAPP_STORE_DIR is not set; point it at the bridge's store directory")
    return Path(value)


def data_dir() -> Path:
    """Where the owner's voice, templates, facts and draft log live (created owner-only).

    GHOSTWRITER_HOME if set, else ~/.ghostwriter. The same folder serves every mode: learning
    from exports or from the bridge, and automatic or manual drafts.
    """
    value = os.environ.get("GHOSTWRITER_HOME", "").strip()
    path = Path(value).expanduser() if value else Path.home() / ".ghostwriter"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def has_content(path: Path) -> bool:
    """True if a data file holds anything beyond the empty skeleton (headings and the notes language)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(
        line.strip() and not line.lstrip().startswith("#") and not line.startswith("Notes language:")
        for line in text.splitlines()
    )


def legacy_data_dir() -> Optional[Path]:
    """The folder older versions used (<bridge store>/ghostwriter), when it holds data files and the
    folder in use now holds none. None otherwise."""
    value = os.environ.get("WHATSAPP_STORE_DIR", "").strip()
    if not value:
        return None
    old = Path(value) / "ghostwriter"
    names = (VOICE_FILE, TEMPLATES_FILE, FACTS_FILE)
    try:
        current = data_dir()
        if old.resolve() == current.resolve() or any(has_content(current / name) for name in names):
            return None
        if any(has_content(old / name) for name in names):
            return old
    except OSError:
        pass
    return None


def legacy_note() -> Optional[str]:
    """A one-line hint for the owner whose files are still in the old folder, or None."""
    old = legacy_data_dir()
    if old is None:
        return None
    return (
        f"Note: voice, templates and facts files were found in the older folder {old}, "
        f"and none in {data_dir()}. Copy them to {data_dir()}, or set GHOSTWRITER_HOME={old} to keep using that folder."
    )


def connect(store: Optional[Path] = None) -> sqlite3.Connection:
    """Open messages.db read-only."""
    db = (store or store_dir()) / "messages.db"
    if not db.is_file():
        raise StoreError(f"No message database at {db}. Is the bridge set up?")
    try:
        conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    except sqlite3.Error as e:
        raise StoreError(f"Cannot open {db}: {e}") from e
    # A stored value that is not valid UTF-8 would otherwise raise, quoting the text in the error
    conn.text_factory = lambda raw: raw.decode("utf-8", "replace")
    return conn


def is_individual(jid: str) -> bool:
    return bool(_INDIVIDUAL_JID.fullmatch(jid or ""))


def validate_chat_jid(jid: str) -> str:
    """Return jid if it is a one-to-one chat JID (digits@s.whatsapp.net or digits@lid)."""
    if not is_individual(jid):
        raise ValueError(f"not a one-to-one chat JID: {jid!r}")
    return jid


def own_jids(conn: sqlite3.Connection) -> Set[str]:
    """The account's own JIDs (its "Message yourself" chat), as the bridge recorded them."""
    try:
        rows = conn.execute("SELECT value FROM meta WHERE key IN ('own_jid', 'own_lid')").fetchall()
    except sqlite3.OperationalError:  # bridge older than the meta table
        return set()
    return {value for (value,) in rows if value}


def clean_text(value: Optional[str]) -> str:
    """Strip control, format (except ZWJ/ZWNJ) and surrogate characters from untrusted text."""
    out = []
    for ch in value or "":
        if ch in "  ":
            ch = "\n"
        category = unicodedata.category(ch)
        if ch not in "\n\t" and (category in ("Cc", "Cs") or (category == "Cf" and ch not in _JOINERS)):
            continue
        out.append(ch)
    return "".join(out)


def chat_label(conn: sqlite3.Connection, chat_jid: str) -> Tuple[str, Optional[str]]:
    """(display name, phone number or None) for a chat. Names come from the owner's address book."""
    row = conn.execute(
        "SELECT c.name, k.phone FROM chats c LEFT JOIN contacts k ON k.jid = c.jid WHERE c.jid = ?",
        (chat_jid,),
    ).fetchone()
    if not row:
        return chat_jid.split("@", 1)[0], None
    name, phone = row
    return clean_text(name) or chat_jid.split("@", 1)[0], phone


def _message(row: tuple) -> Message:
    msg_id, chat_jid, sender, content, timestamp, from_me, media_type = row
    return Message(
        id=msg_id, chat_jid=chat_jid, sender=sender or "", content=clean_text(content),
        timestamp=str(timestamp), from_me=bool(from_me), media_type=media_type or "",
    )


_MESSAGE_COLUMNS = "id, chat_jid, sender, content, timestamp, is_from_me, media_type"


def chat_messages(conn: sqlite3.Connection, chat_jid: str, limit: int = 40) -> List[Message]:
    """The newest `limit` messages of one chat, oldest first."""
    rows = conn.execute(
        f"SELECT {_MESSAGE_COLUMNS} FROM messages WHERE chat_jid = ? ORDER BY timestamp DESC LIMIT ?",
        (chat_jid, limit),
    ).fetchall()
    return [_message(row) for row in reversed(rows)]


def _individual_chat_filter(conn: sqlite3.Connection, exclude: Iterable[str]) -> Tuple[str, list]:
    skipped = sorted(own_jids(conn) | set(exclude))
    sql = "(chat_jid LIKE '%@s.whatsapp.net' OR chat_jid LIKE '%@lid')"
    if skipped:
        sql += f" AND chat_jid NOT IN ({', '.join('?' * len(skipped))})"
    return sql, skipped


def owner_messages(conn: sqlite3.Connection, limit: int = 5000, exclude_chats: Iterable[str] = ()) -> List[Message]:
    """The owner's own text messages in one-to-one chats, newest first.

    Leaves out groups, status updates and the owner's "Message yourself" chat (where drafts arrive).
    """
    where, params = _individual_chat_filter(conn, exclude_chats)
    rows = conn.execute(
        f"""SELECT {_MESSAGE_COLUMNS} FROM messages
            WHERE is_from_me AND content IS NOT NULL AND content != '' AND {where}
            ORDER BY timestamp DESC LIMIT ?""",
        (*params, limit),
    ).fetchall()
    return [_message(row) for row in rows]


def owner_replies(conn: sqlite3.Connection, limit: int = 5000, exclude_chats: Iterable[str] = ()) -> List[ReplyPair]:
    """Customer message -> the owner's reply that directly followed it, newest first.

    One-to-one chats only, as in owner_messages(). Both sides must be text.
    """
    where, params = _individual_chat_filter(conn, exclude_chats)
    rows = conn.execute(
        f"""SELECT chat_jid, prev_content, content, timestamp FROM (
                SELECT chat_jid, content, is_from_me, timestamp,
                       LAG(content) OVER w AS prev_content,
                       LAG(is_from_me) OVER w AS prev_from_me
                FROM messages WHERE {where}
                WINDOW w AS (PARTITION BY chat_jid ORDER BY timestamp)
            )
            WHERE is_from_me AND NOT prev_from_me
              AND content IS NOT NULL AND content != '' AND prev_content IS NOT NULL AND prev_content != ''
            ORDER BY timestamp DESC LIMIT ?""",
        (*params, limit),
    ).fetchall()
    return [
        ReplyPair(chat_jid=chat, customer_text=clean_text(prev), reply_text=clean_text(reply), timestamp=str(ts))
        for chat, prev, reply, ts in rows
    ]


class DbSource:
    """The bridge database as a history source: the same two questions as gw_export.ExportSource."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def owner_messages(self, limit: int = 5000, exclude_chats: Iterable[str] = ()) -> List[Message]:
        return owner_messages(self.conn, limit, exclude_chats)

    def owner_replies(self, limit: int = 5000, exclude_chats: Iterable[str] = ()) -> List[ReplyPair]:
        return owner_replies(self.conn, limit, exclude_chats)
