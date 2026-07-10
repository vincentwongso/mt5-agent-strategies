# Open Range Breakout (ORB)

Trade the directional break of a session's opening range. The first N minutes of a session capture the overnight imbalance — a clean close beyond that range often signals which side absorbs flow for the rest of the session.

## Applicable symbols

ORB works on instruments with a well-defined session open and meaningful opening flow:

- **Indices** — `US30`, `NAS100`, `SPX500`, `GER40`. Anchor the range to the relevant cash open (NY 13:30 UTC for US, Frankfurt 07:00 UTC for GER40).
- **FX majors at session open** — `EURUSD`, `GBPUSD` at London open (07:00 UTC). `USDJPY` at Tokyo open (00:00 UTC) or NY open. Avoid mid-session ORB on FX — flow is too diffuse.
- **Gold (`XAUUSD`)** — NY open (13:30 UTC). London fix windows also produce clean ranges but skip days with scheduled fix-time data.
- **Silver (`XAGUSD`)** — NY open (13:30 UTC). More volatile than gold; tighten range-size filter toward the upper bound and expect wider spreads — verify tick value via `mt5-mcp__get_symbols` before sizing.

Not for: oil (use the swing-long playbook), exotics, crypto pairs on MT5 (low edge, wide spreads).

## Opening range definition

- **Default window**: **15 minutes** from the chosen session open. Captures enough flow to be meaningful without being so long the move is already gone.
- 5-minute variant only on highly liquid indices when MM has a strong directional bias from Stage 1.
- 30-minute variant when the session has known low-volatility character (e.g., summer Friday London).
- The "range" = highest high and lowest low of the window, including wicks.

## Entry conditions (all must be met at Stage 2)

1. **Closed break, not a wick**: a candle on the entry timeframe (M5 or M15) must **close** beyond the range high (long) or range low (short). A wick poke that reverses is not a signal — wait for the next close.
2. **Range size is sane**: ORB is a day-trade setup, so sanity-check the opening range against **D1 ATR(5)** and the recent session range. H1 ATR is micro-scalp context only. Too tight = noise; too wide = the move already happened inside the range.
3. **HTF alignment preferred, not required**: if H4 / daily bias agrees with the break direction, conviction is higher. A counter-trend ORB is allowed only when the range forms at a clear HTF level (prior day high/low, weekly open).
4. **No high-impact news within ±15 minutes of breakout** — standard Stage 1 news-window DEFER applies. ORB right into a release is a coin flip.
5. **No competing positions at the same total-account-risk cap** — see Charter's `max_total_open_risk_pct`.
6. **Within entry window**: breakout must occur **within 2 hours of session open**. Late-session breaks of the opening range are statistically much weaker — defer to a different setup.

## Entry sizing (Stage 2)

- Standard charter risk per trade (typically 1%). ORB is a single-entry setup — no pyramiding.
- Stop placement defines size: SL is at the **opposite end of the opening range**. Verify the resulting position size against contract-spec via `mt5-mcp__get_symbols` before submitting (see broker-symbol-specs rule).
- If the resulting risk distance is excessive versus **D1 ATR(5)** and current session structure, the range is too wide for ORB — skip.

## Management (Stage 3)

- **Initial SL**: opposite end of the opening range. Do NOT tighten before the first target.
- **First target (T1)**: **1R** — take **50% off**. Move stop to **breakeven** on the remainder.
- **Second target (T2)**: **measured move** — project the range height from the breakout level (range high + range_height for longs). Take another **25%** off here.
- **Runner (final 25%)**: trail behind M15 swing structure or VWAP, whichever is further from current price. Let it run until structural break or session close.
- **Time stop**: if price has not reached T1 within **2 hours of entry**, close the full position at market. Stagnant ORBs almost always fail.
- **Failed breakout**: if price re-enters the opening range and closes back inside on M15 before T1 hits, close full position immediately — the break failed regardless of where SL sits.

## Exit

| Reason | Action |
|--------|--------|
| Initial SL hit | Full close (standard) |
| T1 hit | 50% off, runner SL → breakeven |
| T2 hit | Additional 25% off, trail final 25% |
| Failed breakout (re-enters range on M15 close) | Full close immediately |
| Time stop (no T1 within 2 hours) | Full close at market |
| Session close approaching (< 30 min to close) | Close remainder — ORB is intraday, no carry |

## Disqualifiers

- **Do not use** if the opening range straddles a high-impact news release scheduled inside the window. The "range" is just pre-event positioning.
- **Do not use** on holiday-thinned sessions (US holidays, Christmas week, Boxing Day). Range forms on no volume and breaks are noise.
- **Do not use** if pre-market / overnight has already consumed an outsized share of **D1 ATR(5)** — the directional energy is likely spent.
- **Do not use** on the same symbol twice in one session. One ORB attempt per symbol per day; a failed break does not get a "retry."
- **Do not use** if the M15 candle that defines the breakout has spread > 30% of the candle body — that's a liquidity gap, not a break.
- **Do not use** when account equity is within 10% of daily-drawdown limit. ORB has a high failed-breakout rate; size down or skip.
