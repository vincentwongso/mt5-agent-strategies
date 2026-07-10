#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


RUNTIME_DIRS = {
    "openclaw": Path("~/.openclaw/skills").expanduser(),
    "hermes": Path("~/.hermes/skills").expanduser(),
    "claude-code": Path("~/.claude/skills").expanduser(),
    "codex": Path("~/.codex/skills").expanduser(),
}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Install the orb-strategy Agent Skill")
    group = result.add_mutually_exclusive_group(required=True)
    group.add_argument("--runtime", choices=sorted(RUNTIME_DIRS))
    group.add_argument("--target", type=Path, help="Explicit parent skill directory")
    result.add_argument("--force", action="store_true", help="Replace an existing install")
    result.add_argument("--verify", action="store_true", help="Only verify the destination")
    return result


def main() -> int:
    args = parser().parse_args()
    root = Path(__file__).resolve().parent.parent
    source = root / "skills" / "orb-strategy"
    parent = args.target.expanduser().resolve() if args.target else RUNTIME_DIRS[args.runtime]
    destination = parent / "orb-strategy"

    if args.verify:
        skill = destination / "SKILL.md"
        if not skill.is_file():
            raise SystemExit(f"not installed: {skill}")
        print(f"verified: {skill}")
        return 0

    if destination.exists():
        if not args.force:
            raise SystemExit(f"already exists: {destination} (pass --force to replace)")
        shutil.rmtree(destination)
    parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    print(f"installed: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

