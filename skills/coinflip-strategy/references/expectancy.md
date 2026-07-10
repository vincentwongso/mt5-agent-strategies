# What a coin flip is worth

Read this before telling anyone whether this strategy — or their own — is viable.

## Reward-to-risk does not create edge

Take a driftless random walk. Place a stop at `-1R` and a target at `+rr × R`. The probability
of touching the target first is exactly:

```
P(target first) = 1 / (1 + rr)
```

This is the optional stopping theorem applied to a martingale with two absorbing barriers. It
is not an empirical claim about markets, and no indicator changes it.

Expectancy per trade, before costs, is therefore:

```
P     = 1 / (1 + rr)          probability the target is hit first
1 − P = rr / (1 + rr)         probability the stop is hit first

EV = P × rr − (1 − P) × 1
   = rr / (1 + rr) − rr / (1 + rr)
   = 0
```

Zero. At **every** reward-to-risk ratio. Simulated over 20,000 barrier crossings per row:

| R:R | P(win) simulated | P(win) exact | EV per trade |
|---|---|---|---|
| 1:1 | 0.4959 | 0.5000 | 0.0000 |
| 1:1.5 | 0.3998 | 0.4000 | 0.0000 |
| 1:2 | 0.3326 | 0.3333 | 0.0000 |
| 1:3 | 0.2449 | 0.2500 | 0.0000 |

Widening the target makes the win rarer in precisely the proportion that makes it more
valuable. Choosing 1:3 over 1:1.5 changes the *shape* of the equity curve — fewer, larger
wins — and nothing whatsoever about its expected value.

## Costs break the symmetry, one way

Spread and slippage are charged on every trade, win or lose. A scalp holds for minutes, so the
stop is small, so the cost is a **large fraction of 1R**. Write `c` for cost as a fraction of
the stop distance. Then:

```
EV(R) = P × (rr − c) − (1 − P) × (1 + c)
breakeven win rate = (1 + c) / (rr + 1)
```

Substituting `P = 1/(1+rr)` into that first equation collapses it entirely:

```
EV(R) = −cost_r          for every reward-to-risk ratio
```

**Your expected loss per trade, in R, is exactly the cost you pay per trade, in R.** Reward-to-
risk cancels out completely. It follows that the win rate a filter must add just to reach
breakeven is `cost_r / (1 + rr)`. Both identities are asserted in the test suite.

At `rr = 1.5`, where a coin gives 40%:

| cost / R | EV per trade | win rate needed | edge you must manufacture |
|---|---|---|---|
| 0.00 | 0.0000R | 40.0% | — |
| 0.05 | −0.0500R | 42.0% | +2.0 points |
| 0.10 | −0.1000R | 44.0% | +4.0 points |
| 0.15 | −0.1500R | 46.0% | +6.0 points |
| 0.25 | −0.2500R | 50.0% | +10.0 points |

The last column is the honest price of "I'll add some indicators to tilt the probability." At a
realistic scalping cost, a filter must lift the win rate by **six percentage points, out of
sample, net of costs**, merely to stop losing money. Not to profit. To break even.

A filter tuned until it looks good on the data it was selected on has not cleared that bar. It
has only memorised the sample.

## Why a daily profit target makes it worse

A common rule is "risk 0.1% per trade, stop for the day at +5%, no cap on trades." Reaching +5%
at 0.1% risk means netting +50R. Simulating 4,000 trading days under exactly that rule:

| cost / R | P(reach +5%) | P(reach −5%) | median trades to resolve |
|---|---|---|---|
| 0.00 | 48.7% | 47.8% | 1,306 |
| 0.05 | 3.7% | 96.2% | 744 |
| 0.10 | 0.1% | 99.9% | 446 |
| 0.15 | **0.0%** | **100.0%** | 309 |

At zero cost it is a coin flip on the day, as the theory requires. At a realistic cost it
reached +5% in **zero of 4,000 simulated days**.

The structure is what does the damage. Stopping at +5% caps the upside; leaving trade count
uncapped uncaps the downside. Every additional trade is another independent draw from a
negative-expectancy distribution, so *more trading strictly increases the certainty of loss*.
This is why the skill refuses to encode a daily target or unlimited re-entry.

## What this skill is for

It is the control group. Any strategy that cannot beat a coin, out of sample and after costs,
has no edge. This one has no edge by construction, which makes it the cleanest possible
baseline — and a permanent reminder that risk-reward arithmetic is a property of your exit
rules, never a substitute for a reason to be in the trade.

## What has not been verified here

The example config skips Monday and anchors to the London and New York cash opens. **Neither
choice has been measured.** They are the author's priors, carried into config so they are easy
to change and easy to test, not findings. Do not describe them as such.
