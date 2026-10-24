"""Tests for gw_export.py: reading WhatsApp "Export chat" files. All data here is made up."""
import zipfile

import pytest

import gw_export
from gw_export import ExportError, load_exports, parse_text

LRM = "‎"
NNBSP = " "


def parse(text, order="dmy"):
    return parse_text(text, "export:test", order)


def rows(entries):
    return [(e.timestamp, e.sender, e.content, e.media_type) for e in entries]


def test_ios_24_hour_with_seconds():
    text = (
        f"{LRM}[24/10/2026, 21:05:12] Alice: Hello, are you open today?\n"
        f"[24/10/2026, 21:06:40] Sam Shop: Yes, until 6 pm\n"
    )
    assert rows(parse(text)) == [
        ("2026-10-24 21:05:12", "Alice", "Hello, are you open today?", ""),
        ("2026-10-24 21:06:40", "Sam Shop", "Yes, until 6 pm", ""),
    ]


def test_ios_12_hour_am_pm_us_dates():
    text = (
        "[10/24/26, 9:05:12 PM] Alice: evening\n"
        "[10/25/26, 12:01:00 AM] Sam Shop: midnight\n"
        "[10/25/26, 12:30:00 PM] Alice: noon\n"
    )
    assert [e.timestamp for e in parse(text)] == ["2026-10-24 21:05:12", "2026-10-25 00:01:00", "2026-10-25 12:30:00"]


def test_android_24_hour_without_seconds():
    text = "24/10/2026, 21:05 - Alice: hi\n24/10/2026, 21:06 - Sam Shop: hello\n"
    assert rows(parse(text)) == [
        ("2026-10-24 21:05:00", "Alice", "hi", ""),
        ("2026-10-24 21:06:00", "Sam Shop", "hello", ""),
    ]


def test_android_us_12_hour_with_narrow_no_break_space():
    text = f"10/24/26, 9:05{NNBSP}PM - Alice: hi\n10/24/26, 9:07{NNBSP}pm - Sam Shop: hello\n"
    assert [(e.timestamp, e.content) for e in parse(text)] == [("2026-10-24 21:05:00", "hi"), ("2026-10-24 21:07:00", "hello")]


def test_other_date_separators_and_year_first():
    text = "24.10.26, 21:05 - Alice: dots\n24-10-2026 21:06 - Alice: dashes\n2026-10-24, 21:07 - Alice: iso\n"
    assert [e.timestamp[:10] for e in parse(text)] == ["2026-10-24"] * 3


def test_invisible_marks_are_kept_out_of_names_and_text():
    text = f"{LRM}[24/10/2026, 21:05:12] {LRM}Alice: {LRM}hello there\n"
    [entry] = parse(text)
    assert (entry.sender, entry.content) == ("Alice", "hello there")


def test_multi_line_messages_continue_the_previous_message():
    text = (
        "24/10/2026, 21:05 - Alice: first line\n"
        "second line\n"
        "\n"
        "third line\n"
        "24/10/2026, 21:06 - Sam Shop: ok\n"
    )
    assert parse(text)[0].content == "first line\nsecond line\n\nthird line"


def test_system_lines_are_skipped_with_their_continuations():
    text = (
        "24/10/2026, 21:00 - Messages and calls are end-to-end encrypted. No one outside of this chat can read them.\n"
        "24/10/2026, 21:01 - Alice changed their phone number to a new number. Tap to message or add the new number.\n"
        "more system text\n"
        f"{LRM}[24/10/2026, 21:02:00] Alice: real message\n"
        f"{LRM}[24/10/2026, 21:03:00] Your security code with Alice changed. Tap to learn more.\n"
    )
    assert rows(parse(text)) == [("2026-10-24 21:02:00", "Alice", "real message", "")]


