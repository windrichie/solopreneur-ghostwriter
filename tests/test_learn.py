"""Tests for gw_learn.py (the learn-templates and learn-voice helper)."""
import re
import zipfile
import stat
import time
from pathlib import Path

import pytest

import gw_learn
from conftest import OWN_JID

SKILLS = Path(__file__).resolve().parent.parent / "skills"
CUSTOMER = "62811111111@s.whatsapp.net"

DIRECTIONS = "Halo kak! Untuk fitting bisa datang ke Jl. Melati No. 12 lantai 2, tanggal {d}/10 jam 10 ya, kami buka sampai jam 5 sore"
PAYMENT = "Pembayaran bisa transfer ke BCA 1234567 a.n. Toko Bunga, kirim bukti transfer ya kak, terima kasih"


WORDS = "alpha bravo charlie delta echo foxtrot golf hotel".split()


def chat_jid(i: int) -> str:
    return f"62812{i:07d}@s.whatsapp.net"


def ts(day: int, minute: int = 0) -> str:
    return f"2025-02-{day:02d} 10:{minute:02d}:00+08:00"


def run(capsys, *argv):
    code = gw_learn.main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_init_creates_private_files_and_never_overwrites(store, tmp_path, capsys):
    code, out, _ = run(capsys, "init")
    home = tmp_path / "ghostwriter-home"
    assert code == 0
    for name in ("voice.md", "templates.md", "facts.md"):
        path = home / name
        assert path.is_file() and str(path) in out and "created" in out
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(home.stat().st_mode) == 0o700
    assert "Notes language:" in (home / "voice.md").read_text()

    (home / "templates.md").write_text("# Templates\n\n## Mine\nUse when: x\nhello\n")
    code, out, _ = run(capsys, "init")
    assert code == 0 and "already existed" in out and "created" not in out
    assert "## Mine" in (home / "templates.md").read_text()


def test_find_templates_groups_variants(store, capsys):
    for i, day in enumerate((3, 5, 9, 12)):
        jid = chat_jid(i)
        text = DIRECTIONS.format(d=day)
        if i == 2:
            text = text.replace("fitting", "fiting")
        store.message(jid, "kak mau fitting hari sabtu bisa?", ts(day, 0))
        store.message(jid, text, ts(day, 1), from_me=True)
    for i in range(10):
        store.message(chat_jid(20 + i), "ok kak", ts(15, i), from_me=True)
    # copies in a group chat and in the owner's own chat must not count
    store.message("120363025246125486@g.us", DIRECTIONS.format(d=20), ts(20), from_me=True)
    store.message(OWN_JID, DIRECTIONS.format(d=21), ts(21), from_me=True)

    code, out, _ = run(capsys, "find-templates")
    assert code == 0
    assert "Used 4 times in 4 chats" in out
    assert "last 2025-02-12" in out and "2 variants" in out
    assert out.count("\n## ") == 1
    assert "ok kak" not in out.split("Most recent")[0].replace("Customers asked", "")
    assert '- "kak mau fitting hari sabtu bisa?"' in out
    assert "> Halo kak! Untuk fitting bisa datang" in out


def test_find_templates_min_count_and_limit(store, capsys):
    texts = [
        "Ongkos kirim ke Jakarta sekitar dua puluh ribu rupiah ya kak",
        "Kami buka setiap hari dari jam sembilan pagi sampai jam lima sore",
        "Mohon maaf stok warna merah sedang kosong, bisa pesan dulu",
    ]
    for n, (t, uses) in enumerate(zip(texts, (5, 4, 2))):
        for i in range(uses):
            store.message(chat_jid(i), t, ts(1 + n, i), from_me=True)
    code, out, _ = run(capsys, "find-templates", "--min-count", "4")
    assert code == 0 and "Used 5 times" in out and "Used 4 times" in out and "Used 2 times" not in out

    code, out, _ = run(capsys, "find-templates", "--min-count", "4", "--limit", "1")
    assert "Used 5 times" in out and "Used 4 times" not in out and "top 1 of 2" in out

    code, out, _ = run(capsys, "find-templates", "--min-count", "9")
    assert code == 0 and "No reply was sent at least 9 times" in out


