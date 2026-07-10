"""What a coin flip is actually worth.

If price is a driftless random walk, the chance of touching a `+rr * R` target before a
`-1R` stop is exactly `1 / (1 + rr)`. Widening the target makes the win rarer in precisely
the proportion that makes it more valuable, so expectancy before costs is zero at every
reward-to-risk ratio. This is the optional stopping theorem, not a claim about markets.

Costs are what break the symmetry. Spread and slippage are charged on every trade, and a
scalp's stop is small, so the cost is a large fraction of 1R. Substituting p = 1/(1+rr) into
the expectancy formula collapses it to a single term:

    EV(R) = -cost_r          for every reward-to-risk ratio

Your expected loss per trade, measured in R, is exactly the cost you pay per trade, measured
in R. Reward-to-risk cancels out completely. It follows that the win rate a filter must add,
merely to break even, is `cost_r / (1 + rr)`.
"""

from __future__ import annotations

from decimal import Decimal


def target_first_probability(reward_risk: Decimal) -> Decimal:
    """P(target before stop) for a driftless walk. Depends only on the barrier ratio."""
    return Decimal(1) / (Decimal(1) + reward_risk)


def breakeven_win_rate(reward_risk: Decimal, cost_r: Decimal) -> Decimal:
    """The win rate at which `p * (rr - cost) == (1 - p) * (1 + cost)`."""
    return (Decimal(1) + cost_r) / (reward_risk + Decimal(1))


def expected_value_r(reward_risk: Decimal, cost_r: Decimal, win_rate: Decimal) -> Decimal:
    """Expectancy per trade, in units of R, net of cost on both winners and losers."""
    return win_rate * (reward_risk - cost_r) - (Decimal(1) - win_rate) * (Decimal(1) + cost_r)


def summary(reward_risk: Decimal, stop_points: Decimal, cost_points: Decimal) -> dict[str, object]:
    """The block every coinflip signal carries, so the number is never out of sight."""
    cost_r = cost_points / stop_points
    coin = target_first_probability(reward_risk)
    breakeven = breakeven_win_rate(reward_risk, cost_r)
    return {
        "reward_risk": reward_risk,
        "cost_r": cost_r,
        "coin_win_rate": coin,
        "breakeven_win_rate": breakeven,
        "edge_required": breakeven - coin,
        # When the spread is large relative to the stop, breakeven demands a win rate above
        # 100%. The arithmetic still returns a number; it just isn't a probability. Say so,
        # rather than reporting "you need a 386% win rate" as if it were a target.
        "breakeven_achievable": breakeven <= Decimal(1),
        "expected_value_r": expected_value_r(reward_risk, cost_r, coin),
        "note": (
            "A driftless walk hits the target first with probability 1/(1+rr), so expectancy "
            "before costs is zero at every reward-to-risk ratio. After costs, expected_value_r "
            "equals exactly -cost_r: your expected loss per trade is the cost you pay. "
            "`edge_required` is the win rate a filter must add, out of sample, to break even."
        ),
    }
