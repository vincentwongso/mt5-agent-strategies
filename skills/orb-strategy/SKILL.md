---
name: orb-strategy
description: "Evaluate an open-range breakout (ORB) deterministically from timestamped OHLC bars. Use when a user asks whether a session opening range is building, armed, broken long or short, or invalidated; wants reproducible entry, stop, risk, and R-multiple targets; or wants to monitor an ORB watchlist. Advisory only: never size or place trades."
---

# Open-range breakout

Use the bundled CLI as the source of truth. Do not estimate range levels or targets from prose or a chart when the CLI can evaluate the same bars.

## Evaluate a session

1. Read `references/input-format.md` when preparing bar data or connecting an OHLC source.
2. Confirm each symbol's local session open and IANA timezone in the config. Never hard-code a UTC open across daylight-saving changes.
3. Gather completed bars at the configured interval. With `mt5-trading-mcp`, call the read-only `get_rates` tool for M5 bars. Fetch D1 bars too when ATR reporting or filtering is required.
4. Write one input JSON file with an explicit `as_of` timestamp. Preserve the bar timestamps and prices exactly as returned.
5. Run:

```bash
orb-evaluate --config config.yaml --input session-bars.json --pretty
```

6. Narrate the returned state and levels. Keep `invalidated` reasons and data-quality errors visible.
7. Before calling a breakout actionable, apply the contextual checks in `references/playbook.md`, especially scheduled news, holiday-thinned sessions, spread, existing exposure, and drawdown limits. These are not inferred by the OHLC evaluator.

## Interpret states

- `none`: today's configured session has not opened.
- `building`: the opening range has started but is not locked yet.
- `armed`: the full range is locked and no completed bar has closed through it.
- `breakout_long` or `breakout_short`: the first completed close cleared the configured buffer; report entry, opposite-range stop, risk in points, and targets.
- `invalidated`: required bars are missing, an enabled ATR bound rejected the range, or the entry window expired without a break.

Treat a breakout as a technical candidate, not a recommendation or order instruction.

## Configure

Start from `config.example.yaml`. Define session settings per symbol because GER40 and US30 do not share a cash open. Keep `bar_minutes` aligned with the bars supplied.

ATR bounds default to `null` because useful thresholds are instrument- and dataset-specific. When a bound is enabled, supply enough completed D1 bars for the configured ATR period or the evaluator invalidates the setup instead of guessing.

## Boundaries

- Remain advisory-only. Never place orders, calculate lots, or bypass account risk controls.
- Use only completed bars for close confirmation; the CLI excludes an in-progress bar using `as_of`.
- Take only the first qualifying break per symbol and session.
- Do not present a bare ORB rule or synthetic fixture as evidence of an edge or profitability.
- Do not silently convert broker server time. Require timezone-aware ISO 8601 timestamps.
