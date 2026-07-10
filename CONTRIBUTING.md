# Adding a strategy

Every strategy is a package under `src/mt5_agent_strategies/strategies/` plus a skill under
`skills/`. Nothing else in the repo needs to change beyond two one-line registrations.

Below, `<name>` is the strategy id (`orb`), and `<name>-strategy` is its skill directory
(`orb-strategy`). Use `orb` as the worked reference — it is deliberately small.

## The contract

A strategy is any object satisfying `registry.Strategy`:

```python
class Strategy(Protocol):
    name: str          # "orb"
    description: str   # "Open range breakout"

    def load_config(self, path: str | Path) -> Sequence[Any]: ...
    def evaluate_symbol(self, config: Any, data: InputData) -> dict[str, Any]: ...
```

`evaluate_symbol` **must be a pure function of `(config, data)`**. No clocks, no network, no
randomness, no reading files. The `as_of` timestamp on `InputData` is the only "now" that exists.
This is the property the whole repo sells: the same bars and the same `as_of` always produce the
same output. A test asserts it; do not break it.

## Steps

**1. Reuse the core.** `mt5_agent_strategies.core` already solves the boring, easy-to-get-wrong
parts. Prefer these over hand-rolling:

| Helper | Use it for |
|---|---|
| `session_open_utc(as_of, timezone, session_open)` | Today's session open in UTC, correct across daylight saving |
| `completed_bars(bars, as_of, bar_minutes)` | Dropping the in-progress bar |
| `expected_bar_times(start, end, step)` | Which bars *should* exist in a window |
| `true_range_atr(daily_bars, period, before)` | Average true range from completed daily bars |
| `number(...)`, `iso_utc(...)` | JSON-safe decimals and timestamps |
| `load_symbol_settings(path)` | Reading `defaults` + per-symbol overrides out of YAML |
| `decimal`, `positive_int`, `clock`, `timezone_name` | Validating config values with good error messages |

Never hard-code a UTC session hour. Anchor to an IANA timezone or the open drifts an hour twice a
year.

**2. Write the package.**

```
src/mt5_agent_strategies/strategies/<name>/
  __init__.py     defines the Strategy class, calls register(...)
  config.py       dataclass + load(path) -> tuple[Config, ...]
  evaluator.py    evaluate_symbol(config, data) -> dict
```

Raise `core.errors.StrategyError` for anything malformed. The CLI turns it into a JSON error on
stderr with exit code 2, so a bad config never looks like a signal.

**3. Register it.** In `strategies/__init__.py`:

```python
from . import <name>  # noqa: F401  registers "<name>"
```

**4. Give it a command.** In `pyproject.toml` under `[project.scripts]`:

```toml
<name>-evaluate = "mt5_agent_strategies.cli:<name>_evaluate"
```

and in `cli.py`:

```python
<name>_evaluate = make_entrypoint("<name>")
```

**5. Write the skill.**

```
skills/<name>-strategy/
  SKILL.md              frontmatter `name:` must equal the directory name
  config.example.yaml
  references/*.md       at least one
```

`SKILL.md` must state the advisory-only boundary — a test checks for it. Tell the agent to treat
the CLI as the source of truth and never to estimate levels from prose or a chart. The installer
discovers `skills/*/SKILL.md` automatically, so there is nothing to wire up.

Put everything the evaluator *cannot* see into `references/`: news, holidays, spread, exposure,
drawdown, higher-timeframe structure. Those checks belong to the agent and the user, and the skill
must say so explicitly rather than letting OHLC output imply they passed.

**6. Fail closed.** When required bars are missing or a filter cannot be computed, return an
`invalidated` state with a machine-readable `reason` — never a guess, and never silently skip.
Once a signal is confirmed, later missing data must not retract it; see
`test_gap_after_confirmed_break_does_not_erase_it` for the shape of that rule.

## Checklist

- [ ] `evaluate_symbol` is pure; `as_of` is the only clock
- [ ] Session opens anchored to an IANA timezone, not a fixed UTC hour
- [ ] Only completed bars confirm anything
- [ ] Missing data yields `invalidated` with a `reason`, never a guess
- [ ] A confirmed signal is stable under every later `as_of`
- [ ] Config errors raise `StrategyError` with a field-qualified message
- [ ] `SKILL.md` frontmatter `name` matches its directory and states the advisory boundary
- [ ] No sizing, no orders, no trade management — anywhere
- [ ] Fixtures described as synthetic, never as a backtest or evidence of an edge

## Verify

```bash
python -m pytest          # includes the skill contract + registry tests
ruff check . && ruff format --check .
python scripts/install_skill.py --list
python scripts/install_skill.py --target /tmp/skills && python scripts/install_skill.py --target /tmp/skills --verify
```

`tests/test_skill.py` and `tests/test_registry.py` are parametrised over whatever is registered and
bundled, so a new strategy is covered by them the moment it exists. Add its own behaviour tests
alongside — the state machine, the boundary conditions, and at least one determinism test.
