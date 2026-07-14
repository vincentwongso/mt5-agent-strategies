"""The ORB activity gate: arm only when the opening range printed on elevated volume.

Baselines anchor to prior sessions' local opens; anything the gate cannot compute
honestly fails closed. The filter claims no edge — these tests defend determinism and
fail-closed behavior, not profitability.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from mt5_agent_strategies.core.models import Bar, InputData
from mt5_agent_strategies.strategies.orb import (
    ActivityFilters,
    AtrFilters,
    OrbConfig,
    evaluate_symbol,
)

SESSION_OPEN = datetime.strptime("08:00", "%H:%M").time()


def config(**overrides) -> OrbConfig:
    values = {
        "symbol": "GER40",
        "timezone": "Europe/London",
        "session_open": SESSION_OPEN,
        "range_minutes": 15,
        "entry_window_minutes": 120,
        "bar_minutes": 5,
        "buffer_points": Decimal(0),
        "targets_r": (Decimal(1), Decimal(2)),
        "atr": AtrFilters(),
        "activity": ActivityFilters(minimum=Decimal("1.5"), lookback=3),
    }
    values.update(overrides)
    return OrbConfig(**values)


def bar(time: datetime, volume: int | None, close: str = "18230") -> Bar:
    value = Decimal(close)
    return Bar(
        time=time,
        open=value,
        high=Decimal("18250"),
        low=Decimal("18210"),
        close=value,
        tick_volume=None if volume is None else Decimal(volume),
    )


def baseline_bars(days=(11, 12, 13), volume: int = 300, month: int = 7) -> list[Bar]:
    """Complete opening-range windows (3 M5 bars) on prior weekday sessions.

    2026-07-11/12 are Sat/Sun; tests that use them prove weekend-shaped data is just
    'another incomplete day' rather than special-cased. 08:00 Europe/London in July is
    07:00 UTC.
    """
    bars = []
    for day in days:
        opened = datetime(2026, month, day, 7, 0, tzinfo=UTC)
        bars += [bar(opened + timedelta(minutes=m), volume) for m in (0, 5, 10)]
    return bars


def current_range(volume: int | None = 1500) -> list[Bar]:
    opened = datetime(2026, 7, 14, 7, 0, tzinfo=UTC)
    return [bar(opened + timedelta(minutes=m), volume) for m in (0, 5, 10)]


def breaking_bar(volume: int = 800) -> Bar:
    return bar(datetime(2026, 7, 14, 7, 15, tzinfo=UTC), volume, close="18252.5")


def data(as_of: datetime, bars) -> InputData:
    return InputData(as_of=as_of, bars={"GER40": tuple(bars)}, daily_bars={})


AS_OF_ARMED = datetime(2026, 7, 14, 7, 15, tzinfo=UTC)
AS_OF_BROKEN = datetime(2026, 7, 14, 7, 20, tzinfo=UTC)


def test_elevated_open_arms_and_reports_activity():
    bars = baseline_bars(days=(8, 9, 10)) + current_range(1500)
    result = evaluate_symbol(config(), data(AS_OF_ARMED, bars))
    assert result["state"] == "armed"
    assert result["activity"] == {
        "threshold": 1.5,
        "lookback_sessions": 3,
        "or_volume": 4500,
        "baseline_volume": 900,
        "relative_volume": 5,
    }


def test_elevated_open_confirms_break_through_the_gate():
    bars = baseline_bars(days=(8, 9, 10)) + current_range(1500) + [breaking_bar()]
    result = evaluate_symbol(config(), data(AS_OF_BROKEN, bars))
    assert result["state"] == "breakout_long"
    assert result["signal"]["entry"] == 18252.5
    assert result["activity"]["relative_volume"] == 5


def test_quiet_open_stands_down():
    bars = baseline_bars(days=(8, 9, 10), volume=1200) + current_range(300)
    result = evaluate_symbol(config(), data(AS_OF_ARMED, bars))
    assert result["state"] == "invalidated"
    assert result["reason"] == "opening_activity_below_threshold"
    assert result["activity"]["relative_volume"] == 0.25


def test_weekend_days_are_skipped_not_fatal():
    # Baselines on Wed 8th, Thu 9th, Fri 10th; the walk crosses Sat 11th / Sun 12th /
    # Mon 13th (absent) without counting them.
    bars = baseline_bars(days=(8, 9, 10)) + current_range(1500)
    result = evaluate_symbol(config(), data(AS_OF_ARMED, bars))
    assert result["state"] == "armed"


def test_short_history_fails_closed():
    bars = baseline_bars(days=(9, 10)) + current_range(1500)
    result = evaluate_symbol(config(), data(AS_OF_ARMED, bars))
    assert result["state"] == "invalidated"
    assert result["reason"] == "insufficient_volume_history"
    assert result["activity"]["relative_volume"] is None
    assert result["activity"]["or_volume"] == 4500


def test_missing_volume_on_a_baseline_day_does_not_count_toward_lookback():
    incomplete = baseline_bars(days=(8,), volume=300)
    incomplete[1] = bar(incomplete[1].time, None)  # one bar without volume
    bars = incomplete + baseline_bars(days=(9, 10)) + current_range(1500)
    result = evaluate_symbol(config(), data(AS_OF_ARMED, bars))
    assert result["state"] == "invalidated"
    assert result["reason"] == "insufficient_volume_history"


def test_missing_volume_on_current_range_fails_closed():
    bars = baseline_bars(days=(8, 9, 10)) + current_range(None)
    result = evaluate_symbol(config(), data(AS_OF_ARMED, bars))
    assert result["state"] == "invalidated"
    assert result["reason"] == "insufficient_volume_history"
    assert result["activity"]["or_volume"] is None


def test_zero_baseline_fails_closed():
    bars = baseline_bars(days=(8, 9, 10), volume=0) + current_range(1500)
    result = evaluate_symbol(config(), data(AS_OF_ARMED, bars))
    assert result["state"] == "invalidated"
    assert result["reason"] == "insufficient_volume_history"


def test_gate_disabled_ignores_volume_entirely():
    off = config(activity=ActivityFilters())
    result = evaluate_symbol(off, data(AS_OF_ARMED, current_range(None)))
    assert result["state"] == "armed"
    assert "activity" not in result


def test_gated_break_is_stable_across_later_polls():
    bars = baseline_bars(days=(8, 9, 10)) + current_range(1500) + [breaking_bar()]
    results = [
        evaluate_symbol(config(), data(datetime(2026, 7, 14, 7, minute, tzinfo=UTC), bars))
        for minute in (20, 25, 40, 55)
    ]
    assert [r["state"] for r in results] == ["breakout_long"] * 4
    assert {r["activity"]["relative_volume"] for r in results} == {5}


def test_baseline_windows_anchor_to_local_opens_across_dst():
    """US30 09:30 America/New_York: 14:30 UTC before the March DST jump, 13:30 after.

    Baselines live on the winter side, the current session on the summer side; the
    gate must find both by anchoring to local wall time, not a fixed UTC hour.
    """
    ny = config(
        symbol="GER40",  # symbol name is irrelevant; keep the data map key stable
        timezone="America/New_York",
        session_open=datetime.strptime("09:30", "%H:%M").time(),
        activity=ActivityFilters(minimum=Decimal("1.5"), lookback=2),
    )
    bars = []
    for day, utc_hour in ((5, 14), (6, 14)):  # Thu 5th, Fri 6th March 2026: EST
        opened = datetime(2026, 3, day, utc_hour, 30, tzinfo=UTC)
        bars += [bar(opened + timedelta(minutes=m), 300) for m in (0, 5, 10)]
    current_open = datetime(2026, 3, 9, 13, 30, tzinfo=UTC)  # Mon 9th: EDT
    bars += [bar(current_open + timedelta(minutes=m), 900) for m in (0, 5, 10)]
    result = evaluate_symbol(ny, data(current_open + timedelta(minutes=15), bars))
    assert result["state"] == "armed"
    assert result["activity"]["relative_volume"] == 3
