from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence

from . import registry, strategies  # noqa: F401  importing strategies registers them
from .core.errors import StrategyError
from .core.format import iso_utc
from .core.parsing import load_input


def build_parser(name: str, description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"{name}-evaluate",
        description=f"Evaluate {description.lower()} states from timestamped OHLC bars.",
    )
    parser.add_argument("--config", required=True, help="Path to strategy YAML config")
    parser.add_argument("--input", required=True, help="Path to OHLC input JSON")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return parser


def run(name: str, argv: Sequence[str] | None = None) -> int:
    strategy = registry.get(name)
    args = build_parser(strategy.name, strategy.description).parse_args(argv)
    try:
        configs = strategy.load_config(args.config)
        data = load_input(args.input)
        result = {
            "as_of": iso_utc(data.as_of),
            "strategy": strategy.name,
            "setups": [strategy.evaluate_symbol(config, data) for config in configs],
        }
    except StrategyError as exc:
        error = {"error": {"code": "INVALID_INPUT", "message": str(exc)}}
        print(json.dumps(error), file=sys.stderr)
        return 2
    if args.pretty:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, separators=(",", ":")))
    return 0


def make_entrypoint(name: str) -> Callable[[Sequence[str] | None], int]:
    """Build the console-script callable for one strategy.

    Each strategy gets its own command so the invocation stays short. Register the
    result in `[project.scripts]` as `<name>-evaluate`.
    """

    def entrypoint(argv: Sequence[str] | None = None) -> int:
        return run(name, argv)

    return entrypoint


orb_evaluate = make_entrypoint("orb")
coinflip_evaluate = make_entrypoint("coinflip")


if __name__ == "__main__":
    raise SystemExit(orb_evaluate())
