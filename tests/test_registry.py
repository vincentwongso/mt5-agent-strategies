import pytest

from mt5_agent_strategies import registry
from mt5_agent_strategies.core.errors import StrategyError
from mt5_agent_strategies.strategies.orb import OrbStrategy


def test_orb_is_registered():
    assert "orb" in registry.names()
    assert isinstance(registry.get("orb"), OrbStrategy)


def test_registered_strategies_satisfy_the_protocol():
    for name in registry.names():
        strategy = registry.get(name)
        assert isinstance(strategy, registry.Strategy)
        assert strategy.name == name
        assert strategy.description.strip()


def test_unknown_strategy_lists_the_available_ones():
    with pytest.raises(StrategyError, match="unknown strategy: 'nope'.*available: orb"):
        registry.get("nope")


def test_duplicate_registration_is_rejected():
    with pytest.raises(StrategyError, match="already registered"):
        registry.register(OrbStrategy())
