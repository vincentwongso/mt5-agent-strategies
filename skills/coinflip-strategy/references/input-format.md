# Input format

The evaluator accepts the same JSON document every strategy in this repo accepts:

```json
{
  "as_of": "2026-07-14T08:30:00Z",
  "bars": {
    "GER40": [
      {
        "time": "2026-07-14T08:25:00Z",
        "open": "18220.0",
        "high": "18235.0",
        "low": "18212.0",
        "close": "18230.0"
      }
    ]
  },
  "spread_points": {
    "GER40": "1.0"
  }
}
```

## Contract

- `as_of` is required and must include `Z` or an explicit UTC offset. It defines "now", and it
  is the only clock the evaluator has.
- `bars` maps each configured symbol to intraday OHLC bars at the configured `bar_minutes`.
- Supply at least `atr_period + 1` completed bars per symbol, or the symbol comes back
  `invalidated` with `insufficient_bars` rather than a guess.
- `daily_bars` is unused by this strategy and may be omitted.
- Bar order does not matter; the evaluator sorts by timestamp.
- `time` is the bar's opening time and must be timezone-aware ISO 8601.
- Prices may be JSON numbers or decimal strings. Strings preserve broker precision best.
- `NaN` and `Infinity` are rejected as invalid input, not silently propagated.
- Extra MT5 fields such as `tick_volume`, `real_volume`, and `spread` are allowed and ignored.

## MetaTrader 5 adapter

With `mt5-trading-mcp`, call `get_rates(symbol, "M5", atr_period + 5)` for intraday bars.
The MCP result is most-recent-first; preserve it as returned because the evaluator sorts it.

Record the current timezone-aware UTC time as `as_of`. The current, unfinished M5 bar is
excluded automatically: a bar counts only once `time + bar_minutes <= as_of`.

## Spread

`spread_points` maps each symbol to its live spread plus expected slippage, in the
instrument's points — the same units as the prices in `bars`. It is **optional but strongly
preferred**. When a symbol is absent from it, the evaluator falls back to that symbol's
`cost_points` in `config.yaml` and reports `expectancy.spread_source: "config"`.

Prefer the input. A spread written into a YAML file is stale the moment it is saved, and the
spread is the single number that decides everything the `expectancy` block reports. Setting it
to `0` makes the strategy appear break-even, which it is not.

With `mt5-trading-mcp`, read it from the read-only `get_symbols` tool and convert to points:

```
spread_points = symbol.spread * symbol.point
```

Then add whatever slippage a market exit realistically costs you. `expectancy.spread_source`
tells you which value was used, so a screening report can never quietly mix live and stale
numbers.

## Screening a watchlist

`volatility` and `expectancy` are emitted in every state, including `none` and `stand_down`,
so a watchlist can be ranked outside session hours. Sort ascending on `expectancy.cost_r` —
never on raw spread. See `expectancy.md` for why.
