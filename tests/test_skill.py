"""Contract every bundled skill must satisfy. A new strategy's skill is checked here
automatically, with no edit to this file."""

from pathlib import Path

import pytest
import yaml

SKILLS_ROOT = Path("skills")
SKILLS = sorted(path for path in SKILLS_ROOT.iterdir() if (path / "SKILL.md").is_file())


def frontmatter(skill: Path) -> dict:
    text = (skill / "SKILL.md").read_text()
    assert text.startswith("---\n"), f"{skill.name}: SKILL.md must open with YAML frontmatter"
    return yaml.safe_load(text.split("---\n", 2)[1])


def test_at_least_one_skill_is_bundled():
    assert SKILLS, "expected at least one skills/*/SKILL.md"


@pytest.mark.parametrize("skill", SKILLS, ids=lambda path: path.name)
def test_skill_has_required_assets(skill: Path):
    assert (skill / "config.example.yaml").is_file()
    assert (skill / "references").is_dir()
    assert any((skill / "references").glob("*.md"))


@pytest.mark.parametrize("skill", SKILLS, ids=lambda path: path.name)
def test_skill_frontmatter_matches_directory(skill: Path):
    meta = frontmatter(skill)
    assert meta["name"] == skill.name
    assert meta["description"].strip()


@pytest.mark.parametrize("skill", SKILLS, ids=lambda path: path.name)
def test_skill_states_the_advisory_boundary(skill: Path):
    text = (skill / "SKILL.md").read_text().lower()
    assert "advisory" in text, f"{skill.name}: SKILL.md must state the advisory-only boundary"
