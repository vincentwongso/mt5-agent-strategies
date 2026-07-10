"""Importing this package registers every bundled strategy.

To add a strategy, create a sibling package that calls `registry.register(...)` at
import time and add one line here. See CONTRIBUTING.md.
"""

from . import orb  # noqa: F401  registers "orb"

__all__ = ["orb"]
