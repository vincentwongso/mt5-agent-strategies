from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Bar:
    """One OHLC bar. `time` is the bar's opening time and is timezone-aware."""

    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


@dataclass(frozen=True)
class InputData:
    """Bars for one evaluation, pinned to an explicit `as_of` instant."""

    as_of: datetime
    bars: dict[str, tuple[Bar, ...]]
    daily_bars: dict[str, tuple[Bar, ...]]
