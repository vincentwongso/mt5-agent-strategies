import json

from mt5_agent_strategies.cli import orb_evaluate

CONFIG = "skills/orb-strategy/config.example.yaml"
FIXTURE = "tests/fixtures/breakout-long.json"


def test_cli_emits_breakout(capsys):
    code = orb_evaluate(["--config", CONFIG, "--input", FIXTURE])
    result = json.loads(capsys.readouterr().out)
    assert code == 0
    assert result["strategy"] == "orb"
    assert result["setups"][0]["state"] == "breakout_long"
    assert result["setups"][0]["signal"]["entry"] == 18252.5
    assert result["setups"][0]["signal"]["targets"] == {"1R": 18295, "2R": 18337.5}
    assert result["setups"][1]["state"] == "none"


def test_cli_reports_invalid_input_on_stderr(capsys):
    code = orb_evaluate(["--config", CONFIG, "--input", "tests/fixtures/does-not-exist.json"])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "INVALID_INPUT"


def test_cli_rejects_non_finite_price_without_traceback(capsys, tmp_path):
    bars = [
        {"time": "2026-07-10T07:00:00Z", "open": 1, "high": "Infinity", "low": 0, "close": 1},
    ]
    path = tmp_path / "input.json"
    path.write_text(json.dumps({"as_of": "2026-07-10T07:30:00Z", "bars": {"GER40": bars}}))
    code = orb_evaluate(["--config", CONFIG, "--input", str(path)])
    captured = capsys.readouterr()
    assert code == 2
    assert json.loads(captured.err)["error"]["code"] == "INVALID_INPUT"
