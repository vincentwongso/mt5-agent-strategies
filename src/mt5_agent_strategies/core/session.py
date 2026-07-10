from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from .models import Bar


def session_open_utc(as_of: datetime, timezone: str, session_open: time) -> datetime:
    """Resolve today's session open, in UTC, for the local date `as_of` falls on.

    Anchoring to an IANA zone rather than a fixed UTC hour is what keeps the open
    correct across daylight-saving changes.

    Limitation: a `session_open` that lands inside a DST gap (a local wall time that
    never occurs) resolves to a shifted instant rather than raising. Real cash opens
    sit far from the 01:00-03:00 window where gaps happen, so this is left undefended.
    """
    zone = ZoneInfo(timezone)
    local_date = as_of.astimezone(zone).date()
    return datetime.combine(local_date, session_open, tzinfo=zone).astimezone(UTC)


def completed_bars(bars: tuple[Bar, ...], as_of: datetime, bar_minutes: int) -> tuple[Bar, ...]:
    """Bars that had closed by `as_of`, sorted. Excludes the in-progress bar."""
    step = timedelta(minutes=bar_minutes)
    return tuple(sorted((bar for bar in bars if bar.time + step <= as_of), key=lambda b: b.time))


def expected_bar_times(start: datetime, end: datetime, step: timedelta) -> list[datetime]:
    """Opening times of every bar that both starts at/after `start` and closes by `end`."""
    times: list[datetime] = []
    candidate = start
    while candidate + step <= end:
        times.append(candidate)
        candidate += step
    return times


def average_true_range(bars: Sequence[Bar], period: int) -> Decimal | None:
    """Average true range over the last `period` intervals of an already-sorted series.

    Needs `period + 1` bars, because each true range references the prior close.
    Returns None when there are too few bars, or when the range degenerates to zero.
    """
    if len(bars) < period + 1:
        return None
    sample = bars[-(period + 1) :]
    ranges = [
        max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        for previous, current in zip(sample, sample[1:])
    ]
    atr = sum(ranges, Decimal(0)) / Decimal(period)
    return atr if atr > 0 else None


def true_range_atr(bars: tuple[Bar, ...], period: int, before: datetime) -> Decimal | None:
    """Average true range over daily bars fully completed before `before`.

    Assumes daily bars are midnight-anchored in the feed's own timezone. Supply a
    couple of spare bars so a broker's server-time D1 anchor cannot starve the window.
    """
    completed = sorted(
        (bar for bar in bars if bar.time + timedelta(days=1) <= before),
        key=lambda bar: bar.time,
    )
    return average_true_range(completed, period)


def active_session(
    as_of: datetime, timezone: str, sessions: Sequence[tuple[time, int]]
) -> tuple[datetime, datetime] | None:
    """The (open, end) in UTC of whichever configured window contains `as_of`, if any."""
    for session_open, minutes in sessions:
        opened = session_open_utc(as_of, timezone, session_open)
        closes = opened + timedelta(minutes=minutes)
        if opened <= as_of < closes:
            return opened, closes
    return None


def local_weekday(as_of: datetime, timezone: str) -> int:
    """Weekday of `as_of` in the symbol's own timezone. Monday is 0."""
    return as_of.astimezone(ZoneInfo(timezone)).weekday()
