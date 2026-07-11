import random
from datetime import datetime, timedelta

import pytest

from attractors.clock import SimClock


def make_clock(iso="2026-07-13T09:00:00"):
    return SimClock(datetime.fromisoformat(iso), random.Random(0))


def test_advance():
    c = make_clock()
    c.advance(timedelta(minutes=10))
    assert c.stamp() == "2026-07-13 09:10"
    assert c.elapsed_hours() == pytest.approx(1 / 6)


def test_no_backwards():
    c = make_clock()
    with pytest.raises(ValueError):
        c.advance(timedelta(seconds=-1))


def test_next_morning_same_day_boundary():
    c = make_clock("2026-07-13T07:00:00")
    c.advance_to_next_morning(8)
    assert c.stamp() == "2026-07-13 08:00"


def test_next_morning_after_hour():
    c = make_clock("2026-07-13T09:00:00")
    c.advance_to_next_morning(8)
    assert c.stamp() == "2026-07-14 08:00"


def test_jitter_deterministic():
    a, b = make_clock(), make_clock()
    assert a.jitter(20, 90) == b.jitter(20, 90)


def test_sim_date():
    assert make_clock().sim_date == "2026-07-13"
