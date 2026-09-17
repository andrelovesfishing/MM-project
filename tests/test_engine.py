from dataclasses import dataclass

import pytest

from conftest import ASK0, BID0, make_market

from mm import engine
from mm.data import BUY, EXECUTE, SELL, SUBMIT
from mm.strategy import Quote, Quotes


@dataclass
class FixedQuotes:
    bid: int | None = BID0
    ask: int | None = ASK0
    size: int = 20
    inventory_limit: int = 1000

    def quote(self, market, i, inventory):
        return Quotes(Quote(self.bid, self.size) if self.bid else None,
                      Quote(self.ask, self.size) if self.ask else None)


NOOP = (SUBMIT, BID0 - 500, 1, BUY)


def hit_bid(size):
    return (EXECUTE, BID0, size, BUY)


def run(events, strategy=None, **kw):
    kw.setdefault("requote", engine.Timer(1e9))  # quote once, on the first event
    return engine.run(make_market(events, bid_sz=300), strategy or FixedQuotes(), **kw)


def test_quote_lands_after_the_event_at_the_latency():
    r = run([NOOP, NOOP, hit_bid(1000), hit_bid(1000)], latency_events=2)
    assert r.fills["idx"].tolist() == [3]


def test_we_join_behind_displayed_size_and_fill_after_it_trades():
    r = run([NOOP, hit_bid(310)], latency_events=0)
    assert r.fills["size"].tolist() == [10] and r.fills["side"].tolist() == [1]


def test_fills_update_inventory_and_cash():
    r = run([NOOP, hit_bid(1000), (EXECUTE, ASK0, 1000, SELL)], latency_events=0, sample_every=1)
    assert r.samples["inventory"].tolist() == [0, 20, 0]
    assert r.samples["cash"][-1] == 20 * (ASK0 - BID0)


def test_resting_bid_is_pulled_at_the_long_limit():
    r = run([NOOP, hit_bid(310), hit_bid(1000)], FixedQuotes(size=20, inventory_limit=10), latency_events=0)
    assert r.fills["size"].tolist() == [10]


def test_resting_ask_is_pulled_at_the_short_limit():
    lift = (EXECUTE, ASK0, 210, SELL)  # 200 displayed ahead of us on the ask
    r = run([NOOP, lift, (EXECUTE, ASK0, 1000, SELL)], FixedQuotes(size=20, inventory_limit=10), latency_events=0)
    assert r.fills["size"].tolist() == [10]


def test_requote_at_same_price_keeps_queue_place():
    # 300 ahead; 100 trade away, then a requote at the same price must not reset us to the back.
    events = [NOOP, hit_bid(100), hit_bid(210)]
    r = engine.run(make_market(events, bid_sz=300), FixedQuotes(), engine.Timer(1.0), latency_events=0)
    assert r.fills["size"].tolist() == [10]


@pytest.mark.xfail(strict=True, reason="known: a delayed quote can land after the limit is hit (docs/parity.md)")
def test_delayed_quote_cannot_breach_the_limit():
    events = [NOOP, NOOP, NOOP, NOOP, NOOP, hit_bid(1000), NOOP, hit_bid(1000)]
    m = make_market(events, bid_sz=0, times=[0, 1, 2, 3, 10, 10.5, 11, 12])
    r = engine.run(m, FixedQuotes(size=20, inventory_limit=20), engine.Timer(6.0), latency_events=2,
                   sample_every=1)
    assert r.samples["inventory"].max() <= 20


@pytest.mark.xfail(strict=True, reason="known: requotes faster than the latency keep replacing the pending quote")
def test_quotes_land_even_when_requotes_come_every_event():
    events = [NOOP, hit_bid(1000)] * 5
    m = make_market(events, bid_sz=0, times=[7.0 * k for k in range(10)])
    r = engine.run(m, FixedQuotes(), engine.Timer(6.0), latency_events=2, sample_every=1)
    assert len(r.fills["idx"]) > 0


def test_timer_requotes_on_market_time():
    events = [NOOP] * 5
    r = engine.run(make_market(events, times=[0.0, 1.0, 6.0, 6.5, 12.0]), FixedQuotes(), engine.Timer(6.0))
    assert [i for i, _ in r.quotes] == [0, 2, 4]