def test_find_templates_with_no_messages(store, capsys):
    code, out, _ = run(capsys, "find-templates")
    assert code == 0 and "nothing to learn" in out


def test_voice_sample_is_spread_and_deterministic(store, capsys):
    for c in range(8):
        for k in range(6):
            day = 1 + c * 3 + k % 3
            store.message(chat_jid(c), f"customer question {WORDS[c]} {WORDS[k]}", ts(day, 10 + k * 2))
            body = f"reply {WORDS[c]} {WORDS[k]} is varied text about this order"
            if k % 2:
                body += " 😊"
            store.message(chat_jid(c), body, ts(day, 11 + k * 2), from_me=True)
    for c in range(5):  # a template sent 5 times: not voice
        store.message(chat_jid(c), "Where is your shop please", ts(28, c))
        store.message(chat_jid(c), "Our shop is at the mall, third floor, next to the bank", ts(28, c + 10), from_me=True)

    code, out, _ = run(capsys, "voice-sample", "--n", "20")
    assert code == 0
    assert "## Stats" in out and "## Sample replies (20)" in out
    assert "Median length" in out and "With at least one emoji: 4" in out  # 24 of 53 messages carry emoji (45%)
    assert "third floor" not in out.split("## Sample replies")[1]
    per_chat = {}
    for customer, owner in re.findall(r"Customer: (.*)\nOwner: (.*)", out):
        per_chat.setdefault(customer.split(" ")[2], []).append(owner)
        assert customer.startswith("customer question")
    assert per_chat and max(len(v) for v in per_chat.values()) <= 3

    _, again, _ = run(capsys, "voice-sample", "--n", "20")
    assert again == out
    _, other, _ = run(capsys, "voice-sample", "--n", "20", "--seed", "7")
    assert other != out


def test_voice_sample_keeps_short_repeated_replies(store, capsys):
    for c in range(4):  # a short reply the owner repeats is how they talk, not a template
        store.message(chat_jid(c), "ada stok kak?", ts(27, c))
        store.message(chat_jid(c), "baik kak", ts(27, c + 10), from_me=True)
    _, out, _ = run(capsys, "voice-sample")
    assert "Owner: baik kak" in out


def test_voice_stats_numbers(store, capsys):
    for i in range(10):
        text = f"halo kak 😊 {i}" if i < 5 else f"baik kak {i} ya?"
        store.message(chat_jid(i), "pesan", ts(1, i))
        store.message(chat_jid(i), text, ts(1, i + 20), from_me=True)
    _, out, _ = run(capsys, "voice-sample", "--n", "5")
    assert "With at least one emoji: 50%" in out and "😊 (5)" in out
    assert "Ending in ?: 50%" in out
    assert "Median length: 13 characters, 4 words" in out
    assert "kak (10)" in out


def test_voice_sample_excludes_self_chat_and_groups(store, capsys):
    store.message(chat_jid(1), "a question", ts(1, 0))
    store.message(chat_jid(1), "A normal friendly reply from the shop owner", ts(1, 1), from_me=True)
    store.message("120363025246125486@g.us", "group question", ts(2, 0), sender="62899")
    store.message("120363025246125486@g.us", "Group reply that must stay out", ts(2, 1), from_me=True)
    store.message(OWN_JID, "note to self", ts(3, 0))
    store.message(OWN_JID, "Draft: self chat text that must stay out", ts(3, 1), from_me=True)
    _, out, _ = run(capsys, "voice-sample")
    assert "friendly reply" in out
    assert "must stay out" not in out
    assert "Messages analysed: 1" in out


def test_no_source_is_a_clear_error_that_explains_both_options(capsys):
    for cmd in ("find-templates", "voice-sample"):
        code, out, err = run(capsys, cmd)
        assert code == 1 and out == "" and err.count("\n") == 1
        assert "--export" in err and "--store-dir" in err and "WHATSAPP_STORE_DIR" in err


def test_init_needs_no_history_source(tmp_path, capsys):
    code, out, _ = run(capsys, "init")
    home = tmp_path / "home" / ".ghostwriter"
    assert code == 0 and str(home) in out
    assert (home / "voice.md").is_file()


