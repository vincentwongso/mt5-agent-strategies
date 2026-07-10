import json

from orb_strategy.cli import main


def test_cli_emits_breakout(capsys):
    code = main(
        [
            "--config",
            "skills/orb-strategy/config.example.yaml",
            "--input",
            "tests/fixtures/breakout-long.json",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert code == 0
    assert result["setups"][0]["state"] == "breakout_long"
    assert result["setups"][0]["signal"]["entry"] == 18252.5
    assert result["setups"][0]["signal"]["targets"] == {"1R": 18295, "2R": 18337.5}
    assert result["setups"][1]["state"] == "none"
