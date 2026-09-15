from datetime import date, timedelta

import pytest

from cheaptrains.dates import next_saturday, upcoming_weekends


def test_upcoming_weekends_basic():
    today = date(2026, 9, 15)
    windows = upcoming_weekends(
        today, lookahead_weekends=3, outbound_days=["FRI", "SAT"], return_days=["SUN", "MON"]
    )

    assert len(windows) == 3

    first_saturday = next_saturday(today)
    assert windows[0].saturday == first_saturday
    assert windows[0].outbound_dates == (
        first_saturday - timedelta(days=1),
        first_saturday,
    )
    assert windows[0].return_dates == (
        first_saturday + timedelta(days=1),
        first_saturday + timedelta(days=2),
    )
    assert windows[1].saturday == first_saturday + timedelta(days=7)
    assert windows[2].saturday == first_saturday + timedelta(days=14)


def test_past_outbound_dates_are_filtered():
    saturday = next_saturday(date(2026, 1, 1))
    windows = upcoming_weekends(
        saturday, lookahead_weekends=1, outbound_days=["FRI", "SAT"], return_days=["SUN", "MON"]
    )
    # "today" is the Saturday itself, so Friday of that weekend has already passed.
    assert windows[0].outbound_dates == (saturday,)


def test_saturday_only_outbound():
    today = date(2026, 9, 15)
    windows = upcoming_weekends(
        today, lookahead_weekends=1, outbound_days=["SAT"], return_days=["SUN"]
    )
    first_saturday = next_saturday(today)
    assert windows[0].outbound_dates == (first_saturday,)
    assert windows[0].return_dates == (first_saturday + timedelta(days=1),)


def test_invalid_days_raise():
    today = date(2026, 9, 15)
    with pytest.raises(ValueError):
        upcoming_weekends(today, 1, outbound_days=["WED"], return_days=["SUN"])
    with pytest.raises(ValueError):
        upcoming_weekends(today, 1, outbound_days=["FRI"], return_days=["TUE"])
