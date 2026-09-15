"""Generates the outbound/return date candidates for upcoming weekends.

A "weekend" is anchored on a Saturday. Outbound travel can happen on the
Friday evening before it or the Saturday itself; return travel can happen
on the Sunday or the Monday morning after it. Which days are actually
considered is controlled by the ``outbound_days`` / ``return_days`` config.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# Offsets are relative to the anchor Saturday of the weekend.
_OUTBOUND_OFFSETS = {"FRI": -1, "SAT": 0}
_RETURN_OFFSETS = {"SUN": 1, "MON": 2}

ALLOWED_OUTBOUND_DAYS = frozenset(_OUTBOUND_OFFSETS)
ALLOWED_RETURN_DAYS = frozenset(_RETURN_OFFSETS)


@dataclass(frozen=True)
class WeekendWindow:
    label: str
    saturday: date
    outbound_dates: tuple[date, ...]
    return_dates: tuple[date, ...]


def next_saturday(from_date: date) -> date:
    """Return ``from_date`` itself if it's a Saturday, otherwise the next one."""
    days_ahead = (5 - from_date.weekday()) % 7  # Monday=0 ... Saturday=5
    return from_date + timedelta(days=days_ahead)


def upcoming_weekends(
    today: date,
    lookahead_weekends: int,
    outbound_days: list[str],
    return_days: list[str],
) -> list[WeekendWindow]:
    """Return the next ``lookahead_weekends`` weekend windows from ``today``."""
    unknown_outbound = set(outbound_days) - ALLOWED_OUTBOUND_DAYS
    unknown_return = set(return_days) - ALLOWED_RETURN_DAYS
    if unknown_outbound:
        raise ValueError(f"Unsupported outbound_days: {sorted(unknown_outbound)}")
    if unknown_return:
        raise ValueError(f"Unsupported return_days: {sorted(unknown_return)}")

    first_saturday = next_saturday(today)
    windows: list[WeekendWindow] = []
    for i in range(lookahead_weekends):
        saturday = first_saturday + timedelta(weeks=i)
        outbound_dates = tuple(
            sorted(
                saturday + timedelta(days=_OUTBOUND_OFFSETS[d])
                for d in outbound_days
                if saturday + timedelta(days=_OUTBOUND_OFFSETS[d]) >= today
            )
        )
        return_dates = tuple(
            sorted(saturday + timedelta(days=_RETURN_OFFSETS[d]) for d in return_days)
        )
        if outbound_dates and return_dates:
            windows.append(
                WeekendWindow(
                    label=f"weekend of {saturday.isoformat()}",
                    saturday=saturday,
                    outbound_dates=outbound_dates,
                    return_dates=return_dates,
                )
            )
    return windows