def test_media_and_deleted_placeholders():
    text = (
        f"[24/10/2026, 21:00:00] Alice: {LRM}<attached: 00000012-PHOTO-2026-10-24-21-00-00.jpg>\n"
        f"[24/10/2026, 21:01:00] Alice: {LRM}<attached: 00000013-AUDIO-2026-10-24-21-01-00.opus>\n"
        f"[24/10/2026, 21:02:00] Alice: {LRM}<attached: 00000014-STICKER-2026-10-24-21-02-00.webp>\n"
        f"[24/10/2026, 21:03:00] Alice: {LRM}<attached: invoice.pdf>\n"
        "[24/10/2026, 21:04:00] Alice: image omitted\n"
        "[24/10/2026, 21:05:00] Alice: video omitted\n"
        "[24/10/2026, 21:06:00] Alice: audio omitted\n"
        "[24/10/2026, 21:07:00] Alice: sticker omitted\n"
        "[24/10/2026, 21:08:00] Alice: document omitted\n"
        f"[24/10/2026, 21:09:00] Alice: {LRM}This message was deleted.\n"
        "24/10/2026, 21:10 - Sam Shop: <Media omitted>\n"
        "24/10/2026, 21:11 - Sam Shop: This message was deleted\n"
        "24/10/2026, 21:12 - Sam Shop: You deleted this message\n"
    )
    kinds = [e.media_type for e in parse(text)]
    assert kinds == ["image", "audio", "sticker", "document", "image", "video", "audio", "sticker", "document",
                     "deleted", "media", "deleted", "deleted"]
    assert all(e.content == "" for e in parse(text))


def test_edited_marker_is_removed():
    [entry] = parse("24/10/2026, 21:05 - Alice: see you at 5 <This message was edited>\n")
    assert entry.content == "see you at 5"


def test_names_with_spaces_emoji_numbers_and_colons():
    text = (
        "24/10/2026, 21:05 - +65 9123 4567: hi\n"
        "24/10/2026, 21:06 - Sam 🌸 Shop: hello: how can I help? 10:30 works\n"
    )
    assert rows(parse(text)) == [
        ("2026-10-24 21:05:00", "+65 9123 4567", "hi", ""),
        ("2026-10-24 21:06:00", "Sam 🌸 Shop", "hello: how can I help? 10:30 works", ""),
    ]


def test_date_order_is_found_from_the_dates_or_taken_from_the_default():
    day_first = "03/04/2026, 10:00 - Alice: a\n13/04/2026, 10:00 - Alice: b\n"
    assert [e.timestamp[:10] for e in parse(day_first, order="mdy")] == ["2026-04-03", "2026-04-13"]
    month_first = "03/04/2026, 10:00 - Alice: a\n04/13/2026, 10:00 - Alice: b\n"
    assert [e.timestamp[:10] for e in parse(month_first, order="dmy")] == ["2026-03-04", "2026-04-13"]
    unclear = "03/04/2026, 10:00 - Alice: a\n"
    assert parse(unclear)[0].timestamp[:10] == "2026-04-03"  # default: day first
    assert parse(unclear, order="mdy")[0].timestamp[:10] == "2026-03-04"


def test_an_impossible_date_is_part_of_the_message_before():
    text = "24/10/2026, 21:05 - Alice: look\n31/02/2026, 10:00 - not a message\n"
    assert parse(text)[0].content == "look\n31/02/2026, 10:00 - not a message"


def test_empty_and_bom_and_invalid_bytes(tmp_path):
    (tmp_path / "bom.txt").write_bytes("﻿24/10/2026, 21:05 - Alice: hi\n".encode("utf-8"))
    (tmp_path / "bad.txt").write_bytes(b"24/10/2026, 21:05 - Bob: caf\xe9 ok\n")
    source = load_exports([str(tmp_path)], "Bob")
    contents = {c.chat_id: c.entries[0].content for c in source.chats}
    assert contents == {"export:bad": "caf� ok", "export:bom": "hi"}
    (tmp_path / "empty.txt").write_text("")
    assert len(load_exports([str(tmp_path)], "Bob").chats) == 2  # the empty file is skipped


