from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal


@dataclass(frozen=True)
class AtrFilters:
    period: int = 5
    minimum: Decimal | None = None
    maximum: Decimal | None = None


@dataclass(frozen=True)
class SymbolConfig:
    symbol: str
    timezone: str
    session_open: time
    range_minutes: int
    entry_window_minutes: int
    bar_minutes: int
    buffer_points: Decimal
    targets_r: tuple[Decimal, ...]
    atr: AtrFilters


@dataclass(frozen=True)
class Config:
    symbols: tuple[SymbolConfig, ...]


@dataclass(frozen=True)
class Bar:
    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


@dataclass(frozen=True)
class InputData:
    as_of: datetime
    bars: dict[str, tuple[Bar, ...]]
    daily_bars: dict[str, tuple[Bar, ...]]

