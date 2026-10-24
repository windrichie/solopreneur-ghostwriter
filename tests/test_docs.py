"""The README and the skills speak to any owner: no gendered pronouns, no one's personal details."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_FILES = sorted((ROOT / "skills").glob("*/SKILL.md"))
DOC_FILES = [ROOT / "README.md", *SKILL_FILES]
GENDERED = re.compile(r"\b(she|her|hers|herself|he|him|his|himself)\b", re.IGNORECASE)
PERSONAL = re.compile(r"WS-|coordinator|/Users/")


def test_the_three_skills_exist():
    assert [p.parent.name for p in SKILL_FILES] == ["draft-reply", "learn-templates", "learn-voice"]


@pytest.mark.parametrize("path", DOC_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_docs_are_gender_neutral_and_impersonal(path):
    text = path.read_text(encoding="utf-8")
    assert GENDERED.findall(text) == []
    assert PERSONAL.findall(text) == []


@pytest.mark.parametrize("path", sorted((ROOT / "scripts").glob("*.py")) + [ROOT / "bin" / "draft"], ids=lambda p: p.name)
def test_scripts_are_gender_neutral_and_impersonal(path):
    text = path.read_text(encoding="utf-8")
    assert GENDERED.findall(text) == []
    assert PERSONAL.findall(text) == []


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_skill_frontmatter_matches_the_folder(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    front = text.split("---\n")[1]
    fields = dict(line.split(":", 1) for line in front.splitlines() if re.match(r"^[a-z-]+:", line))
    assert fields["name"].strip() == path.parent.name
    assert fields["description"].strip()


@pytest.mark.parametrize("name", ["learn-templates", "learn-voice"])
def test_learn_skills_preapprove_exactly_the_learn_script(name):
    text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    assert re.search(r"^allowed-tools: Bash\(python3 -I \$\{CLAUDE_PLUGIN_ROOT\}/scripts/gw_learn\.py \*\)$", text, re.MULTILINE)


def test_draft_reply_skill_never_passes_customer_text_to_a_command():
    text = (ROOT / "skills" / "draft-reply" / "SKILL.md").read_text(encoding="utf-8")
    assert "gw_draft.py files" in text
    assert "gw_draft.py draft" not in text and "--paste" not in text
