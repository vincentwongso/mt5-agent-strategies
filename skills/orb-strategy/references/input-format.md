# Input format

The evaluator accepts one JSON document:

```json
{
  "as_of": "2026-07-10T07:30:00Z",
  "bars": {
    "GER40": [
      {
        "time": "2026-07-10T07:00:00Z",
        "open": "18220.0",
        "high": "18235.0",
        "low": "18212.0",
        "close": "18230.0"
      }
    ]
  },
  "daily_bars": {
    "GER40": []
  }
}
```

## Contract

- `as_of` is required and must include `Z` or an explicit UTC offset. It makes completed-bar handling reproducible.
- `bars` maps each configured symbol to intraday OHLC bars.
- `daily_bars` is optional unless ATR bounds are enabled. Provide at least `atr_period + 1` completed D1 bars.
- Bar order does not matter; the evaluator sorts by timestamp.
- `time` is the bar's opening time and must be timezone-aware ISO 8601.
- Prices may be JSON numbers or decimal strings. Strings preserve broker precision best.
- Extra MT5 fields such as `tick_volume`, `real_volume`, and `spread` are allowed and ignored by the deterministic core.

## MetaTrader 5 adapter

With `mt5-trading-mcp`, call `get_rates(symbol, "M5", count)` for intraday bars and `get_rates(symbol, "D1", atr_period + 2)` for ATR context. The MCP result is most-recent-first; preserve it as returned because the evaluator sorts it.

Assemble the tool results under their symbols and record the current timezone-aware UTC time as `as_of`. Do not use the current M5 bar as a close confirmation: the evaluator treats it as incomplete until `time + bar_minutes <= as_of`.

