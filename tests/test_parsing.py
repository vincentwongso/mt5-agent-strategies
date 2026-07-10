import json

import pytest

from mt5_agent_strategies.core.errors import StrategyError
from mt5_agent_strategies.core.parsing import load_input
from mt5_agent_strategies.strategies.orb import config as orb_config

EXAMPLE = "skills/orb-strategy/config.example.yaml"


def test_example_config_loads():
    configs = orb_config.load(EXAMPLE)
    assert [item.symbol for item in configs] == ["GER40", "US30"]
    assert configs[0].timezone == "Europe/London"
    assert configs[1].timezone == "America/New_York"


def test_symbol_overrides_a_single_filter(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "defaults:\n"
        "  timezone: Europe/London\n"
        "  session_open: '08:00'\n"
        "  filters:\n"
        "    atr_period: 5\n"
        "    max_range_atr: 0.5\n"
        "symbols:\n"
        "  GER40: {}\n"
        "  US30:\n"
        "    filters:\n"
        "      max_range_atr: 0.8\n"
    )
    ger40, us30 = orb_config.load(path)
    assert ger40.atr.period == 5 and float(ger40.atr.maximum) == 0.5
    assert us30.atr.period == 5 and float(us30.atr.maximum) == 0.8


def test_config_rejects_range_not_divisible_by_bar(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "defaults:\n"
        "  timezone: Europe/London\n"
        "  session_open: '08:00'\n"
        "  range_minutes: 14\n"
        "  bar_minutes: 5\n"
        "symbols:\n"
        "  GER40: {}\n"
    )
    with pytest.raises(StrategyError, match="divisible by bar_minutes"):
        orb_config.load(path)


def test_config_rejects_unknown_timezone(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("symbols:\n  GER40:\n    timezone: Mars/Olympus\n    session_open: '08:00'\n")
    with pytest.raises(StrategyError, match="not an IANA timezone"):
        orb_config.load(path)


def test_input_rejects_naive_timestamp(tmp_path):
    path = tmp_path / "input.json"
    path.write_text(json.dumps({"as_of": "2026-07-10T07:00:00", "bars": {}}))
    with pytest.raises(StrategyError, match="must include Z or a UTC offset"):
        load_input(path)


def test_input_rejects_duplicate_bars(tmp_path):
    row = {"time": "2026-07-10T07:00:00Z", "open": 1, "high": 2, "low": 0, "close": 1}
    path = tmp_path / "input.json"
    path.write_text(json.dumps({"as_of": "2026-07-10T08:00:00Z", "bars": {"X": [row, row]}}))
    with pytest.raises(StrategyError, match="duplicate bar timestamps"):
        load_input(path)


def test_input_rejects_bar_violating_ohlc_bounds(tmp_path):
    row = {"time": "2026-07-10T07:00:00Z", "open": 5, "high": 4, "low": 3, "close": 3}
    path = tmp_path / "input.json"
    path.write_text(json.dumps({"as_of": "2026-07-10T08:00:00Z", "bars": {"X": [row]}}))
    with pytest.raises(StrategyError, match="violates OHLC bounds"):
        load_input(path)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_input_rejects_non_finite_prices(tmp_path, value):
    """A broker feed glitch must fail as INVALID_INPUT, never poison the arithmetic."""
    row = {"time": "2026-07-10T07:00:00Z", "open": 1, "high": value, "low": 0, "close": 1}
    path = tmp_path / "input.json"
    path.write_text(json.dumps({"as_of": "2026-07-10T08:00:00Z", "bars": {"X": [row]}}))
    with pytest.raises(StrategyError, match="must be a finite number"):
        load_input(path)
