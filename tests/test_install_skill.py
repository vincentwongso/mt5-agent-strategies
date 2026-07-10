import subprocess
import sys

SCRIPT = "scripts/install_skill.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, SCRIPT, *args], check=True, capture_output=True, text=True
    )


def test_lists_bundled_skills():
    listed = run("--list").stdout.split()
    assert "orb-strategy" in listed


def test_installs_every_bundled_skill_and_verifies(tmp_path):
    installed = run("--target", str(tmp_path))
    assert "installed:" in installed.stdout
    for name in run("--list").stdout.split():
        assert (tmp_path / name / "SKILL.md").is_file()
    assert "verified:" in run("--target", str(tmp_path), "--verify").stdout


def test_refuses_to_overwrite_without_force(tmp_path):
    run("--target", str(tmp_path))
    clash = subprocess.run(
        [sys.executable, SCRIPT, "--target", str(tmp_path)], capture_output=True, text=True
    )
    assert clash.returncode != 0
    assert "pass --force to replace" in clash.stderr
    assert "installed:" in run("--target", str(tmp_path), "--force").stdout


def test_installs_a_single_named_skill(tmp_path):
    assert "installed:" in run("--target", str(tmp_path), "--skill", "orb-strategy").stdout
    assert (tmp_path / "orb-strategy" / "SKILL.md").is_file()


def test_unknown_skill_is_rejected(tmp_path):
    failure = subprocess.run(
        [sys.executable, SCRIPT, "--target", str(tmp_path), "--skill", "nope"],
        capture_output=True,
        text=True,
    )
    assert failure.returncode != 0
    assert "unknown skill: nope" in failure.stderr
