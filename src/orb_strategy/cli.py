from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .errors import OrbError
from .evaluator import evaluate
from .parsing import load_config, load_input


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orb-evaluate",
        description="Evaluate open-range breakout states from timestamped OHLC bars.",
    )
    parser.add_argument("--config", required=True, help="Path to strategy YAML config")
    parser.add_argument("--input", required=True, help="Path to OHLC input JSON")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = evaluate(load_config(args.config), load_input(args.input))
    except OrbError as exc:
        print(json.dumps({"error": {"code": "INVALID_INPUT", "message": str(exc)}}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2 if args.pretty else None, separators=None if args.pretty else (",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

