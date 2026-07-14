from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from ...core.format import iso_utc, number
from ...core.models import Bar, InputData
from ...core.session import (
    completed_bars,
    expected_bar_times,
    session_open_utc,
    true_range_atr,
)
from .config import OrbConfig

QUANTUM = Decimal("0.000001")


def _base(symbol: str, state: str, session_open: datetime, reason: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "state": state,
        "reason": reason,
        "session_open": iso_utc(session_open),
    }


def _range_payload(high: Decimal, low: Decimal) -> dict[str, int | float]:
    return {"high": number(high), "low": number(low), "size": number(high - low)}


def _signal(
    direction: str, bar: Bar, step: timedelta, stop: Decimal, targets_r: tuple[Decimal, ...]
) -> dict[str, Any]:
    risk = abs(bar.close - stop)
    sign = 1 if direction == "long" else -1
    return {
        "direction": direction,
        "trigger_time": iso_utc(bar.time + step),
        "entry": number(bar.close),
        "stop": number(stop),
        "risk_points": number(risk),
        "targets": {
            f"{number(target)}R": number(bar.close + sign * risk * target) for target in targets_r
        },
    }


def _window_volume(
    by_time: dict[datetime, Bar], opened: datetime, minutes: int, step: timedelta
) -> Decimal | None:
    """Total tick volume of one session-open window, or None unless every bar of the
    window is present and carries volume. Partial windows never contribute."""
    bars = [
        by_time.get(when)
        for when in expected_bar_times(opened, opened + timedelta(minutes=minutes), step)
    ]
    if any(bar is None or bar.tick_volume is None for bar in bars):
        return None
    return sum((bar.tick_volume for bar in bars), Decimal(0))


def _activity(
    config: OrbConfig,
    by_time: dict[datetime, Bar],
    session_open: datetime,
    range_bars: list[Bar],
    step: timedelta,
) -> tuple[dict[str, Any], Decimal | None]:
    """Relative volume of today's opening range against the same window on the prior
    `lookback` sessions, walking back local calendar days so DST is handled by
    construction and days without a complete window (weekends, holidays, gaps) simply
    do not count. Returns (payload, relative_volume); relative_volume is None whenever
    the ratio cannot be computed honestly — the caller fails closed on it.
    """
    payload: dict[str, Any] = {
        "threshold": number(config.activity.minimum),
        "lookback_sessions": config.activity.lookback,
        "or_volume": None,
        "baseline_volume": None,
        "relative_volume": None,
    }
    if any(bar.tick_volume is None for bar in range_bars):
        return payload, None
    or_volume = sum((bar.tick_volume for bar in range_bars), Decimal(0))
    payload["or_volume"] = number(or_volume)

    zone = ZoneInfo(config.timezone)
    earliest = min(by_time).astimezone(zone).date()
    day = session_open.astimezone(zone).date() - timedelta(days=1)
    volumes: list[Decimal] = []
    while day >= earliest and len(volumes) < config.activity.lookback:
        opened = datetime.combine(day, config.session_open, tzinfo=zone).astimezone(UTC)
        volume = _window_volume(by_time, opened, config.range_minutes, step)
        if volume is not None:
            volumes.append(volume)
        day -= timedelta(days=1)

    if len(volumes) < config.activity.lookback:
        return payload, None
    baseline = sum(volumes, Decimal(0)) / Decimal(config.activity.lookback)
    if baseline <= 0:
        # A zero baseline makes the ratio meaningless; degenerate data fails closed.
        return payload, None
    payload["baseline_volume"] = number(baseline.quantize(QUANTUM).normalize())
    relative = or_volume / baseline
    payload["relative_volume"] = number(relative.quantize(QUANTUM).normalize())
    return payload, relative


