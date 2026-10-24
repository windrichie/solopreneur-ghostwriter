import sqlite3
import stat

import pytest

import gw_store
from conftest import OWN_JID, OWN_LID

ALICE = "111111111111111@lid"
BOB = "6591234567@s.whatsapp.net"
GROUP = "120363025246125486@g.us"


def test_owner_replies_pair_customer_messages_with_her_answers(store):
    store.conversation(ALICE, [("customer", "hi, open sunday?"), ("me", "Hi kak! Closed on Sunday 🙏"), ("me", "Mon-Sat 10-6")])
    store.conversation(BOB, [("me", "promo starts today"), ("customer", "price?"), ("me", "IDR 250k")], start_hour=11)
    store.conversation(GROUP, [("customer", "group q"), ("me", "group answer")], start_hour=12)
    store.conversation(OWN_JID, [("customer", "draft header"), ("me", "draft body")], start_hour=13)

    with gw_store.connect() as conn:
        pairs = gw_store.owner_replies(conn)
        mine = gw_store.owner_messages(conn)
    assert [(p.chat_jid, p.customer_text, p.reply_text) for p in pairs] == [
        (BOB, "price?", "IDR 250k"),
        (ALICE, "hi, open sunday?", "Hi kak! Closed on Sunday 🙏"),
    ]
    assert [m.content for m in mine] == ["IDR 250k", "promo starts today", "Mon-Sat 10-6", "Hi kak! Closed on Sunday 🙏"]


def test_chat_messages_and_label(store):
    store.chat(ALICE, "Alice Tan")
    store.contact(ALICE, "6591234567", "Alice Tan")
    store.conversation(ALICE, [("customer", f"m{i}") for i in range(5)])
    with gw_store.connect() as conn:
        assert [m.content for m in gw_store.chat_messages(conn, ALICE, limit=3)] == ["m2", "m3", "m4"]
        assert gw_store.chat_label(conn, ALICE) == ("Alice Tan", "6591234567")
        assert gw_store.chat_label(conn, "999@lid") == ("999", None)
        assert gw_store.own_jids(conn) == {OWN_JID, OWN_LID}


def test_untrusted_text_is_cleaned(store):
    store.message(ALICE, "hello‮​\x1b[31m‍👍", "2025-01-02 09:00:00+08:00")
    with gw_store.connect() as conn:
        assert gw_store.chat_messages(conn, ALICE)[0].content == "hello[31m‍👍"


def test_database_is_read_only_and_data_dir_is_private(store):
    with gw_store.connect() as conn:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM messages")
    home = gw_store.data_dir()
    assert stat.S_IMODE(home.stat().st_mode) == 0o700


def test_invalid_utf8_is_replaced_not_raised(store):
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("INSERT INTO chats VALUES (?, 'x', '2025-01-02 09:00:00+08:00')", (ALICE,))
        conn.execute(
            "INSERT INTO messages (id, chat_jid, sender, content, timestamp, is_from_me) VALUES ('M1', ?, 's', CAST(X'6869FF' AS TEXT), '2025-01-02 09:00:00+08:00', 0)",
            (ALICE,),
        )
    with gw_store.connect() as conn:
        assert gw_store.chat_messages(conn, ALICE)[0].content == "hi\ufffd"


def test_chat_jid_validation():
    assert gw_store.validate_chat_jid(ALICE) == ALICE
    for bad in [GROUP, "status@broadcast", "../x@lid", "6591234567", "", "1@lid; rm -rf /", ALICE + "\n"]:
        with pytest.raises(ValueError):
            gw_store.validate_chat_jid(bad)


def test_data_dir_defaults_to_a_private_folder_in_home(isolated_home):
    path = gw_store.data_dir()
    assert path == isolated_home / ".ghostwriter"
    assert stat.S_IMODE(path.stat().st_mode) == 0o700


def test_data_dir_does_not_depend_on_the_bridge_store(store, monkeypatch, isolated_home):
    monkeypatch.delenv("GHOSTWRITER_HOME")
    assert gw_store.data_dir() == isolated_home / ".ghostwriter"
    monkeypatch.delenv("WHATSAPP_STORE_DIR")
    assert gw_store.data_dir() == isolated_home / ".ghostwriter"


def test_ghostwriter_home_overrides_the_default(tmp_path, monkeypatch, isolated_home):
    monkeypatch.setenv("GHOSTWRITER_HOME", str(tmp_path / "shop-two"))
    path = gw_store.data_dir()
    assert path == tmp_path / "shop-two" and stat.S_IMODE(path.stat().st_mode) == 0o700
    assert not (isolated_home / ".ghostwriter").exists()


def test_data_dir_is_tightened_when_it_already_exists(isolated_home):
    folder = isolated_home / ".ghostwriter"
    folder.mkdir(mode=0o755)
    folder.chmod(0o755)
    assert stat.S_IMODE(gw_store.data_dir().stat().st_mode) == 0o700


def test_legacy_folder_is_noticed_only_when_it_holds_files(store, monkeypatch, isolated_home):
    monkeypatch.delenv("GHOSTWRITER_HOME")
    assert gw_store.legacy_note() is None
    old = store.root / "ghostwriter"
    old.mkdir()
    assert gw_store.legacy_note() is None  # empty
    (old / "voice.md").write_text("# Voice\nNotes language: English\n## Tone\n")
    assert gw_store.legacy_note() is None  # only the skeleton
    (old / "voice.md").write_text("# Voice\nNotes language: English\n## Tone\nWarm and short.\n")
    note = gw_store.legacy_note()
    assert str(old) in note and str(isolated_home / ".ghostwriter") in note and "GHOSTWRITER_HOME" in note
    new = isolated_home / ".ghostwriter"
    new.mkdir(mode=0o700, exist_ok=True)
    (new / "voice.md").write_text("# Voice\n## Tone\n")  # a fresh skeleton does not hide the note
    assert gw_store.legacy_note() is not None
    (new / "facts.md").write_text("# Facts\n- Hours: 10-6\n")  # real content in the new folder: no note
    assert gw_store.legacy_note() is None
    (new / "facts.md").unlink()
    monkeypatch.setenv("GHOSTWRITER_HOME", str(old))  # already using the old folder
    assert gw_store.legacy_note() is None


def test_missing_store_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("WHATSAPP_STORE_DIR", str(tmp_path / "nope"))
    with pytest.raises(gw_store.StoreError, match="No message database"):
        gw_store.connect()
    monkeypatch.delenv("WHATSAPP_STORE_DIR")
    with pytest.raises(gw_store.StoreError, match="WHATSAPP_STORE_DIR"):
        gw_store.store_dir()
