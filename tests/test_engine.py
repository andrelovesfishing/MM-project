from dataclasses import dataclass

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


def test_quote_only_rests_after_the_latency():
    # Trade at event 1 would reach us if we were resting; the quote only lands at event 2.
    r = run([NOOP, hit_bid(1000), NOOP], latency_events=2)
    assert len(r.fills["idx"]) == 0


def test_we_join_behind_displayed_size_and_fill_after_it_trades():
    r = run([NOOP, hit_bid(310)], latency_events=0)
    assert r.fills["size"].tolist() == [10] and r.fills["side"].tolist() == [1]


def test_fills_update_inventory_and_cash():
    r = run([NOOP, hit_bid(1000), (EXECUTE, ASK0, 1000, SELL)], latency_events=0, sample_every=1)
    assert r.samples["inventory"].tolist() == [0, 20, 0]
    assert r.samples["cash"][-1] == 20 * (ASK0 - BID0)


def test_resting_bid_is_pulled_at_the_long_limit():
    r = run([NOOP, hit_bid(1000), hit_bid(1000)], FixedQuotes(size=20, inventory_limit=10), latency_events=0)
    assert r.fills["size"].tolist() == [20]


def test_timer_requotes_on_market_time():
    events = [NOOP] * 5
    r = engine.run(make_market(events, times=[0.0, 1.0, 6.0, 6.5, 12.0]), FixedQuotes(), engine.Timer(6.0))
    assert [i for i, _ in r.quotes] == [0, 2, 4]