def evaluate_symbol(config: OrbConfig, data: InputData) -> dict[str, Any]:
    as_of = data.as_of.astimezone(UTC)
    session_open = session_open_utc(as_of, config.timezone, config.session_open)
    step = timedelta(minutes=config.bar_minutes)
    range_end = session_open + timedelta(minutes=config.range_minutes)
    deadline = session_open + timedelta(minutes=config.entry_window_minutes)

    if as_of < session_open:
        return _base(config.symbol, "none", session_open, "session_not_open")

    bars = completed_bars(data.bars.get(config.symbol, ()), as_of, config.bar_minutes)
    by_time = {bar.time: bar for bar in bars}

    range_times = expected_bar_times(session_open, range_end, step)
    range_bars = [by_time[when] for when in range_times if when in by_time]
    if len(range_bars) != len(range_times):
        if as_of < range_end:
            result = _base(config.symbol, "building", session_open, "opening_range_in_progress")
            if range_bars:
                result["range"] = _range_payload(
                    max(bar.high for bar in range_bars), min(bar.low for bar in range_bars)
                )
            return result
        result = _base(config.symbol, "invalidated", session_open, "opening_range_incomplete")
        result["missing_bars"] = [iso_utc(when) for when in range_times if when not in by_time]
        return result

    high = max(bar.high for bar in range_bars)
    low = min(bar.low for bar in range_bars)
    range_payload = _range_payload(high, low)

    daily_atr = true_range_atr(
        data.daily_bars.get(config.symbol, ()), config.atr.period, session_open
    )
    filters: dict[str, Any] = {
        "atr_period": config.atr.period,
        "daily_atr": number(daily_atr) if daily_atr is not None else None,
        "range_atr": number((high - low) / daily_atr) if daily_atr else None,
    }

    extras: dict[str, Any] = {}

    def invalid(reason: str, **extra: Any) -> dict[str, Any]:
        result = _base(config.symbol, "invalidated", session_open, reason)
        result.update({"range": range_payload, "filters": filters, **extras, **extra})
        return result

    if (config.atr.minimum is not None or config.atr.maximum is not None) and daily_atr is None:
        return invalid("atr_unavailable")
    if daily_atr:
        ratio = (high - low) / daily_atr
        if config.atr.minimum is not None and ratio < config.atr.minimum:
            return invalid("range_below_atr_min")
        if config.atr.maximum is not None and ratio > config.atr.maximum:
            return invalid("range_above_atr_max")

    if config.activity.minimum is not None:
        activity, relative = _activity(config, by_time, session_open, range_bars, step)
        extras["activity"] = activity
        if relative is None:
            return invalid("insufficient_volume_history")
        if relative < config.activity.minimum:
            # Standing down on a quiet open is the gate doing its job, not an error.
            return invalid("opening_activity_below_threshold")

    # Walk the entry window in order and stop at the first decision. A bar missing
    # *before* any break makes the first break undecidable, so it fails closed; a gap
    # *after* a confirmed break cannot unmake it, and is never reached.
    for when in expected_bar_times(range_end, min(as_of, deadline), step):
        bar = by_time.get(when)
        if bar is None:
            return invalid("entry_bars_incomplete", missing_bars=[iso_utc(when)])
        if bar.close > high + config.buffer_points:
            result = _base(config.symbol, "breakout_long", session_open, "first_close_above_range")
            result.update(
                {
                    "range": range_payload,
                    "filters": filters,
                    **extras,
                    "signal": _signal("long", bar, step, low, config.targets_r),
                }
            )
            return result
        if bar.close < low - config.buffer_points:
            result = _base(config.symbol, "breakout_short", session_open, "first_close_below_range")
            result.update(
                {
                    "range": range_payload,
                    "filters": filters,
                    **extras,
                    "signal": _signal("short", bar, step, high, config.targets_r),
                }
            )
            return result

    if as_of >= deadline:
        return invalid("entry_window_expired")
    result = _base(config.symbol, "armed", session_open, "waiting_for_close")
    result.update({"range": range_payload, "filters": filters, **extras})
    return result