def test_group_files_are_skipped_with_a_warning(tmp_path, capsys):
    (tmp_path / "Group.txt").write_text(
        "24/10/2026, 21:05 - Alice: hi\n24/10/2026, 21:06 - Bob: hi\n24/10/2026, 21:07 - Carol: hi\n"
    )
    (tmp_path / "Pair.txt").write_text("24/10/2026, 21:05 - Alice: hi\n24/10/2026, 21:06 - Sam: hi\n")
    source = load_exports([str(tmp_path)], "Sam")
    assert [c.chat_id for c in source.chats] == ["export:Pair"]
    err = capsys.readouterr().err
    assert "Group.txt" in err and "group" in err and "Carol" not in err


def test_only_groups_is_an_error(tmp_path):
    (tmp_path / "G.txt").write_text(
        "24/10/2026, 21:05 - A: hi\n24/10/2026, 21:06 - B: hi\n24/10/2026, 21:07 - C: hi\n"
    )
    with pytest.raises(ExportError, match="no one-to-one chats"):
        load_exports([str(tmp_path)], "A")


def make_zip(path, members):
    with zipfile.ZipFile(path, "w") as zf:
        for name, text in members.items():
            zf.writestr(name, text)


def test_zip_with_one_chat_file(tmp_path):
    make_zip(tmp_path / "WhatsApp Chat - Alice.zip", {"_chat.txt": "24/10/2026, 21:05 - Alice: hi\n24/10/2026, 21:06 - Sam: yo\n"})
    source = load_exports([str(tmp_path / "WhatsApp Chat - Alice.zip")], "Sam")
    assert [c.chat_id for c in source.chats] == ["export:WhatsApp Chat - Alice"]
    assert [m.content for m in source.owner_messages()] == ["yo"]


def test_zip_with_several_txt_prefers_the_chat_file(tmp_path):
    line = "24/10/2026, 21:05 - Alice: hi\n"
    make_zip(tmp_path / "a.zip", {"notes.txt": "nothing here\n", "WhatsApp Chat with Alice.txt": line, "__MACOSX/._x.txt": "junk"})
    assert load_exports([str(tmp_path / "a.zip")], "Sam").chats[0].entries[0].content == "hi"
    make_zip(tmp_path / "b.zip", {"one.txt": line, "two.txt": line})
    with pytest.raises(ExportError, match="one chat .txt"):
        load_exports([str(tmp_path / "b.zip")], "Sam")


def test_bad_inputs_give_one_clear_error(tmp_path):
    (tmp_path / "x.zip").write_text("not a zip")
    (tmp_path / "x.pdf").write_text("x")
    for bad, message in ((tmp_path / "x.zip", "not a valid zip"), (tmp_path / "x.pdf", "not a .txt or .zip"),
                         (tmp_path / "missing", "no such file"), (tmp_path / "empty-dir", "no such file")):
        with pytest.raises(ExportError, match=message):
            load_exports([str(bad)], "Sam")
    (tmp_path / "folder").mkdir()
    with pytest.raises(ExportError, match="no .txt or .zip"):
        load_exports([str(tmp_path / "folder")], "Sam")


def test_folder_search_and_chat_ids(tmp_path):
    line = "24/10/2026, 21:05 - Alice: hi\n24/10/2026, 21:06 - Sam: yo\n"
    (tmp_path / "Alice.txt").write_text(line)
    (tmp_path / "unzipped").mkdir()
    (tmp_path / "unzipped" / "_chat.txt").write_text(line.replace("hi", "hello"))
    (tmp_path / ".hidden.txt").write_text(line)
    (tmp_path / "readme.md").write_text("x")
    source = load_exports([str(tmp_path), str(tmp_path / "Alice.txt")], "Sam")
    assert sorted(c.chat_id for c in source.chats) == ["export:Alice", "export:unzipped"]


