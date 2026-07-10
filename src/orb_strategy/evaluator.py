from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from .models import Bar, Config, InputData, SymbolConfig


def _number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral() else float(value)


def _range_payload(high: Decimal, low: Decimal) -> dict[str, int | float]:
    return {"high": _number(high), "low": _number(low), "size": _number(high - low)}


def _true_range_atr(
    bars: tuple[Bar, ...], period: int, session_open: datetime
) -> Decimal | None:
    completed = sorted(
        (bar for bar in bars if bar.time + timedelta(days=1) <= session_open),
        key=lambda bar: bar.time,
    )
    if len(completed) < period + 1:
        return None
    sample = completed[-(period + 1) :]
    ranges: list[Decimal] = []
    for previous, current in zip(sample, sample[1:]):
        ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    atr = sum(ranges, Decimal(0)) / Decimal(period)
    return atr if atr > 0 else None


def _base(symbol: str, state: str, session_open: datetime, reason: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "state": state,
        "reason": reason,
        "session_open": session_open.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }


def evaluate_symbol(config: SymbolConfig, data: InputData) -> dict[str, Any]:
    zone = ZoneInfo(config.timezone)
    local_as_of = data.as_of.astimezone(zone)
    local_open = datetime.combine(local_as_of.date(), config.session_open, tzinfo=zone)
    session_open = local_open.astimezone(UTC)
    as_of = data.as_of.astimezone(UTC)
    range_end = session_open + timedelta(minutes=config.range_minutes)
    deadline = session_open + timedelta(minutes=config.entry_window_minutes)

    if as_of < session_open:
        return _base(config.symbol, "none", session_open, "session_not_open")

    bars = tuple(sorted(data.bars.get(config.symbol, ()), key=lambda bar: bar.time))
    step = timedelta(minutes=config.bar_minutes)
    complete = tuple(bar for bar in bars if bar.time + step <= as_of)
    expected_times = {
        session_open + index * step for index in range(config.range_minutes // config.bar_minutes)
    }
    range_bars = tuple(bar for bar in complete if bar.time in expected_times)

    partial = tuple(bar for bar in range_bars if session_open <= bar.time < range_end)
    if len(range_bars) != len(expected_times):
        if as_of < range_end:
            result = _base(config.symbol, "building", session_open, "opening_range_in_progress")
            if partial:
                result["range"] = _range_payload(
                    max(bar.high for bar in partial), min(bar.low for bar in partial)
                )
            return result
        missing = sorted(expected_times - {bar.time for bar in range_bars})
        result = _base(config.symbol, "invalidated", session_open, "opening_range_incomplete")
        result["missing_bars"] = [
            value.isoformat().replace("+00:00", "Z") for value in missing
        ]
        return result

    high = max(bar.high for bar in range_bars)
    low = min(bar.low for bar in range_bars)
    result_range = _range_payload(high, low)

    daily_atr = _true_range_atr(
        data.daily_bars.get(config.symbol, ()), config.atr.period, session_open
    )
    filter_payload: dict[str, Any] = {
        "atr_period": config.atr.period,
        "daily_atr": _number(daily_atr) if daily_atr is not None else None,
        "range_atr": _number((high - low) / daily_atr) if daily_atr else None,
    }
    needs_atr = config.atr.minimum is not None or config.atr.maximum is not None
    if needs_atr and daily_atr is None:
        result = _base(config.symbol, "invalidated", session_open, "atr_unavailable")
        result.update({"range": result_range, "filters": filter_payload})
        return result
    if daily_atr:
        ratio = (high - low) / daily_atr
        if config.atr.minimum is not None and ratio < config.atr.minimum:
            result = _base(config.symbol, "invalidated", session_open, "range_below_atr_min")
            result.update({"range": result_range, "filters": filter_payload})
            return result
        if config.atr.maximum is not None and ratio > config.atr.maximum:
            result = _base(config.symbol, "invalidated", session_open, "range_above_atr_max")
            result.update({"range": result_range, "filters": filter_payload})
            return result

    observed_until = min(as_of, deadline)
    expected_entry_times: set[datetime] = set()
    candidate_time = range_end
    while candidate_time + step <= observed_until:
        expected_entry_times.add(candidate_time)
        candidate_time += step
    entry_bars = tuple(bar for bar in complete if bar.time in expected_entry_times)
    missing_entry = sorted(expected_entry_times - {bar.time for bar in entry_bars})
    if missing_entry:
        result = _base(config.symbol, "invalidated", session_open, "entry_bars_incomplete")
        result.update(
            {
                "range": result_range,
                "filters": filter_payload,
                "missing_bars": [
                    value.isoformat().replace("+00:00", "Z") for value in missing_entry
                ],
            }
        )
        return result

    candidates = iter(entry_bars)
    for bar in candidates:
        if bar.close > high + config.buffer_points:
            risk = bar.close - low
            signal = {
                "direction": "long",
                "trigger_time": (bar.time + step).astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "entry": _number(bar.close),
                "stop": _number(low),
                "risk_points": _number(risk),
                "targets": {
                    f"{_number(target)}R": _number(bar.close + risk * target)
                    for target in config.targets_r
                },
            }
            result = _base(config.symbol, "breakout_long", session_open, "first_close_above_range")
            result.update({"range": result_range, "filters": filter_payload, "signal": signal})
            return result
        if bar.close < low - config.buffer_points:
            risk = high - bar.close
            signal = {
                "direction": "short",
                "trigger_time": (bar.time + step).astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "entry": _number(bar.close),
                "stop": _number(high),
                "risk_points": _number(risk),
                "targets": {
                    f"{_number(target)}R": _number(bar.close - risk * target)
                    for target in config.targets_r
                },
            }
            result = _base(config.symbol, "breakout_short", session_open, "first_close_below_range")
            result.update({"range": result_range, "filters": filter_payload, "signal": signal})
            return result

    state = "invalidated" if as_of >= deadline else "armed"
    reason = "entry_window_expired" if state == "invalidated" else "waiting_for_close"
    result = _base(config.symbol, state, session_open, reason)
    result.update({"range": result_range, "filters": filter_payload})
    return result


def evaluate(config: Config, data: InputData) -> dict[str, Any]:
    return {
        "as_of": data.as_of.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "setups": [evaluate_symbol(symbol, data) for symbol in config.symbols],
    }
