"""Event loop: replay the session, route events to the fill model, ask the strategy for
quotes, and apply them after a latency."""

from collections import deque
from dataclasses import dataclass

import numpy as np

from mm.accounting import Ledger
from mm.data import Market
from mm.queue import ASK, BID, FillModel, take
from mm.strategy import Quotes, Strategy


@dataclass(frozen=True)
class Timer:
    """Requote every `seconds` of market time."""
    seconds: float

    def due(self, market: Market, i: int, last: int) -> bool:
        return last < 0 or market.time[i] - market.time[last] >= self.seconds


@dataclass
class Result:
    fills: dict        # arrays: idx, side (+1 buy / -1 sell), price, size, forced
    quotes: list       # (event index, Quotes) per requote decision
    samples: dict      # arrays every sample_every events: idx, inventory, cash, realized, avg_cost


def run(market: Market, strategy: Strategy, requote=Timer(6.0), latency_events: int = 2,
        sample_every: int = 50, fill_model: FillModel = FillModel()) -> Result:
    # Python lists index far faster than NumPy arrays inside a per-event loop.
    etype, price, size, direction, submitted_at = (a.tolist() for a in (
        market.event_type, market.price, market.size, market.direction, market.submitted_at))
    ledger = Ledger()
    orders = {BID: None, ASK: None}
    fills, decisions, samples = [], [], []
    in_flight, last_quote = deque(), -1  # (lands at event, quotes), oldest first
    limit = strategy.inventory_limit

    for i in range(len(market)):
        for side in (BID, ASK):
            order = orders[side]
            if order is not None:
                orders[side], filled = fill_model.on_event(order, etype[i], price[i], size[i], direction[i],
                                                           submitted_at[i])
                if filled:
                    ledger.fill(side, order.price, filled)
                    fills.append((i, side, order.price, filled, order.forced))

        _enforce_limit(orders, ledger.inventory, limit)

        if requote.due(market, i, last_quote):
            last_quote = i
            quotes = strategy.quote(market, i, ledger.inventory)
            decisions.append((i, quotes))
            in_flight.append((i + latency_events, quotes))

        # Each quote lands after its own latency, in the order sent, like messages to an exchange.
        while in_flight and in_flight[0][0] <= i:
            for side, px, qty, forced in _apply(in_flight.popleft()[1], orders, market, i, fill_model):
                ledger.fill(side, px, qty)
                fills.append((i, side, px, qty, forced))
            _enforce_limit(orders, ledger.inventory, limit)  # the quote was decided before recent fills

        if i % sample_every == 0:
            samples.append((i, ledger.inventory, ledger.cash, ledger.realized, ledger.avg_cost))

    fill_cols = ("idx", "side", "price", "size", "forced")
    sample_cols = ("idx", "inventory", "cash", "realized", "avg_cost")
    return Result(
        fills={c: np.array([f[k] for f in fills]) for k, c in enumerate(fill_cols)},
        quotes=decisions,
        samples={c: np.array([s[k] for s in samples]) for k, c in enumerate(sample_cols)},
    )


def _enforce_limit(orders: dict, inventory: int, limit: int):
    """Pull a resting order that would take us past the inventory limit."""
    if inventory >= limit:
        orders[BID] = None
    if inventory <= -limit:
        orders[ASK] = None


def _apply(quotes: Quotes, orders: dict, market: Market, i: int, model: FillModel) -> list:
    """Send quotes to the book as it is when they land. A quote that crosses executes at once against
    the far side and rests any remainder. Returns the immediate fills as (side, price, shares, forced).
    A passive quote keeps its queue place when only its size shrinks (FillModel.replace_order).
    A side with no quote cancels its resting order."""
    books = {BID: (market.bid_px[i], market.bid_sz[i]), ASK: (market.ask_px[i], market.ask_sz[i])}
    taken = []
    for side, q in ((BID, quotes.bid), (ASK, quotes.ask)):
        if q is None:
            orders[side] = None
            continue
        crossed = take(side, q.price, q.size, *books[-side])
        if crossed:
            taken += [(side, px, qty, q.forced) for px, qty in crossed]
            left = q.size - sum(qty for _, qty in crossed)
            orders[side] = model.replace_order(side, None, q.price, left, q.forced, *books[side], i) if left else None
        else:
            orders[side] = model.replace_order(side, orders[side], q.price, q.size, q.forced, *books[side], i)
    return taken