def test_missing_database_is_a_clear_error(store, capsys):
    store.db_path.unlink()
    code, _, err = run(capsys, "find-templates")
    assert code == 1 and "messages.db" in err


def test_skills_have_frontmatter():
    for name in ("learn-templates", "learn-voice"):
        text = (SKILLS / name / "SKILL.md").read_text()
        assert text.startswith("---\n")
        front = text.split("---\n")[1]
        fields = dict(line.split(":", 1) for line in front.splitlines() if re.match(r"^[a-z-]+:", line))
        assert fields["name"].strip() == name
        assert fields["description"].strip()


def test_find_templates_speed(store, capsys):
    import random
    rng = random.Random(1)
    words = "kak halo bisa harga ready stok ukuran warna kirim hari besok jam toko alamat transfer terima kasih pesanan".split()
    rows = []
    for i in range(3000):
        sentence = " ".join(rng.choice(words) for _ in range(rng.randint(6, 18)))
        rows.append((chat_jid(i % 150), f"{sentence} {i}", ts(1 + i % 27, i % 60)))
    for jid, text, stamp in rows:
        store.message(jid, text, stamp, from_me=True)
    started = time.process_time()
    code, _, _ = run(capsys, "find-templates")
    assert code == 0 and time.process_time() - started < 10


def test_store_dir_option_replaces_the_environment_variable(store, monkeypatch, capsys):
    store.message(chat_jid(1), "a question", ts(1, 0))
    store.message(chat_jid(1), "A normal friendly reply from the shop owner", ts(1, 1), from_me=True)
    monkeypatch.delenv("WHATSAPP_STORE_DIR")
    code, out, _ = run(capsys, "--store-dir", str(store.root), "voice-sample")
    assert code == 0 and "friendly reply" in out


# --------------------------------------------------------------------------- export source

def write_exports(root):
    """Two made-up chats between the owner ("Sam Shop") and two customers."""
    root.mkdir()
    directions = "Hi! The shop is at 12 Maple Street, second floor, open until 6 pm. See you!"
    ios = []
    for i, day in enumerate((3, 5, 9)):
        ios.append(f"[{day:02d}/03/2025, 10:0{i}:00] Alice: where is your shop?")
        ios.append(f"[{day:02d}/03/2025, 10:0{i}:30] Sam Shop: {directions}")
    ios.append("[10/03/2025, 11:00:00] Alice: thanks")
    ios.append("[10/03/2025, 11:01:00] Sam Shop: you are welcome 🙂")
    (root / "WhatsApp Chat - Alice.txt").write_text("\n".join(ios) + "\n", encoding="utf-8")
    android = [
        "11/03/2025, 09:00 - Bob: halo, toko di mana?",
        f"11/03/2025, 09:01 - Sam Shop: {directions}",
        "12/03/2025, 09:00 - Bob: ada stok?",
        "12/03/2025, 09:01 - Sam Shop: ada kak 🙂",
    ]
    with zipfile.ZipFile(root / "WhatsApp Chat - Bob.zip", "w") as zf:
        zf.writestr("_chat.txt", "\n".join(android) + "\n")
    return root


def test_names_lists_senders_with_counts_and_files(tmp_path, capsys):
    root = write_exports(tmp_path / "exports")
    code, out, err = run(capsys, "--export", str(root), "names")
    assert code == 0 and err == ""
    assert "| Sam Shop | 6 | 2 |" in out and "| Alice | 4 | 1 |" in out and "| Bob | 2 | 1 |" in out
    assert out.index("Sam Shop") < out.index("Alice") < out.index("Bob")


def test_names_needs_an_export(store, capsys):
    code, out, err = run(capsys, "names")
    assert code == 1 and out == "" and "--export" in err


def test_find_templates_from_exports(tmp_path, capsys):
    root = write_exports(tmp_path / "exports")
    code, out, err = run(capsys, "--export", str(root), "--me", "sam shop", "find-templates")
    assert code == 0 and err == ""
    assert "Used 4 times in 2 chats" in out and "2 variants" not in out
    assert '- "where is your shop?"' in out
    assert "> Hi! The shop is at 12 Maple Street" in out
    assert "Alice" not in out and "Bob" not in out  # customer names stay out of the summary


