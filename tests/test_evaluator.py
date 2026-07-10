from datetime import UTC, datetime
from decimal import Decimal

from orb_strategy.evaluator import evaluate_symbol
from orb_strategy.models import AtrFilters, Bar, InputData, SymbolConfig


def bar(hour: int, minute: int, high: str, low: str, close: str, *, month: int = 7) -> Bar:
    value = Decimal(close)
    return Bar(
        time=datetime(2026, month, 10, hour, minute, tzinfo=UTC),
        open=value,
        high=Decimal(high),
        low=Decimal(low),
        close=value,
    )


def config(**overrides) -> SymbolConfig:
    values = {
        "symbol": "GER40",
        "timezone": "Europe/London",
        "session_open": datetime.strptime("08:00", "%H:%M").time(),
        "range_minutes": 15,
        "entry_window_minutes": 120,
        "bar_minutes": 5,
        "buffer_points": Decimal(0),
        "targets_r": (Decimal(1), Decimal(2)),
        "atr": AtrFilters(),
    }
    values.update(overrides)
    return SymbolConfig(**values)


def session_bars(extra=()):
    return (
        bar(7, 0, "18232", "18215", "18225"),
        bar(7, 5, "18235", "18210", "18218"),
        bar(7, 10, "18250", "18212", "18230"),
        *extra,
    )


def flat_entry_bars():
    return tuple(
        bar(7 + minute // 60, minute % 60, "18245", "18220", "18230")
        for minute in range(15, 120, 5)
    )


def data(as_of: datetime, bars=(), daily=()) -> InputData:
    return InputData(as_of=as_of, bars={"GER40": tuple(bars)}, daily_bars={"GER40": tuple(daily)})


def test_before_open_is_none():
    result = evaluate_symbol(config(), data(datetime(2026, 7, 10, 6, 59, tzinfo=UTC)))
    assert result["state"] == "none"


def test_incomplete_current_bar_keeps_range_building():
    result = evaluate_symbol(
        config(),
        data(datetime(2026, 7, 10, 7, 14, tzinfo=UTC), session_bars()),
    )
    assert result["state"] == "building"
    assert result["range"] == {"high": 18235, "low": 18210, "size": 25}


def test_range_arms_after_three_complete_m5_bars():
    inside = bar(7, 15, "18245", "18220", "18230")
    result = evaluate_symbol(
        config(),
        data(datetime(2026, 7, 10, 7, 20, tzinfo=UTC), session_bars((inside,))),
    )
    assert result["state"] == "armed"
    assert result["range"] == {"high": 18250, "low": 18210, "size": 40}


def test_wick_above_does_not_confirm_breakout():
    wick = bar(7, 15, "18260", "18230", "18245")
    result = evaluate_symbol(
        config(),
        data(datetime(2026, 7, 10, 7, 20, tzinfo=UTC), session_bars((wick,))),
    )
    assert result["state"] == "armed"


def test_first_close_above_range_returns_levels():
    first = bar(7, 15, "18255", "18230", "18252.5")
    later = bar(7, 20, "18280", "18245", "18270")
    result = evaluate_symbol(
        config(),
        data(datetime(2026, 7, 10, 7, 25, tzinfo=UTC), session_bars((first, later))),
    )
    assert result["state"] == "breakout_long"
    assert result["signal"]["entry"] == 18252.5
    assert result["signal"]["stop"] == 18210
    assert result["signal"]["risk_points"] == 42.5
    assert result["signal"]["targets"] == {"1R": 18295, "2R": 18337.5}
    assert result["signal"]["trigger_time"] == "2026-07-10T07:20:00Z"


def test_close_below_range_returns_short_levels():
    first = bar(7, 15, "18220", "18195", "18200")
    result = evaluate_symbol(
        config(),
        data(datetime(2026, 7, 10, 7, 20, tzinfo=UTC), session_bars((first,))),
    )
    assert result["state"] == "breakout_short"
    assert result["signal"]["stop"] == 18250
    assert result["signal"]["risk_points"] == 50
    assert result["signal"]["targets"] == {"1R": 18150, "2R": 18100}


def test_no_break_by_deadline_invalidates_session():
    result = evaluate_symbol(
        config(),
        data(
            datetime(2026, 7, 10, 9, 0, tzinfo=UTC),
            session_bars(flat_entry_bars()),
        ),
    )
    assert result["state"] == "invalidated"
    assert result["reason"] == "entry_window_expired"


def test_new_york_open_tracks_daylight_saving():
    ny = config(
        symbol="US30",
        timezone="America/New_York",
        session_open=datetime.strptime("09:30", "%H:%M").time(),
    )
    summer = evaluate_symbol(
        ny,
        InputData(datetime(2026, 7, 10, 13, 29, tzinfo=UTC), {"US30": ()}, {}),
    )
    winter = evaluate_symbol(
        ny,
        InputData(datetime(2026, 1, 10, 14, 29, tzinfo=UTC), {"US30": ()}, {}),
    )
    assert summer["session_open"] == "2026-07-10T13:30:00Z"
    assert winter["session_open"] == "2026-01-10T14:30:00Z"


def test_enabled_atr_filter_fails_closed_when_daily_bars_absent():
    filtered = config(atr=AtrFilters(period=5, maximum=Decimal("0.5")))
    result = evaluate_symbol(
        filtered,
        data(datetime(2026, 7, 10, 7, 20, tzinfo=UTC), session_bars()),
    )
    assert result["state"] == "invalidated"
    assert result["reason"] == "atr_unavailable"


def test_missing_entry_bar_invalidates_instead_of_skipping_first_break():
    later = bar(7, 20, "18260", "18240", "18255")
    result = evaluate_symbol(
        config(),
        data(datetime(2026, 7, 10, 7, 25, tzinfo=UTC), session_bars((later,))),
    )
    assert result["state"] == "invalidated"
    assert result["reason"] == "entry_bars_incomplete"
    assert result["missing_bars"] == ["2026-07-10T07:15:00Z"]
