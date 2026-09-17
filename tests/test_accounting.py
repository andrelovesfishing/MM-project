import random

import pytest

from mm.accounting import Ledger


def test_adding_to_a_position_averages_cost():
    led = Ledger()
    led.fill(1, 100, 10)
    led.fill(1, 110, 30)
    assert (led.inventory, led.avg_cost, led.realized, led.cash) == (40, 107.5, 0.0, -4300)


def test_reducing_realizes_against_average_cost():
    led = Ledger()
    led.fill(-1, 100, 10)
    led.fill(1, 90, 4)
    assert (led.inventory, led.avg_cost, led.realized) == (-6, 100, 40)


def test_flipping_through_flat_resets_cost_to_fill_price():
    led = Ledger()
    led.fill(1, 100, 10)
    led.fill(-1, 105, 25)
    assert (led.inventory, led.avg_cost, led.realized) == (-15, 105, 50)


def test_mark_to_market_splits_into_realized_plus_unrealized():
    rng = random.Random(0)
    led = Ledger()
    for _ in range(2000):
        led.fill(rng.choice((1, -1)), rng.randint(9_900, 10_100), rng.randint(1, 50))
        mark = rng.uniform(9_900, 10_100)
        assert led.total(mark) == pytest.approx(led.realized + led.unrealized(mark), rel=1e-12, abs=1e-6)
