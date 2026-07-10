import json

import pytest

from orb_strategy.errors import OrbError
from orb_strategy.parsing import load_config, load_input


def test_example_config_loads():
    config = load_config("skills/orb-strategy/config.example.yaml")
    assert [item.symbol for item in config.symbols] == ["GER40", "US30"]
    assert config.symbols[0].timezone == "Europe/London"
    assert config.symbols[1].timezone == "America/New_York"


def test_input_rejects_naive_timestamp(tmp_path):
    path = tmp_path / "input.json"
    path.write_text(json.dumps({"as_of": "2026-07-10T07:00:00", "bars": {}}))
    with pytest.raises(OrbError, match="must include Z or a UTC offset"):
        load_input(path)


def test_input_rejects_duplicate_bars(tmp_path):
    row = {"time": "2026-07-10T07:00:00Z", "open": 1, "high": 2, "low": 0, "close": 1}
    path = tmp_path / "input.json"
    path.write_text(json.dumps({"as_of": "2026-07-10T08:00:00Z", "bars": {"X": [row, row]}}))
    with pytest.raises(OrbError, match="duplicate bar timestamps"):
        load_input(path)

