from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from ...core.format import iso_utc, number
from ...core.models import Bar, InputData
from ...core.session import (
    completed_bars,
    expected_bar_times,
    session_open_utc,
    true_range_atr,
)
from .config import OrbConfig


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

    def invalid(reason: str, **extra: Any) -> dict[str, Any]:
        result = _base(config.symbol, "invalidated", session_open, reason)
        result.update({"range": range_payload, "filters": filters, **extra})
        return result

    if (config.atr.minimum is not None or config.atr.maximum is not None) and daily_atr is None:
        return invalid("atr_unavailable")
    if daily_atr:
        ratio = (high - low) / daily_atr
        if config.atr.minimum is not None and ratio < config.atr.minimum:
            return invalid("range_below_atr_min")
        if config.atr.maximum is not None and ratio > config.atr.maximum:
            return invalid("range_above_atr_max")

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
                    "signal": _signal("short", bar, step, high, config.targets_r),
                }
            )
            return result

    if as_of >= deadline:
        return invalid("entry_window_expired")
    result = _base(config.symbol, "armed", session_open, "waiting_for_close")
    result.update({"range": range_payload, "filters": filters})
    return result
