"""Open range breakout: the directional break of a session's opening range."""

from __future__ import annotations

from pathlib import Path

from ...core.models import InputData
from ...registry import register
from . import config as _config
from .config import ActivityFilters, AtrFilters, OrbConfig
from .evaluator import evaluate_symbol


class OrbStrategy:
    name = "orb"
    description = "Open range breakout"

    def load_config(self, path: str | Path) -> tuple[OrbConfig, ...]:
        return _config.load(path)

    def evaluate_symbol(self, config: OrbConfig, data: InputData) -> dict:
        return evaluate_symbol(config, data)


STRATEGY = register(OrbStrategy())

__all__ = [
    "ActivityFilters",
    "AtrFilters",
    "OrbConfig",
    "OrbStrategy",
    "STRATEGY",
    "evaluate_symbol",
]
