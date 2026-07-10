from datetime import UTC, datetime
from decimal import Decimal

import pytest

from mt5_agent_strategies.core.errors import StrategyError
from mt5_agent_strategies.core.models import Bar, InputData
from mt5_agent_strategies.strategies.coinflip import CoinflipConfig, evaluate_symbol, flip
from mt5_agent_strategies.strategies.coinflip import config as cf_config
from mt5_agent_strategies.strategies.coinflip import expectancy

LONDON = [(datetime.strptime("08:00", "%H:%M").time(), 120)]


def config(**overrides) -> CoinflipConfig:
    values = {
        "symbol": "GER40",
        "timezone": "Europe/London",
        "sessions": tuple(LONDON),
        "skip_weekdays": frozenset(),
        "bar_minutes": 5,
        "atr_period": 3,
        "stop_atr_multiple": Decimal("0.5"),
        "reward_risk": Decimal("1.5"),
        "cost_points": Decimal(0),
    }
    values.update(overrides)
    return CoinflipConfig(**values)


def bars(count: int, start_hour: int = 7, day: int = 14) -> tuple[Bar, ...]:
    out = []
    for index in range(count):
        base = Decimal(18000 + index)
        out.append(
            Bar(
                time=datetime(2026, 7, day, start_hour, index * 5, tzinfo=UTC),
                open=base,
                high=base + 10,
                low=base - 10,
                close=base,
            )
        )
    return tuple(out)


def data(as_of: datetime, rows: tuple[Bar, ...] = (), spreads=None) -> InputData:
    return InputData(as_of=as_of, bars={"GER40": rows}, daily_bars={}, spreads=dict(spreads or {}))


# --- the math, which is the whole point ------------------------------------------------


@pytest.mark.parametrize("rr", ["1", "1.5", "2", "3", "5"])
def test_expectancy_before_costs_is_zero_at_every_reward_risk(rr):
    """The optional stopping theorem. Exact to Decimal's working precision: for rr like 2,
    P = 1/3 does not terminate, so the residual is representation error, not expectancy."""
    reward_risk = Decimal(rr)
    p = expectancy.target_first_probability(reward_risk)
    assert abs(expectancy.expected_value_r(reward_risk, Decimal(0), p)) < Decimal("1e-25")


def test_target_first_probability_matches_the_barrier_ratio():
    assert expectancy.target_first_probability(Decimal("1.5")) == Decimal("0.4")
    assert expectancy.target_first_probability(Decimal(1)) == Decimal("0.5")


def test_costs_make_expectancy_strictly_negative_for_a_coin():
    reward_risk = Decimal("1.5")
    coin = expectancy.target_first_probability(reward_risk)
    for cost in ("0.05", "0.10", "0.15", "0.25"):
        assert expectancy.expected_value_r(reward_risk, Decimal(cost), coin) < 0


@pytest.mark.parametrize("rr", ["0.5", "1", "1.5", "2", "3"])
@pytest.mark.parametrize("cost", ["0.05", "0.2", "0.222753", "0.5"])
def test_expected_loss_per_trade_equals_the_cost_paid(rr, cost):
    """Substituting p = 1/(1+rr) collapses expectancy to exactly -cost_r, for every rr.
    Reward-to-risk cancels out entirely; the coin loses precisely what it is charged."""
    reward_risk, cost_r = Decimal(rr), Decimal(cost)
    coin = expectancy.target_first_probability(reward_risk)
    ev = expectancy.expected_value_r(reward_risk, cost_r, coin)
    assert abs(ev - (-cost_r)) < Decimal("1e-25")


@pytest.mark.parametrize("rr", ["0.5", "1", "1.5", "2", "3"])
@pytest.mark.parametrize("cost", ["0.05", "0.2", "0.5"])
def test_edge_required_is_cost_over_one_plus_reward_risk(rr, cost):
    reward_risk, cost_r = Decimal(rr), Decimal(cost)
    coin = expectancy.target_first_probability(reward_risk)
    edge = expectancy.breakeven_win_rate(reward_risk, cost_r) - coin
    assert abs(edge - cost_r / (Decimal(1) + reward_risk)) < Decimal("1e-25")


