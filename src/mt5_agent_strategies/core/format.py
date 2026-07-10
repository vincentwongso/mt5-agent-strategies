from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal


def number(value: Decimal) -> int | float:
    """Render a Decimal as the narrowest JSON number that displays it cleanly."""
    return int(value) if value == value.to_integral() else float(value)


def iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
