# ORB playbook

Use this reference after the evaluator returns a technical state. The CLI owns price arithmetic; these checks remain agent- and user-owned because OHLC alone cannot establish them.

## Session anchors

- GER40 cash open: `09:00 Europe/Berlin`, equivalent to `08:00 Europe/London` through normal DST alignment.
- US indices cash open: `09:30 America/New_York`.
- London FX session: `08:00 Europe/London`.
- Tokyo FX session: choose and document a local Asia session convention; do not label a fixed UTC hour as universal.

Use an IANA timezone so the UTC instant changes correctly with daylight saving.

## Technical rule

- Build the range from the highest high and lowest low, including wicks, during the configured opening window.
- Confirm a break only when a completed entry-timeframe candle closes beyond the range plus any configured buffer.
- Accept only the first qualifying break within the entry window.
- Put the reported technical stop at the opposite end of the range.
- Derive targets as configured R multiples of entry-to-stop distance.

## Contextual disqualifiers

Stand down or request an explicit user decision when any of these applies:

- High-impact scheduled news overlaps the opening range or falls within 15 minutes of the breakout.
- The session is holiday-thinned or the relevant cash market is closed.
- Spread or liquidity is abnormal at the breakout.
- The user already has competing exposure at their account risk cap.
- Equity is near the user's daily drawdown limit.
- The breakout conflicts with a required higher-timeframe filter in the user's own plan.

The bundled evaluator does not inspect news, market calendars, spreads, positions, equity, or higher-timeframe structure. Never claim those checks passed from OHLC output alone.

## Scope boundary

The skill reports a setup. It does not size positions, place orders, pyramid, manage partial exits, trail stops, or backtest profitability. Those require separate, explicit risk and execution layers.

