from pathlib import Path


ROOT = Path("skills/orb-strategy")


def test_skill_assets_exist():
    assert (ROOT / "SKILL.md").is_file()
    assert (ROOT / "scripts/evaluate.py").is_file()
    assert (ROOT / "references/input-format.md").is_file()
    assert (ROOT / "references/playbook.md").is_file()
    assert (ROOT / "agents/openai.yaml").is_file()

