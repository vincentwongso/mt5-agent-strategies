from __future__ import annotations

import json
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from .errors import StrategyError
from .models import Bar, InputData


def mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StrategyError(f"{label} must be an object")
    return value


def positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise StrategyError(f"{label} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise StrategyError(f"{label} must be a positive integer") from exc
    if parsed <= 0 or parsed != value:
        raise StrategyError(f"{label} must be a positive integer")
    return parsed


def decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise StrategyError(f"{label} must be a decimal number")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise StrategyError(f"{label} must be a decimal number") from exc
    # NaN and Infinity parse cleanly but poison every comparison downstream, so a
    # glitched feed would otherwise surface as a silent state rather than an error.
    if not parsed.is_finite():
        raise StrategyError(f"{label} must be a finite number")
    return parsed


def optional_decimal(value: Any, label: str) -> Decimal | None:
    return None if value is None else decimal(value, label)


def timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise StrategyError(f"{label} must be an ISO 8601 string")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise StrategyError(f"{label} must be a valid ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StrategyError(f"{label} must include Z or a UTC offset")
    return parsed


def clock(value: Any, label: str) -> time:
    if not isinstance(value, str):
        raise StrategyError(f"{label} must use HH:MM")
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise StrategyError(f"{label} must use HH:MM") from exc
    if parsed.tzinfo is not None:
        raise StrategyError(f"{label} must be local wall time without an offset")
    return parsed


def timezone_name(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise StrategyError(f"{label} is required")
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise StrategyError(f"{label} is not an IANA timezone") from exc
    return value


def load_symbol_settings(path: str | Path) -> dict[str, dict[str, Any]]:
    """Read a strategy YAML config into per-symbol settings.

    `defaults` are shallow-merged under each symbol's overrides, except `filters`,
    which merges one level deeper so a symbol can override a single filter.
    Strategy-specific validation happens in the strategy's own config module.
    """
    try:
        raw = yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise StrategyError(f"cannot read config: {exc}") from exc

    root = mapping(raw, "config")
    defaults = mapping(root.get("defaults", {}), "defaults")
    symbols = mapping(root.get("symbols"), "symbols")
    if not symbols:
        raise StrategyError("symbols must contain at least one symbol")

    merged: dict[str, dict[str, Any]] = {}
    for symbol, overrides_raw in symbols.items():
        if not isinstance(symbol, str) or not symbol.strip():
            raise StrategyError("symbol names must be non-empty strings")
        overrides = mapping(overrides_raw, f"symbols.{symbol}")
        settings = {**defaults, **overrides}
        filters = {**mapping(defaults.get("filters", {}), "defaults.filters")}
        filters.update(mapping(overrides.get("filters", {}), f"symbols.{symbol}.filters"))
        settings["filters"] = filters
        merged[symbol] = settings
    return merged


def _parse_bar(raw: Any, label: str) -> Bar:
    item = mapping(raw, label)
    bar = Bar(
        time=timestamp(item.get("time"), f"{label}.time"),
        open=decimal(item.get("open"), f"{label}.open"),
        high=decimal(item.get("high"), f"{label}.high"),
        low=decimal(item.get("low"), f"{label}.low"),
        close=decimal(item.get("close"), f"{label}.close"),
    )
    if bar.low > bar.high:
        raise StrategyError(f"{label}.low cannot exceed high")
    if bar.low > min(bar.open, bar.close) or bar.high < max(bar.open, bar.close):
        raise StrategyError(f"{label} violates OHLC bounds")
    return bar


def _bar_map(raw: Any, label: str) -> dict[str, tuple[Bar, ...]]:
    result: dict[str, tuple[Bar, ...]] = {}
    for symbol, rows in mapping(raw, label).items():
        if not isinstance(rows, list):
            raise StrategyError(f"{label}.{symbol} must be an array")
        bars = tuple(
            _parse_bar(row, f"{label}.{symbol}[{index}]") for index, row in enumerate(rows)
        )
        timestamps = [bar.time for bar in bars]
        if len(timestamps) != len(set(timestamps)):
            raise StrategyError(f"{label}.{symbol} contains duplicate bar timestamps")
        result[str(symbol)] = bars
    return result


def load_input(path: str | Path) -> InputData:
    try:
        raw = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise StrategyError(f"cannot read input: {exc}") from exc
    root = mapping(raw, "input")
    return InputData(
        as_of=timestamp(root.get("as_of"), "as_of"),
        bars=_bar_map(root.get("bars"), "bars"),
        daily_bars=_bar_map(root.get("daily_bars", {}), "daily_bars"),
    )
