from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .core.errors import StrategyError
from .core.models import InputData


@runtime_checkable
class Strategy(Protocol):
    """What a strategy must provide to be evaluated by the shared CLI.

    `load_config` turns a YAML path into one config object per configured symbol.
    `evaluate_symbol` turns bars into a JSON-serialisable state for one symbol, and
    must be a pure function of (config, data) so the same inputs always agree.
    """

    name: str
    description: str

    def load_config(self, path: str | Path) -> Sequence[Any]: ...

    def evaluate_symbol(self, config: Any, data: InputData) -> dict[str, Any]: ...


_REGISTRY: dict[str, Strategy] = {}


def register(strategy: Strategy) -> Strategy:
    if strategy.name in _REGISTRY:
        raise StrategyError(f"strategy already registered: {strategy.name}")
    _REGISTRY[strategy.name] = strategy
    return strategy


def get(name: str) -> Strategy:
    try:
        return _REGISTRY[name]
    except KeyError:
        available = ", ".join(names()) or "none"
        raise StrategyError(f"unknown strategy: {name!r} (available: {available})") from None


def names() -> list[str]:
    return sorted(_REGISTRY)
