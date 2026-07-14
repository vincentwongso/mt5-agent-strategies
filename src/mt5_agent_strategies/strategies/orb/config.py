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
    optional_decimal,
    positive_int,
    timezone_name,
)


@dataclass(frozen=True)
class AtrFilters:
    period: int = 5
    minimum: Decimal | None = None
    maximum: Decimal | None = None


@dataclass(frozen=True)
class ActivityFilters:
    """Opening-range relative-volume gate.

    `minimum` is the relative volume (opening-range tick volume over the mean of the
    same window across the prior `lookback` sessions) required to arm the range. None
    disables the gate. The documented conditioning effect (Zarattini & Aziz 2024) is
    US-equities evidence; the threshold is a prior to verify, not a measured edge.
    """

    minimum: Decimal | None = None
    lookback: int = 10


@dataclass(frozen=True)
class OrbConfig:
    symbol: str
    timezone: str
    session_open: time
    range_minutes: int
    entry_window_minutes: int
    bar_minutes: int
    buffer_points: Decimal
    targets_r: tuple[Decimal, ...]
    atr: AtrFilters
    activity: ActivityFilters = ActivityFilters()


def _atr_filters(filters: dict[str, Any]) -> AtrFilters:
    atr = AtrFilters(
        period=positive_int(filters.get("atr_period", 5), "filters.atr_period"),
        minimum=optional_decimal(filters.get("min_range_atr"), "filters.min_range_atr"),
        maximum=optional_decimal(filters.get("max_range_atr"), "filters.max_range_atr"),
    )
    if atr.minimum is not None and atr.minimum < 0:
        raise StrategyError("filters.min_range_atr cannot be negative")
    if atr.maximum is not None and atr.maximum <= 0:
        raise StrategyError("filters.max_range_atr must be positive")
    if atr.minimum is not None and atr.maximum is not None and atr.minimum > atr.maximum:
        raise StrategyError("filters.min_range_atr cannot exceed max_range_atr")
    return atr


def _activity_filters(filters: dict[str, Any]) -> ActivityFilters:
    activity = ActivityFilters(
        minimum=optional_decimal(filters.get("min_relative_volume"), "filters.min_relative_volume"),
        lookback=positive_int(
            filters.get("relative_volume_lookback", 10), "filters.relative_volume_lookback"
        ),
    )
    if activity.minimum is not None and activity.minimum <= 0:
        raise StrategyError("filters.min_relative_volume must be positive")
    return activity


def _targets(settings: dict[str, Any], symbol: str) -> tuple[Decimal, ...]:
    raw = settings.get("targets_r", [1, 2])
    if not isinstance(raw, list) or not raw:
        raise StrategyError(f"symbols.{symbol}.targets_r must be a non-empty list")
    targets = tuple(decimal(value, f"symbols.{symbol}.targets_r") for value in raw)
    if any(value <= 0 for value in targets):
        raise StrategyError(f"symbols.{symbol}.targets_r values must be positive")
    return targets


def build(symbol: str, settings: dict[str, Any]) -> OrbConfig:
    config = OrbConfig(
        symbol=symbol,
        timezone=timezone_name(settings.get("timezone"), f"symbols.{symbol}.timezone"),
        session_open=clock(settings.get("session_open"), f"symbols.{symbol}.session_open"),
        range_minutes=positive_int(settings.get("range_minutes", 15), "range_minutes"),
        entry_window_minutes=positive_int(
            settings.get("entry_window_minutes", 120), "entry_window_minutes"
        ),
        bar_minutes=positive_int(settings.get("bar_minutes", 5), "bar_minutes"),
        buffer_points=decimal(settings.get("buffer_points", 0), "buffer_points"),
        targets_r=_targets(settings, symbol),
        atr=_atr_filters(settings.get("filters", {})),
        activity=_activity_filters(settings.get("filters", {})),
    )
    if config.buffer_points < 0:
        raise StrategyError("buffer_points cannot be negative")
    if config.range_minutes % config.bar_minutes:
        raise StrategyError("range_minutes must be divisible by bar_minutes")
    if config.entry_window_minutes <= config.range_minutes:
        raise StrategyError("entry_window_minutes must be longer than range_minutes")
    return config


def load(path: str | Path) -> tuple[OrbConfig, ...]:
    settings = load_symbol_settings(path)
    return tuple(build(symbol, values) for symbol, values in settings.items())
