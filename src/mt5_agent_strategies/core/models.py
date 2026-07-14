from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Bar:
    """One OHLC bar. `time` is the bar's opening time and is timezone-aware.

    `tick_volume` is optional because most evaluations don't need it; a strategy that
    does (e.g. the ORB activity gate) must fail closed when it is absent, never guess.
    """

    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    tick_volume: Decimal | None = None


@dataclass(frozen=True)
class InputData:
    """Bars for one evaluation, pinned to an explicit `as_of` instant.

    `spreads` carries the live spread per symbol, in the instrument's points. It belongs in
    the input rather than in config because it changes minute to minute; a spread written
    into a YAML file is stale the moment it is saved.
    """

    as_of: datetime
    bars: dict[str, tuple[Bar, ...]]
    daily_bars: dict[str, tuple[Bar, ...]]
    spreads: dict[str, Decimal] = field(default_factory=dict)
