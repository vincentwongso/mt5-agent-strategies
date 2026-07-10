# AGENTS.md

Setup instructions for coding agents asked to install and run this repository.

## What this is

`orb-strategy` is an advisory-only Agent Skill and deterministic Python CLI. It turns timestamped OHLC bars into one technical ORB state per configured symbol. It never sizes or places trades.

## Install the CLI

Requires Python 3.11+.

```bash
python -m pip install -e ".[dev]"
```

Verify the command without broker access or network calls:

```bash
orb-evaluate --help
python -m pytest
```

Expect the help output to list `--config`, `--input`, and `--pretty`, followed by a green offline test suite.

## Install the Agent Skill

Use the installer so the same source works with supported agent homes:

```bash
python scripts/install_skill.py --runtime hermes
```

Valid runtimes are `openclaw`, `hermes`, `claude-code`, and `codex`. The installer copies `skills/orb-strategy` to that runtime's user skill directory and refuses to overwrite an existing copy unless `--force` is passed.

Verify the destination without modifying it again:

```bash
python scripts/install_skill.py --runtime hermes --verify
```

For a project-local or test install, provide an explicit directory:

```bash
python scripts/install_skill.py --target /absolute/path/to/skills
python scripts/install_skill.py --target /absolute/path/to/skills --verify
```

## Configure and run

```bash
cp skills/orb-strategy/config.example.yaml config.yaml
orb-evaluate --config config.yaml --input tests/fixtures/breakout-long.json --pretty
```

The fixture is synthetic and exists only to verify the deterministic contract. Do not describe it as a backtest or evidence of profitability.

For live advisory use, gather completed M5 and D1 bars with a read-only market-data tool, write the input shape documented in `skills/orb-strategy/references/input-format.md`, and run the CLI. Narrate its JSON; do not reimplement its arithmetic in the model.

## Boundaries

- Advisory only: no order placement, position sizing, or trade management.
- Never commit credentials or broker account details.
- Preserve timezone-aware source timestamps.
- Contextual disqualifiers such as news, holidays, spread, exposure, and drawdown remain separate checks.
