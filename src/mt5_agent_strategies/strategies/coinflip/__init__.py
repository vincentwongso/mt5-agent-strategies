"""Coinflip: the null hypothesis.

A random direction with a fixed reward-to-risk, evaluated the same way a real strategy is.
It exists to be beaten. Any strategy that cannot out-perform this one, out of sample and
net of costs, has no edge — and this one has none by construction.
"""

from __future__ import annotations

from pathlib import Path

from ...core.models import InputData
from ...registry import register
from . import config as _config
from .config import CoinflipConfig
from .evaluator import evaluate_symbol, flip

__all__ = ["CoinflipConfig", "CoinflipStrategy", "STRATEGY", "evaluate_symbol", "flip"]


class CoinflipStrategy:
    name = "coinflip"
    description = "Coin flip null hypothesis"

    def load_config(self, path: str | Path) -> tuple[CoinflipConfig, ...]:
        return _config.load(path)

    def evaluate_symbol(self, config: CoinflipConfig, data: InputData) -> dict:
        return evaluate_symbol(config, data)


STRATEGY = register(CoinflipStrategy())
