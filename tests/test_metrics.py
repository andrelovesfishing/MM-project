import numpy as np
import pytest

from mm.metrics import attribution, sharpe_annualized


def test_sharpe_uses_one_minute_bars_and_annualises_by_trading_minutes():
    time = np.arange(0.0, 601.0, 1.0)                        # ten minutes, sampled every second
    per_minute = np.cumsum([0] + [1.0, 3.0] * 5)             # P&L changes of 1, 3, 1, 3... per minute
    series = np.interp(time, np.arange(0.0, 601.0, 60.0), per_minute)
    assert sharpe_annualized(time, series) == pytest.approx(2.0 * np.sqrt(252 * 390))


def test_sharpe_is_nan_for_flat_pnl():
    assert np.isnan(sharpe_annualized(np.arange(0.0, 601.0), np.zeros(601)))


def moving_market(bids):
    """A one-cent-wide book whose bid follows `bids`, one event each."""
    from dataclasses import replace
    from conftest import make_market
    from mm.data import BUY, SUBMIT
    m = make_market([(SUBMIT, 1, 1, BUY)] * len(bids), n_levels=1)
    bid = np.array(bids).reshape(-1, 1)
    return replace(m, bid_px=bid, ask_px=bid + 100, _cache={})


def fills_result(idx, side, price, size, forced):
    from mm.engine import Result
    cols = dict(idx=idx, side=side, price=price, size=size, forced=forced)
    return Result(fills={k: np.array(v) for k, v in cols.items()}, quotes=[], samples={})


def test_attribution_splits_a_fill_into_spread_adverse_selection_and_inventory():
    # Buy 10 at the bid with mid 50 above. One event later mid is 100 lower; at the close it is 350 above that.
    m = moving_market([1_000_000, 999_900, 1_000_250])
    r = fills_result([0], [1], [1_000_000], [10], [False])
    a = attribution(r, m, horizon=1)
    assert a["pnl_spread_passive"] == pytest.approx(10 * 50 / 10_000)
    assert a["pnl_adverse_selection"] == pytest.approx(10 * -100 / 10_000)
    assert a["pnl_inventory"] == pytest.approx(10 * 350 / 10_000)
    assert a["pnl_crossing"] == 0
    assert a["pnl_total_at_close"] == pytest.approx(10 * 300 / 10_000)


def test_attribution_counts_shares_and_adverse_selection_on_passive_fills():
    # Mid rises 100 then 200: the passive buy of 10 gains 100 each, the forced sell of 4 loses 200 each
    m = moving_market([1_000_000, 1_000_100, 1_000_300])
    r = fills_result([0, 1, 2], [1, -1, 1], [1_000_000] * 3, [10, 4, 7], [False, True, False])
    a = attribution(r, m, horizon=1)
    assert (a["shares_passive"], a["shares_forced"]) == (17, 4)
    assert a["pnl_adverse_selection_passive"] == pytest.approx(10 * 100 / 10_000)
    assert a["pnl_adverse_selection"] == pytest.approx((10 * 100 - 4 * 200) / 10_000)


def test_attribution_components_sum_to_total_pnl():
    rng = np.random.default_rng(0)
    m = moving_market(1_000_000 + 100 * rng.integers(-20, 20, 300))
    n = 40
    r = fills_result(np.sort(rng.integers(0, 300, n)), rng.choice([-1, 1], n),
                     1_000_000 + 100 * rng.integers(-20, 20, n), rng.integers(1, 50, n), rng.random(n) < 0.3)
    a = attribution(r, m, horizon=25)  # some fills are within 25 events of the close
    parts = a["pnl_spread_passive"] + a["pnl_crossing"] + a["pnl_adverse_selection"] + a["pnl_inventory"]
    cash = -np.sum(r.fills["side"] * r.fills["size"] * r.fills["price"])
    inventory = np.sum(r.fills["side"] * r.fills["size"])
    assert parts == pytest.approx(a["pnl_total_at_close"])
    assert a["pnl_total_at_close"] == pytest.approx((cash + inventory * m.mid[-1]) / 10_000)


def test_attribution_total_matches_the_engine_ledger():
    from conftest import ASK0, BID0, make_market
    from mm import engine
    from mm.data import BUY, EXECUTE, SELL, SUBMIT
    from mm.strategy import Quote, Quotes

    class Both:
        inventory_limit = 1000

        def quote(self, market, i, inventory):
            return Quotes(Quote(BID0, 20), Quote(ASK0, 30))

    events = [(SUBMIT, BID0, 1, BUY), (EXECUTE, BID0, 400, BUY), (EXECUTE, ASK0, 210, SELL), (SUBMIT, BID0, 1, BUY)]
    r = engine.run(make_market(events), Both(), engine.Timer(1e9), latency_events=0, sample_every=1)
    m = make_market(events)
    ledger_total = (r.samples["cash"][-1] + r.samples["inventory"][-1] * m.mid[-1]) / 10_000
    assert attribution(r, m)["pnl_total_at_close"] == pytest.approx(ledger_total)
