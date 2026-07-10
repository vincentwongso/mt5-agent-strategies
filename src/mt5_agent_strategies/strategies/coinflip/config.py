from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from ...core.errors import StrategyError
from ...core.parsing import (
    clock,
    decimal,
    load_symbol_settings,
    mapping,
    positive_int,
    timezone_name,
)

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

# The user's own rule: never take a flip at worse than 1:1.5. It does not create an edge
# (see expectancy.py), but a config that silently allowed 1:0.5 would be worse still.
MIN_REWARD_RISK = Decimal("1.5")


@dataclass(frozen=True)
class CoinflipConfig:
    symbol: str
    timezone: str
    sessions: tuple[tuple[time, int], ...]
    skip_weekdays: frozenset[int]
    bar_minutes: int
    atr_period: int
    stop_atr_multiple: Decimal
    reward_risk: Decimal
    cost_points: Decimal


def _sessions(raw: Any, symbol: str) -> tuple[tuple[time, int], ...]:
    label = f"symbols.{symbol}.sessions"
    if not isinstance(raw, list) or not raw:
        raise StrategyError(f"{label} must be a non-empty list")
    parsed = []
    for index, item in enumerate(raw):
        window = mapping(item, f"{label}[{index}]")
        parsed.append(
            (
                clock(window.get("open"), f"{label}[{index}].open"),
                positive_int(window.get("minutes"), f"{label}[{index}].minutes"),
            )
        )
    return tuple(parsed)


def _skip_weekdays(raw: Any, symbol: str) -> frozenset[int]:
    label = f"symbols.{symbol}.skip_weekdays"
    if raw is None:
        return frozenset()
    if not isinstance(raw, list):
        raise StrategyError(f"{label} must be a list of weekday names")
    days = set()
    for value in raw:
        if not isinstance(value, str) or value.strip().lower() not in WEEKDAYS:
            raise StrategyError(f"{label} entries must be weekday names, got {value!r}")
        days.add(WEEKDAYS[value.strip().lower()])
    return frozenset(days)


def build(symbol: str, settings: dict[str, Any]) -> CoinflipConfig:
    reward_risk = decimal(settings.get("reward_risk", "1.5"), "reward_risk")
    if reward_risk < MIN_REWARD_RISK:
        raise StrategyError(f"reward_risk must be at least {MIN_REWARD_RISK}")

    stop_atr_multiple = decimal(settings.get("stop_atr_multiple", "0.5"), "stop_atr_multiple")
    if stop_atr_multiple <= 0:
        raise StrategyError("stop_atr_multiple must be positive")

    cost_points = decimal(settings.get("cost_points", 0), "cost_points")
    if cost_points < 0:
        raise StrategyError("cost_points cannot be negative")

    return CoinflipConfig(
        symbol=symbol,
        timezone=timezone_name(settings.get("timezone"), f"symbols.{symbol}.timezone"),
        sessions=_sessions(settings.get("sessions"), symbol),
        skip_weekdays=_skip_weekdays(settings.get("skip_weekdays"), symbol),
        bar_minutes=positive_int(settings.get("bar_minutes", 5), "bar_minutes"),
        atr_period=positive_int(settings.get("atr_period", 14), "atr_period"),
        stop_atr_multiple=stop_atr_multiple,
        reward_risk=reward_risk,
        cost_points=cost_points,
    )


def load(path: str | Path) -> tuple[CoinflipConfig, ...]:
    settings = load_symbol_settings(path)
    return tuple(build(symbol, values) for symbol, values in settings.items())
