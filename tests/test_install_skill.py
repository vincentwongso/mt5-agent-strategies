import subprocess
import sys


def test_installer_copies_and_verifies_skill(tmp_path):
    command = [sys.executable, "scripts/install_skill.py", "--target", str(tmp_path)]
    installed = subprocess.run(command, check=True, capture_output=True, text=True)
    assert "installed:" in installed.stdout
    assert (tmp_path / "orb-strategy" / "SKILL.md").is_file()
    verified = subprocess.run(command + ["--verify"], check=True, capture_output=True, text=True)
    assert "verified:" in verified.stdout
