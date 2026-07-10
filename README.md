# mt5-agent-strategies

Deterministic trading-strategy evaluators, packaged as portable [Agent Skills](https://agentskills.io/specification).

An LLM asked to read a chart will improvise a level and fail to reproduce it thirty seconds
later. These evaluators do the price arithmetic in plain Python instead: the same bars and the
same `as_of` timestamp always produce the same levels. The agent's job is to collect the bars,
run the rule, cross-check the result against context the evaluator cannot see, and explain what
formed.

**Advisory only.** Nothing here sizes a position, places an order, or manages a trade.

> ⚠️ Educational and experimental engineering content, not financial advice. CFDs are complex,
> leveraged instruments and the large majority of retail accounts lose money. A rule an agent can
> apply reproducibly is not an edge. Run it on a demo account. See [DISCLAIMER](#disclaimer).

## Strategies

| Skill | Command | What it reports |
|---|---|---|
| `orb-strategy` | `orb-evaluate` | Open range breakout: `none` · `building` · `armed` · `breakout_long` / `breakout_short` · `invalidated` |
| `coinflip-strategy` | `coinflip-evaluate` | The null hypothesis. A random direction at a fixed reward-to-risk, plus the expectancy that proves it has no edge. |

`coinflip` is the control group, not a trading idea. It exists because reward-to-risk is widely
mistaken for an edge, and it is the cleanest way to show it is not: on a driftless walk the
probability of reaching a `+rr × R` target before a `-1R` stop is exactly `1 / (1 + rr)`, so
expectancy before costs is zero at *every* ratio, and after costs it equals exactly `-cost_r`.
Any strategy that cannot beat this coin, out of sample and net of spread, has no edge. See
[`references/expectancy.md`](skills/coinflip-strategy/references/expectancy.md).

## Install

Requires Python 3.11+.

```bash
python -m pip install -e ".[dev]"
orb-evaluate --help
python -m pytest
```

Install the Agent Skill into your runtime (`claude-code`, `codex`, `hermes`, or `openclaw`):

```bash
python scripts/install_skill.py --runtime claude-code
python scripts/install_skill.py --runtime claude-code --verify
```

## Run

```bash
cp skills/orb-strategy/config.example.yaml config.yaml
orb-evaluate --config config.yaml --input tests/fixtures/breakout-long.json --pretty
```

The bundled fixture is synthetic. It exists to prove the evaluator is deterministic — it is not a
backtest and not evidence of profitability.

For live advisory use, gather completed bars with a read-only market-data tool, write the shape
documented in [`skills/orb-strategy/references/input-format.md`](skills/orb-strategy/references/input-format.md),
and run the CLI. Narrate its JSON; do not reimplement its arithmetic in the model.

## Layout

```
src/mt5_agent_strategies/
  core/          bars, timestamps, session math, ATR — shared by every strategy
  registry.py    the Strategy protocol and the name → strategy lookup
  strategies/
    orb/         config + evaluator for the open range breakout
  cli.py         one console script per strategy
skills/
  orb-strategy/  SKILL.md, config example, references — what an agent installs
```

`core/` owns everything a strategy shouldn't have to re-solve: timezone-aware session opens that
track daylight saving, completed-bar selection against an explicit `as_of`, and decimal parsing
that preserves broker precision.

## Adding a strategy

A new strategy is one package under `strategies/`, one skill under `skills/`, and one line in each
of `strategies/__init__.py` and `pyproject.toml`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Related

- [`mt5-trading-mcp`](https://github.com/vincentwongso/mt5-trading-mcp) — read-only MetaTrader 5 access for agents
- [Teaching your AI agent a trading strategy](https://engineering.fintrixmarkets.com/posts/orb-strategy-part-3/) — the article this repo accompanies

## Disclaimer

This is educational and experimental engineering content, not financial advice. Everything is
designed for a demo account. The open range breakout can fail, breakouts fake out, defined risk is
not low risk, and a rule that behaves on recorded sessions can behave very differently live. The
evaluator does not inspect news, market calendars, spreads, positions, equity, or higher-timeframe
structure — those checks stay with you. Run it locally, understand how it works, keep it advisory,
and never point it at real capital you cannot afford to lose.

Licensed under the [MIT License](LICENSE).
