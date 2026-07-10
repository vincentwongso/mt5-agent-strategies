from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from ...core.format import iso_utc, number
from ...core.models import InputData
from ...core.session import active_session, average_true_range, completed_bars, local_weekday
from . import expectancy
from .config import CoinflipConfig

QUANTUM = Decimal("0.000001")


def _base(symbol: str, state: str, reason: str) -> dict[str, Any]:
    return {"symbol": symbol, "state": state, "reason": reason}


def _round(value: Decimal) -> int | float:
    return number(value.quantize(QUANTUM).normalize())


def flip(symbol: str, session_open: datetime, reward_risk: Decimal) -> str:
    """A coin whose result is a pure function of the session it belongs to.

    Python's `hash()` is salted per process, and a real RNG would break the repo's
    determinism contract outright. Hashing a canonical key gives one stable flip per
    symbol per session: re-evaluating five minutes later re-reads the same coin rather
    than tossing a new one.
    """
    key = f"{symbol}|{iso_utc(session_open)}|{reward_risk}"
    digest = hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest()
    return "long" if int.from_bytes(digest, "big") & 1 else "short"


def _cost_points(config: CoinflipConfig, data: InputData) -> tuple[Decimal, str]:
    """Live spread wins over the configured fallback. Spread is data, not configuration."""
    live = data.spreads.get(config.symbol)
    if live is not None:
        return live, "input"
    return config.cost_points, "config"


def _screening(config: CoinflipConfig, data: InputData) -> dict[str, Any]:
    """Volatility and cost, computable whenever there are enough bars.

    Emitted in every state, not only alongside a signal, so a watchlist can be ranked
    before any session opens. Rank ascending on `expectancy.cost_r`, never on spread.
    """
    bars = completed_bars(data.bars.get(config.symbol, ()), data.as_of, config.bar_minutes)
    atr = average_true_range(bars, config.atr_period)
    if atr is None:
        return {}

    entry = bars[-1].close
    stop_points = config.stop_atr_multiple * atr
    if stop_points <= 0:
        return {}

    cost_points, source = _cost_points(config, data)
    numbers = expectancy.summary(config.reward_risk, stop_points, cost_points)
    return {
        "volatility": {
            "atr_period": config.atr_period,
            "bar_minutes": config.bar_minutes,
            "atr_points": _round(atr),
            # Comparable across instruments; atr_points is not.
            "atr_percent_of_price": _round(atr / entry * Decimal(100)),
        },
        "expectancy": {
            "reward_risk": _round(numbers["reward_risk"]),
            "spread_points": _round(cost_points),
            "spread_source": source,
            "stop_points": _round(stop_points),
            "cost_r": _round(numbers["cost_r"]),
            "coin_win_rate": _round(numbers["coin_win_rate"]),
            "breakeven_win_rate": _round(numbers["breakeven_win_rate"]),
            "edge_required": _round(numbers["edge_required"]),
            "breakeven_achievable": numbers["breakeven_achievable"],
            "expected_value_r": _round(numbers["expected_value_r"]),
            "note": numbers["note"],
        },
        "_entry": entry,
        "_stop_points": stop_points,
    }


def evaluate_symbol(config: CoinflipConfig, data: InputData) -> dict[str, Any]:
    as_of = data.as_of.astimezone(UTC)
    screening = _screening(config, data)
    blocks = {key: value for key, value in screening.items() if not key.startswith("_")}

    if local_weekday(as_of, config.timezone) in config.skip_weekdays:
        return {**_base(config.symbol, "stand_down", "weekday_excluded"), **blocks}

    window = active_session(as_of, config.timezone, config.sessions)
    if window is None:
        return {**_base(config.symbol, "none", "outside_session"), **blocks}
    session_open, session_close = window

    if not screening:
        bars = completed_bars(data.bars.get(config.symbol, ()), as_of, config.bar_minutes)
        result = _base(config.symbol, "invalidated", "insufficient_bars")
        result["required_bars"] = config.atr_period + 1
        result["completed_bars"] = len(bars)
        return result

    entry: Decimal = screening["_entry"]
    stop_points: Decimal = screening["_stop_points"]
    direction = flip(config.symbol, session_open, config.reward_risk)
    sign = Decimal(1) if direction == "long" else Decimal(-1)
    target_points = stop_points * config.reward_risk

    result = _base(config.symbol, f"signal_{direction}", "coin_flip")
    result.update(
        {
            "session_open": iso_utc(session_open),
            "session_close": iso_utc(session_close),
            **blocks,
            "signal": {
                "direction": direction,
                "entry": _round(entry),
                "stop": _round(entry - sign * stop_points),
                "target": _round(entry + sign * target_points),
                "risk_points": _round(stop_points),
                "reward_points": _round(target_points),
            },
        }
    )
    return result
