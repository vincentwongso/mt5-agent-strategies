#!/usr/bin/env python3
"""Install the bundled Agent Skills into an agent runtime's skill directory.

Skills are discovered from `skills/*/SKILL.md`, so a new strategy's skill is picked
up without editing this script.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = ROOT / "skills"

RUNTIME_DIRS = {
    "claude-code": Path("~/.claude/skills"),
    "codex": Path("~/.codex/skills"),
    "hermes": Path("~/.hermes/skills"),
    "openclaw": Path("~/.openclaw/skills"),
}


def discover() -> list[Path]:
    if not SKILLS_ROOT.is_dir():
        return []
    return sorted(path for path in SKILLS_ROOT.iterdir() if (path / "SKILL.md").is_file())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install this repo's Agent Skills")
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--runtime", choices=sorted(RUNTIME_DIRS))
    destination.add_argument("--target", type=Path, help="Explicit parent skill directory")
    destination.add_argument("--list", action="store_true", help="List bundled skills and exit")
    parser.add_argument("--skill", help="Install only this skill (default: all)")
    parser.add_argument("--force", action="store_true", help="Replace an existing install")
    parser.add_argument("--verify", action="store_true", help="Only verify the destination")
    return parser


def select(name: str | None) -> list[Path]:
    available = discover()
    if not available:
        raise SystemExit(f"no skills found under {SKILLS_ROOT}")
    if name is None:
        return available
    chosen = [path for path in available if path.name == name]
    if not chosen:
        known = ", ".join(path.name for path in available)
        raise SystemExit(f"unknown skill: {name} (available: {known})")
    return chosen


def main() -> int:
    args = build_parser().parse_args()

    if args.list:
        for path in discover():
            print(path.name)
        return 0

    if args.target:
        parent = args.target.expanduser().resolve()
    else:
        parent = RUNTIME_DIRS[args.runtime].expanduser()

    for source in select(args.skill):
        destination = parent / source.name

        if args.verify:
            skill = destination / "SKILL.md"
            if not skill.is_file():
                raise SystemExit(f"not installed: {skill}")
            print(f"verified: {skill}")
            continue

        if destination.exists():
            if not args.force:
                raise SystemExit(f"already exists: {destination} (pass --force to replace)")
            shutil.rmtree(destination)
        parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__"))
        print(f"installed: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
