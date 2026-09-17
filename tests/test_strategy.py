import math

import numpy as np
import pytest
from conftest import ASK0, BID0, make_market

from mm.data import BUY, SUBMIT
from mm.strategy import ASQuoter, OFIGuard, SizeSkew, as_half_spread_ticks


# Book: bid x 300, ask x 200, one tick apart, so the micro-price sits 0.6 ticks above the bid.
@pytest.fixture
def market():
    return make_market([(SUBMIT, BID0, 1, BUY)] * 3)


def plain(**kw):
    return ASQuoter(**{"order_size": 20, "inventory_limit": 100, "inventory_skew": None,
                       "size_skew": None, "ofi_guard": None, **kw})


def with_ofi_z(market, z):
    market.cached(("ofi_z", 50, 200), lambda: np.full(len(market), z))
    return market


def test_as_half_spread_formula():
    assert as_half_spread_ticks(0.1, 3.2) == pytest.approx(20 * math.log(1 + 0.1 / 3.2))


def test_tight_model_spread_quotes_at_the_touch(market):
    q = plain().quote(market, 0, 0)
    assert (q.bid.price, q.ask.price) == (BID0, ASK0)


def test_quotes_never_improve_on_or_cross_the_touch(market):
    q = plain(min_half_spread_ticks=0.0, max_half_spread_ticks=0.0).quote(market, 0, 0)
    assert q.bid.price <= BID0 and q.ask.price >= ASK0


def test_wide_model_spread_joins_the_touch_instead_of_resting_far_back(market):
    q = plain(kappa=0.01).quote(market, 0, 0)
    assert (q.bid.price, q.ask.price, q.n_snapped) == (BID0, ASK0, 2)


def test_rests_behind_touch_when_within_join_distance(market):
    q = plain(kappa=0.01, max_half_spread_ticks=2.0, touch_join_ticks=2.0).quote(market, 0, 0)
    assert q.bid.price == BID0 - 100 and q.ask.price == ASK0 + 200 and q.n_organic == 2


def test_ofi_guard_pulls_back_the_side_about_to_be_run_over(market):
    q = plain(ofi_guard=OFIGuard(widen_ticks=4.0)).quote(with_ofi_z(market, -3.0), 0, 0)
    assert q.bid.price == BID0 - 300 and q.ask.price == ASK0  # selling pressure: back off the bid only


def test_size_skew_shrinks_the_side_that_adds_to_inventory(market):
    q = plain(size_skew=SizeSkew(min_frac=0.2)).quote(market, 0, 25)  # half way to flatten at 50
    assert (q.bid.size, q.ask.size) == (12, 20)


def test_no_bid_at_the_long_limit(market):
    assert plain().quote(market, 0, 100).bid is None


def test_forced_flatten_crosses_to_the_far_touch(market):
    q = plain().quote(market, 0, -60)
    assert q.ask is None and (q.bid.price, q.bid.forced) == (ASK0, True)
