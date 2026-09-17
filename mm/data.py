"""LOBSTER data as plain NumPy arrays, one ticker at a time.

Prices stay in LOBSTER's own integer units (1/10,000 of a dollar) everywhere inside
the package. Dollars appear only when results are reported. See docs/adr/0001.
"""

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import numpy as np
import polars as pl

from mm import signals

PX_PER_DOLLAR = 10_000
TICK = 100  # one cent

# LOBSTER event types
SUBMIT, CANCEL, DELETE, EXECUTE, EXECUTE_HIDDEN, HALT = 1, 2, 3, 4, 5, 7
# LOBSTER direction: the side of the order the event belongs to
BUY, SELL = 1, -1


def dollars(px):
    return px / PX_PER_DOLLAR


@dataclass(frozen=True, eq=False)
class Market:
    """One session of events plus the book state after each event (row i = after event i)."""

    ticker: str
    time: np.ndarray        # seconds after midnight
    event_type: np.ndarray
    order_id: np.ndarray
    size: np.ndarray
    price: np.ndarray
    direction: np.ndarray
    ask_px: np.ndarray      # (n, levels), best level first
    ask_sz: np.ndarray
    bid_px: np.ndarray
    bid_sz: np.ndarray
    _cache: dict = field(default_factory=dict, repr=False)

    def __len__(self):
        return len(self.time)

    @property
    def best_bid(self):
        return self.bid_px[:, 0]

    @property
    def best_ask(self):
        return self.ask_px[:, 0]

    @cached_property
    def mid(self):
        return (self.best_ask + self.best_bid) / 2.0

    @cached_property
    def micro(self):
        """Mid weighted towards the side with less queued size, where price is likelier to move."""
        bv, av = self.bid_sz[:, 0], self.ask_sz[:, 0]
        total = bv + av
        with np.errstate(invalid="ignore", divide="ignore"):
            micro = (bv * self.best_ask + av * self.best_bid) / total
        return np.where(total > 0, micro, self.mid)

    @cached_property
    def ofi(self):
        return signals.ofi(self.best_bid, self.bid_sz[:, 0], self.best_ask, self.ask_sz[:, 0])

    def cached(self, key, compute):
        """Memoise a derived feature on this market, so strategies sharing it compute it once."""
        if key not in self._cache:
            self._cache[key] = compute()
        return self._cache[key]


def load(ticker: str, data_dir: str | Path = "data", levels: int = 10,
         date: str = "2012-06-21") -> Market:
    stem = Path(data_dir) / f"{ticker}_{date}_34200000_57600000"
    msg = pl.read_csv(
        f"{stem}_message_{levels}.csv", has_header=False,
        new_columns=["time", "event_type", "order_id", "size", "price", "direction"],
        schema_overrides={"time": pl.Float64},
    )
    book = pl.read_csv(f"{stem}_orderbook_{levels}.csv", has_header=False).to_numpy()
    if len(msg) != len(book):
        raise ValueError(f"{ticker}: message and orderbook files have different lengths")

    # Columns repeat as ask price, ask size, bid price, bid size per level. Views, not copies.
    return Market(
        ticker=ticker,
        time=msg["time"].to_numpy(),
        event_type=msg["event_type"].to_numpy(),
        order_id=msg["order_id"].to_numpy(),
        size=msg["size"].to_numpy(),
        price=msg["price"].to_numpy(),
        direction=msg["direction"].to_numpy(),
        ask_px=book[:, 0::4], ask_sz=book[:, 1::4],
        bid_px=book[:, 2::4], bid_sz=book[:, 3::4],
    )


def liquidity_profile(m: Market) -> dict:
    return {
        "avg_touch_depth_shares": float((m.bid_sz[:, 0].mean() + m.ask_sz[:, 0].mean()) / 2.0),
        "event_rate_per_sec": len(m) / (m.time[-1] - m.time[0]),
        "avg_mid_price": float(dollars(m.mid).mean()),
        "session_length_sec": m.time[-1] - m.time[0],
    }
