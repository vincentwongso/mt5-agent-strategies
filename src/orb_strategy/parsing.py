from __future__ import annotations

import json
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from .errors import OrbError
from .models import AtrFilters, Bar, Config, InputData, SymbolConfig


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OrbError(f"{label} must be an object")
    return value


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise OrbError(f"{label} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise OrbError(f"{label} must be a positive integer") from exc
    if parsed <= 0 or parsed != value:
        raise OrbError(f"{label} must be a positive integer")
    return parsed


def _decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise OrbError(f"{label} must be a decimal number")
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise OrbError(f"{label} must be a decimal number") from exc


def _optional_decimal(value: Any, label: str) -> Decimal | None:
    return None if value is None else _decimal(value, label)


def _timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise OrbError(f"{label} must be an ISO 8601 string")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise OrbError(f"{label} must be a valid ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OrbError(f"{label} must include Z or a UTC offset")
    return parsed


def _clock(value: Any, label: str) -> time:
    if not isinstance(value, str):
        raise OrbError(f"{label} must use HH:MM")
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise OrbError(f"{label} must use HH:MM") from exc
    if parsed.tzinfo is not None:
        raise OrbError(f"{label} must be local wall time without an offset")
    return parsed


def load_config(path: str | Path) -> Config:
    try:
        raw = yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise OrbError(f"cannot read config: {exc}") from exc
    root = _mapping(raw, "config")
    defaults = _mapping(root.get("defaults", {}), "defaults")
    symbols = _mapping(root.get("symbols"), "symbols")
    if not symbols:
        raise OrbError("symbols must contain at least one symbol")

    configs: list[SymbolConfig] = []
    for symbol, symbol_raw in symbols.items():
        if not isinstance(symbol, str) or not symbol.strip():
            raise OrbError("symbol names must be non-empty strings")
        overrides = _mapping(symbol_raw, f"symbols.{symbol}")
        merged = {**defaults, **overrides}
        filters = {**_mapping(defaults.get("filters", {}), "defaults.filters")}
        filters.update(_mapping(overrides.get("filters", {}), f"symbols.{symbol}.filters"))

        timezone_name = merged.get("timezone")
        if not isinstance(timezone_name, str):
            raise OrbError(f"symbols.{symbol}.timezone is required")
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise OrbError(f"symbols.{symbol}.timezone is not an IANA timezone") from exc

        targets_raw = merged.get("targets_r", [1, 2])
        if not isinstance(targets_raw, list) or not targets_raw:
            raise OrbError(f"symbols.{symbol}.targets_r must be a non-empty list")
        targets = tuple(
            _decimal(value, f"symbols.{symbol}.targets_r") for value in targets_raw
        )
        if any(value <= 0 for value in targets):
            raise OrbError(f"symbols.{symbol}.targets_r values must be positive")

        atr = AtrFilters(
            period=_positive_int(filters.get("atr_period", 5), "filters.atr_period"),
            minimum=_optional_decimal(filters.get("min_range_atr"), "filters.min_range_atr"),
            maximum=_optional_decimal(filters.get("max_range_atr"), "filters.max_range_atr"),
        )
        if atr.minimum is not None and atr.minimum < 0:
            raise OrbError("filters.min_range_atr cannot be negative")
        if atr.maximum is not None and atr.maximum <= 0:
            raise OrbError("filters.max_range_atr must be positive")
        if atr.minimum is not None and atr.maximum is not None and atr.minimum > atr.maximum:
            raise OrbError("filters.min_range_atr cannot exceed max_range_atr")

        config = SymbolConfig(
            symbol=symbol,
            timezone=timezone_name,
            session_open=_clock(merged.get("session_open"), f"symbols.{symbol}.session_open"),
            range_minutes=_positive_int(merged.get("range_minutes", 15), "range_minutes"),
            entry_window_minutes=_positive_int(
                merged.get("entry_window_minutes", 120), "entry_window_minutes"
            ),
            bar_minutes=_positive_int(merged.get("bar_minutes", 5), "bar_minutes"),
            buffer_points=_decimal(merged.get("buffer_points", 0), "buffer_points"),
            targets_r=targets,
            atr=atr,
        )
        if config.buffer_points < 0:
            raise OrbError("buffer_points cannot be negative")
        if config.range_minutes % config.bar_minutes:
            raise OrbError("range_minutes must be divisible by bar_minutes")
        if config.entry_window_minutes <= config.range_minutes:
            raise OrbError("entry_window_minutes must be longer than range_minutes")
        configs.append(config)
    return Config(symbols=tuple(configs))


def _parse_bar(raw: Any, label: str) -> Bar:
    item = _mapping(raw, label)
    bar = Bar(
        time=_timestamp(item.get("time"), f"{label}.time"),
        open=_decimal(item.get("open"), f"{label}.open"),
        high=_decimal(item.get("high"), f"{label}.high"),
        low=_decimal(item.get("low"), f"{label}.low"),
        close=_decimal(item.get("close"), f"{label}.close"),
    )
    if bar.low > min(bar.open, bar.close) or bar.high < max(bar.open, bar.close):
        raise OrbError(f"{label} violates OHLC bounds")
    if bar.low > bar.high:
        raise OrbError(f"{label}.low cannot exceed high")
    return bar


def _bar_map(raw: Any, label: str) -> dict[str, tuple[Bar, ...]]:
    mapping = _mapping(raw, label)
    result: dict[str, tuple[Bar, ...]] = {}
    for symbol, rows in mapping.items():
        if not isinstance(rows, list):
            raise OrbError(f"{label}.{symbol} must be an array")
        bars = tuple(_parse_bar(row, f"{label}.{symbol}[{index}]") for index, row in enumerate(rows))
        timestamps = [bar.time for bar in bars]
        if len(timestamps) != len(set(timestamps)):
            raise OrbError(f"{label}.{symbol} contains duplicate bar timestamps")
        result[str(symbol)] = bars
    return result


def load_input(path: str | Path) -> InputData:
    try:
        raw = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise OrbError(f"cannot read input: {exc}") from exc
    root = _mapping(raw, "input")
    return InputData(
        as_of=_timestamp(root.get("as_of"), "as_of"),
        bars=_bar_map(root.get("bars"), "bars"),
        daily_bars=_bar_map(root.get("daily_bars", {}), "daily_bars"),
    )

