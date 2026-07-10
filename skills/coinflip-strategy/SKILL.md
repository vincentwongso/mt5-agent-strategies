---
name: coinflip-strategy
description: "Evaluate a deterministic coin-flip trade signal with a fixed reward-to-risk, and report its true expectancy. Use as the null hypothesis a real strategy must beat, to answer 'is my reward-to-risk enough on its own?', or to compute the win rate an indicator must reach to break even after spread. Advisory only: never size or place trades. It has no edge by construction."
---

# Coinflip: the null hypothesis

This skill picks a direction at random and attaches a fixed reward-to-risk. It exists to be
beaten, not traded. Its purpose is to make a specific, checkable claim visible: **a good
reward-to-risk ratio does not create an edge.**

Use the bundled CLI as the source of truth. Never estimate these levels from a chart.

## The claim, and why it holds

If price is a driftless random walk, the probability of touching a `+rr × R` target before a
`-1R` stop is exactly `1 / (1 + rr)`. At 1:1.5 that is 40%. Widening the target makes the win
rarer in exactly the proportion that makes it more valuable, so **expectancy before costs is
zero at every reward-to-risk ratio.** This is the optional stopping theorem. It is a property
of barriers on a martingale, not a claim about any particular market.

Costs break the symmetry, and always in one direction. Substituting the probability above into
the expectancy formula collapses it to `EV(R) = -cost_r`: **the expected loss per trade equals
exactly the cost paid per trade**, at every reward-to-risk ratio. Read
`references/expectancy.md` before telling a user anything about this strategy's viability.

## Run it

1. Read `references/input-format.md` when preparing bar data.
2. Configure each symbol's timezone and session windows. Nothing here has verified that any
   particular session or weekday is best — those are the user's priors, not measurements.
3. Gather completed bars at the configured interval, with a read-only market-data tool.
4. Write one input JSON file with an explicit `as_of` timestamp.
5. Run:

```bash
coinflip-evaluate --config config.yaml --input session-bars.json --pretty
```

6. **Always report the `expectancy` block alongside any signal.** It is not optional detail.
   Reporting the direction without `expected_value_r` and `edge_required` misrepresents what
   this skill is.

## Interpret states

- `stand_down`: the local weekday is excluded by config.
- `none`: `as_of` falls outside every configured session window.
- `invalidated`: too few completed bars to measure volatility, or a degenerate stop.
- `signal_long` / `signal_short`: the coin's call, with entry, stop, target, and expectancy.

The coin is seeded from the symbol and its session open, so it is **one flip per symbol per
session**. Re-evaluating five minutes later re-reads the same coin rather than tossing a new
one. Same bars and same `as_of` always produce the same answer, exactly as for every other
strategy here.

## Rank a watchlist

**Never rank on spread.** Rank ascending on `expectancy.cost_r`.

Because `EV(R) = -cost_r`, the only thing that matters is spread *relative to the stop*, and
the stop scales with volatility. A tight spread on a quiet instrument is worse than a wide
spread on a lively one. Concretely, at `stop_atr_multiple: 0.5`:

| spread | ATR(M5) | stop | `cost_r` | EV/trade |
|---|---|---|---|---|
| 0.2 | 1.0 | 0.50 | 0.4000 | −0.4000R |
| 1.0 | 9.0 | 4.50 | 0.2222 | −0.2222R |

The first symbol's spread is five times tighter, and it is more than twice as expensive to
trade. Screening a watchlist by spread alone selects exactly the wrong instruments.

The `volatility` and `expectancy` blocks are emitted in **every** state, including `none` and
`stand_down`, so a watchlist can be ranked before any session opens. To build one:

1. Pull the live spread for each candidate symbol with the read-only `get_symbols` tool, and
   convert to points (`spread * point`).
2. Pull `atr_period + 5` completed M5 bars per symbol.
3. Put the spreads in the input's `spread_points` map — not in `config.yaml`. Spread is data;
   it changes minute to minute.
4. Run the evaluator once for the whole watchlist and sort the setups by `expectancy.cost_r`,
   ascending.
5. Report `cost_r`, `edge_required`, and `expected_value_r` for each. Every `expected_value_r`
   will be negative. That is the finding, not a defect.

When `expectancy.breakeven_achievable` is `false`, the spread is so large relative to the stop
that breakeven would demand a win rate above 100%. No filter can rescue that symbol at that
stop size. Say so plainly rather than quoting `edge_required` as if it were a target.

`volatility.atr_percent_of_price` is comparable across instruments; `atr_points` is not. Use it
when asked for "the most volatile" symbol. Note that higher volatility raises the target and
the stop together, so it does not improve expectancy on its own — it only lowers `cost_r` by
making the spread a smaller share of the stop, and makes the outcome arrive sooner.

## Using it as a control

When a user proposes a filter, an indicator, or a session rule that they believe adds edge,
the honest test is whether it beats this coin **out of sample and net of costs**. The signal's
`edge_required` field states the bar in percentage points of win rate. A filter tuned until it
looks good on the same data it was chosen on has not cleared it.

## Boundaries

- Advisory only. Never place orders, calculate lots, or bypass account risk controls.
- Never present this strategy as tradeable, profitable, or as having any edge. It has none.
- Never omit the `expectancy` block when reporting a signal.
- Do not add a daily profit target, a martingale, or unlimited re-entry on this skill's output.
  Losing strategies are made worse, not better, by more trades.
- Contextual disqualifiers such as news, holidays, spread, exposure, and drawdown remain
  separate checks that this evaluator does not perform.