def test_breakeven_win_rate_rises_with_cost():
    reward_risk = Decimal("1.5")
    assert expectancy.breakeven_win_rate(reward_risk, Decimal(0)) == Decimal("0.4")
    assert expectancy.breakeven_win_rate(reward_risk, Decimal("0.15")) == Decimal("0.46")
    assert expectancy.breakeven_win_rate(reward_risk, Decimal("0.25")) == Decimal("0.5")


def test_breakeven_win_rate_is_the_zero_of_expected_value():
    reward_risk, cost = Decimal("1.5"), Decimal("0.15")
    breakeven = expectancy.breakeven_win_rate(reward_risk, cost)
    assert expectancy.expected_value_r(reward_risk, cost, breakeven) == 0


# --- determinism -----------------------------------------------------------------------


def test_flip_is_stable_for_a_session():
    session = datetime(2026, 7, 14, 7, 0, tzinfo=UTC)
    calls = {flip("GER40", session, Decimal("1.5")) for _ in range(50)}
    assert len(calls) == 1


def test_flip_differs_across_symbols_and_sessions():
    a = datetime(2026, 7, 14, 7, 0, tzinfo=UTC)
    b = datetime(2026, 7, 15, 7, 0, tzinfo=UTC)
    outcomes = {
        flip("GER40", a, Decimal("1.5")),
        flip("US30", a, Decimal("1.5")),
        flip("GER40", b, Decimal("1.5")),
    }
    assert outcomes <= {"long", "short"}
    assert all(value in ("long", "short") for value in outcomes)


def test_signal_is_identical_across_repeated_evaluations_in_the_session():
    rows = bars(6)
    results = [
        evaluate_symbol(config(), data(datetime(2026, 7, 14, 7, minute, tzinfo=UTC), rows))
        for minute in (30, 35, 40)
    ]
    assert len({result["state"] for result in results}) == 1
    assert len({result["signal"]["direction"] for result in results}) == 1


# --- state machine ---------------------------------------------------------------------


def test_outside_session_reports_none():
    result = evaluate_symbol(config(), data(datetime(2026, 7, 14, 12, 0, tzinfo=UTC), bars(6)))
    assert result["state"] == "none"
    assert result["reason"] == "outside_session"


def test_excluded_weekday_stands_down():
    monday = datetime(2026, 7, 13, 7, 30, tzinfo=UTC)
    result = evaluate_symbol(config(skip_weekdays=frozenset({0})), data(monday, bars(6)))
    assert result["state"] == "stand_down"
    assert result["reason"] == "weekday_excluded"


def test_too_few_bars_invalidates_rather_than_guessing():
    result = evaluate_symbol(config(), data(datetime(2026, 7, 14, 7, 30, tzinfo=UTC), bars(2)))
    assert result["state"] == "invalidated"
    assert result["reason"] == "insufficient_bars"
    assert result["required_bars"] == 4


def test_signal_carries_levels_and_expectancy():
    result = evaluate_symbol(config(), data(datetime(2026, 7, 14, 7, 30, tzinfo=UTC), bars(6)))
    assert result["state"] in ("signal_long", "signal_short")
    signal, numbers = result["signal"], result["expectancy"]
    assert numbers["coin_win_rate"] == 0.4
    assert numbers["expected_value_r"] == 0  # cost_points is 0 in this config
    # reward is exactly 1.5x the risk, by construction
    assert signal["reward_points"] == pytest.approx(signal["risk_points"] * 1.5)
    if signal["direction"] == "long":
        assert signal["stop"] < signal["entry"] < signal["target"]
    else:
        assert signal["target"] < signal["entry"] < signal["stop"]


def test_realistic_cost_reports_negative_expectancy_and_a_required_edge():
    result = evaluate_symbol(
        config(cost_points=Decimal("1.5")),
        data(datetime(2026, 7, 14, 7, 30, tzinfo=UTC), bars(6)),
    )
    numbers = result["expectancy"]
    assert numbers["expected_value_r"] < 0
    assert numbers["breakeven_win_rate"] > numbers["coin_win_rate"]
    assert numbers["edge_required"] > 0


# --- screening a watchlist -------------------------------------------------------------