def test_voice_sample_from_exports(tmp_path, capsys):
    root = write_exports(tmp_path / "exports")
    code, out, _ = run(capsys, "--export", str(root / "WhatsApp Chat - Alice.txt"), "--export", str(root / "WhatsApp Chat - Bob.zip"),
                       "--me", "Sam Shop", "voice-sample")
    assert code == 0
    assert "Messages analysed: 6" in out and "## Sample replies (" in out
    assert "Customer: thanks\nOwner: you are welcome 🙂" in out
    assert "Owner: ada kak 🙂" in out


def test_me_is_found_when_one_name_is_in_every_file(tmp_path, capsys):
    root = write_exports(tmp_path / "exports")
    code, out, err = run(capsys, "--export", str(root), "voice-sample")
    assert code == 0 and "Messages analysed: 6" in out
    assert 'using "Sam Shop" as you' in err and err.count("\n") == 1


def test_me_cannot_be_found_when_it_is_unclear(tmp_path, capsys):
    root = write_exports(tmp_path / "exports")
    for args in (["--export", str(root / "WhatsApp Chat - Alice.txt")], ["--export", str(root / "WhatsApp Chat - Bob.zip")]):
        code, out, err = run(capsys, *args, "find-templates")  # one file: both names are in every file
        assert code == 1 and out == "" and "names" in err and "--me" in err and err.count("\n") == 1


def test_wrong_me_says_nothing_was_found_and_suggests_names(tmp_path, capsys):
    root = write_exports(tmp_path / "exports")
    for command in ("find-templates", "voice-sample"):
        code, out, _ = run(capsys, "--export", str(root), "--me", "Nobody", command)
        assert code == 0 and "No messages from \"Nobody\"" in out and "`names`" in out and "--date-order" in out


def test_date_order_option_reaches_the_parser(tmp_path, capsys):
    root = tmp_path / "exports"
    root.mkdir()
    (root / "a.txt").write_text(
        "03/04/2025, 10:00 - Alice: a question\n03/04/2025, 10:01 - Sam: a long enough reply to be counted here\n"
    )
    _, out, _ = run(capsys, "--export", str(root), "--me", "Sam", "--date-order", "mdy", "find-templates", "--min-count", "1")
    assert "first 2025-03-04" in out
    _, out, _ = run(capsys, "--export", str(root), "--me", "Sam", "find-templates", "--min-count", "1")
    assert "first 2025-04-03" in out


def test_export_and_store_dir_together_are_refused(store, tmp_path, capsys):
    root = write_exports(tmp_path / "exports")
    code, out, err = run(capsys, "--store-dir", str(store.root), "--export", str(root), "names")
    assert code == 1 and out == "" and "not both" in err


def test_me_and_date_order_need_an_export(store, capsys):
    for extra in (["--me", "Sam"], ["--date-order", "mdy"]):
        code, out, err = run(capsys, *extra, "find-templates")
        assert code == 1 and out == "" and "--export" in err


def test_export_source_wins_over_the_environment_variable(store, tmp_path, capsys):
    store.message(chat_jid(1), "a question", ts(1, 0))
    store.message(chat_jid(1), "A reply that comes from the database only", ts(1, 1), from_me=True)
    root = write_exports(tmp_path / "exports")
    _, out, _ = run(capsys, "--export", str(root), "--me", "Sam Shop", "voice-sample")
    assert "database only" not in out and "Messages analysed: 6" in out


def test_bad_export_path_is_a_clear_error(tmp_path, capsys):
    code, out, err = run(capsys, "--export", str(tmp_path / "nope"), "--me", "Sam", "find-templates")
    assert code == 1 and out == "" and "no such file" in err and err.count("\n") == 1


def test_exports_are_read_only(tmp_path, capsys):
    root = write_exports(tmp_path / "exports")
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    run(capsys, "--export", str(root), "--me", "Sam Shop", "voice-sample")
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before
