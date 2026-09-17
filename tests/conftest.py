import numpy as np

from mm.data import Market

# A one-cent-wide AAPL-like book: bid 100.00 x 300, ask 100.01 x 200, then 1 cent per level.
BID0, ASK0 = 1_000_000, 1_000_100


def make_market(events, n_levels=3, bid_sz=300, ask_sz=200, times=None, order_ids=None):
    """events: list of (event_type, price, size, direction). The book stays constant."""
    n = len(events)
    et, px, sz, d = (np.array(col) for col in zip(*events))
    level = np.arange(n_levels) * 100
    return Market(
        ticker="TEST",
        time=np.array(times if times is not None else np.arange(n, dtype=float)),
        event_type=et, order_id=np.array(order_ids) if order_ids is not None else np.arange(n), size=sz, price=px, direction=d,
        ask_px=np.tile(ASK0 + level, (n, 1)), ask_sz=np.full((n, n_levels), ask_sz),
        bid_px=np.tile(BID0 - level, (n, 1)), bid_sz=np.full((n, n_levels), bid_sz),
    )