def test_names_and_owner_questions(tmp_path):
    (tmp_path / "A.txt").write_text(
        "24/10/2026, 10:00 - Alice: price?\n24/10/2026, 10:01 - Sam Shop: 10 dollars\n"
        "24/10/2026, 10:02 - Alice: ok\n24/10/2026, 10:03 - Alice: <Media omitted>\n"
        "24/10/2026, 10:04 - sam shop: sold out\n"
    )
    (tmp_path / "B.txt").write_text("25/10/2026, 10:00 - Bob: open?\n25/10/2026, 10:01 - Sam Shop: yes\n")
    source = load_exports([str(tmp_path)])
    assert [(s.name, s.messages, s.files) for s in source.names()] == [("Alice", 3, 1), ("Sam Shop", 3, 2), ("Bob", 1, 1)]
    assert source.names_in_every_file() == ["Sam Shop"]
    assert source.owner_messages() == []  # no owner chosen yet
    source.me = " SAM SHOP "
    assert [m.content for m in source.owner_messages()] == ["yes", "sold out", "10 dollars"]
    assert all(m.from_me for m in source.owner_messages())
    # the reply after "<Media omitted>" has no customer text, so it is not a pair
    assert [(p.customer_text, p.reply_text) for p in source.owner_replies()] == [("open?", "yes"), ("price?", "10 dollars")]
    assert source.owner_messages(limit=1)[0].content == "yes"
    assert source.owner_messages(exclude_chats=["export:B"])[0].content == "sold out"
    assert source.owner_messages()[0].chat_jid == "export:B"


def test_unknown_date_order_is_refused(tmp_path):
    (tmp_path / "a.txt").write_text("24/10/2026, 21:05 - Alice: hi\n")
    with pytest.raises(ExportError, match="date order"):
        load_exports([str(tmp_path)], None, "ymd")


def test_ios_encryption_notice_with_the_contact_name_is_not_a_message():
    text = (
        f"{LRM}[24/10/2026, 21:00:00] Alice: {LRM}Messages and calls are end-to-end encrypted. No one outside of this chat can read them.\n"
        "[24/10/2026, 21:01:00] Alice: real message\n"
        "[24/10/2026, 21:02:00] Alice: Your security code with Sam changed. Tap to learn more.\n"
    )
    assert [e.content for e in parse(text)] == ["real message"]


def test_long_runs_of_spaces_are_fast():
    import time
    hostile = "a" + " " * 60000 + "b"
    text = f"24/10/2026, 21:05 - Alice: {hostile}\n" + "24/10/2026, 21:06 - Sam: " + " " * 60000 + "\n"
    started = time.process_time()
    parse(text)
    assert time.process_time() - started < 2


def test_a_zip_and_its_unzipped_copy_count_once(tmp_path, capsys):
    line = "24/10/2026, 21:05 - Alice: hi\n24/10/2026, 21:06 - Sam: yo\n"
    make_zip(tmp_path / "WhatsApp Chat - Alice.zip", {"_chat.txt": line})
    (tmp_path / "WhatsApp Chat - Alice").mkdir()
    (tmp_path / "WhatsApp Chat - Alice" / "_chat.txt").write_text(line)
    source = load_exports([str(tmp_path)], "Sam")
    assert len(source.chats) == 1 and len(source.owner_messages()) == 1
    assert "same messages" in capsys.readouterr().err


def test_chat_ids_stay_unique_for_three_files_with_one_name(tmp_path):
    for folder, text in (("a", "hi"), ("b", "hello"), ("c", "hey")):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "Chat.txt").write_text(f"24/10/2026, 21:05 - Alice: {text}\n24/10/2026, 21:06 - Sam: yo\n")
    source = load_exports([str(tmp_path)], "Sam")
    ids = [c.chat_id for c in source.chats]
    assert sorted(ids) == ["export:Chat", "export:Chat#2", "export:Chat#3"]


def test_damaged_or_protected_zips_and_unreadable_folders_give_one_clear_error(tmp_path, monkeypatch):
    make_zip(tmp_path / "locked.zip", {"_chat.txt": "24/10/2026, 21:05 - Alice: hi\n"})

    def refuse(self, *args, **kwargs):
        raise RuntimeError("File is encrypted, password required for extraction")

    monkeypatch.setattr(zipfile.ZipFile, "open", refuse)
    with pytest.raises(ExportError, match="locked.zip: cannot read the zip"):
        load_exports([str(tmp_path / "locked.zip")], "Sam")
    monkeypatch.undo()

    def denied(self, pattern):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(type(tmp_path), "rglob", denied)
    with pytest.raises(ExportError, match="Permission denied"):
        load_exports([str(tmp_path)], "Sam")