def test_live_spread_from_input_overrides_configured_cost():
    at = datetime(2026, 7, 14, 7, 30, tzinfo=UTC)
    configured = evaluate_symbol(config(cost_points=Decimal("1.0")), data(at, bars(6)))
    live = evaluate_symbol(
        config(cost_points=Decimal("1.0")),
        data(at, bars(6), spreads={"GER40": Decimal("4.0")}),
    )
    assert configured["expectancy"]["spread_source"] == "config"
    assert live["expectancy"]["spread_source"] == "input"
    assert live["expectancy"]["spread_points"] == 4.0
    assert live["expectancy"]["cost_r"] > configured["expectancy"]["cost_r"]


def test_screening_blocks_are_present_outside_the_session():
    """A watchlist must be rankable before any session opens."""
    result = evaluate_symbol(config(), data(datetime(2026, 7, 14, 12, 0, tzinfo=UTC), bars(6)))
    assert result["state"] == "none"
    assert "signal" not in result
    assert result["expectancy"]["cost_r"] >= 0
    assert result["volatility"]["atr_points"] > 0


def test_screening_blocks_are_present_on_an_excluded_weekday():
    monday = datetime(2026, 7, 13, 7, 30, tzinfo=UTC)
    result = evaluate_symbol(config(skip_weekdays=frozenset({0})), data(monday, bars(6, day=13)))
    assert result["state"] == "stand_down"
    assert "expectancy" in result and "volatility" in result


def test_breakeven_above_one_is_flagged_unachievable():
    """A spread wide enough versus the stop demands a win rate over 100%. That is not a
    target to aim at, and must not be reported as one."""
    at = datetime(2026, 7, 14, 7, 30, tzinfo=UTC)
    ok = evaluate_symbol(config(), data(at, bars(6), spreads={"GER40": Decimal("0.5")}))
    hopeless = evaluate_symbol(config(), data(at, bars(6), spreads={"GER40": Decimal("40")}))
    assert ok["expectancy"]["breakeven_achievable"] is True
    assert ok["expectancy"]["breakeven_win_rate"] <= 1
    assert hopeless["expectancy"]["breakeven_achievable"] is False
    assert hopeless["expectancy"]["breakeven_win_rate"] > 1


def test_tight_spread_can_be_worse_than_wide_spread():
    """The whole reason to rank on cost_r rather than on spread.

    A 0.5-point spread against a small stop costs more R than a 2.0-point spread
    against a stop four times larger.
    """
    at = datetime(2026, 7, 14, 7, 30, tzinfo=UTC)
    tight = evaluate_symbol(
        config(stop_atr_multiple=Decimal("0.1")),
        data(at, bars(6), spreads={"GER40": Decimal("0.5")}),
    )
    wide = evaluate_symbol(
        config(stop_atr_multiple=Decimal("0.8")),
        data(at, bars(6), spreads={"GER40": Decimal("2.0")}),
    )
    assert tight["expectancy"]["spread_points"] < wide["expectancy"]["spread_points"]
    assert tight["expectancy"]["cost_r"] > wide["expectancy"]["cost_r"]
    assert tight["expectancy"]["expected_value_r"] < wide["expectancy"]["expected_value_r"]


# --- config ----------------------------------------------------------------------------


def test_example_config_loads():
    configs = cf_config.load("skills/coinflip-strategy/config.example.yaml")
    assert [item.symbol for item in configs] == ["GER40", "US30"]
    assert configs[0].skip_weekdays == frozenset({0})
    assert configs[1].sessions[0][1] == 240


def test_reward_risk_below_the_floor_is_rejected(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "defaults:\n"
        "  timezone: Europe/London\n"
        "  reward_risk: 1.0\n"
        "  sessions:\n"
        "    - open: '08:00'\n"
        "      minutes: 120\n"
        "symbols:\n  GER40: {}\n"
    )
    with pytest.raises(StrategyError, match="reward_risk must be at least 1.5"):
        cf_config.load(path)


def test_unknown_weekday_is_rejected(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "defaults:\n"
        "  timezone: Europe/London\n"
        "  sessions:\n"
        "    - open: '08:00'\n"
        "      minutes: 120\n"
        "  skip_weekdays: [Funday]\n"
        "symbols:\n  GER40: {}\n"
    )
    with pytest.raises(StrategyError, match="must be weekday names"):
        cf_config.load(path)
