"""Fill model: how a resting order moves up the queue and gets filled.

Pure functions of (order, event), with no strategy or loop state, so every fill rule
can be tested on hand-built events. All three historical fill bugs lived in logic that
was tangled into the backtest loop. See docs/adr/0002.

Our order was never really in the book, so some rules are assumptions the data can't
settle. Those are FillModel switches, bracketed by the PESSIMISTIC and OPTIMISTIC presets
(fewest and most generous fills; not necessarily worst and best P&L).
"""

from dataclasses import dataclass, replace
from typing import Literal

from mm.data import CANCEL, DELETE, EXECUTE, EXECUTE_HIDDEN

BID, ASK = 1, -1  # same sign convention as LOBSTER's direction column


@dataclass(frozen=True)
class RestingOrder:
    side: int
    price: int
    size: int
    ahead: int          # visible shares queued in front of us; negative once trades reach us
    forced: bool = False
    placed_at: int = -1  # event index we joined the queue after


@dataclass(frozen=True)
class FillModel:
    # Who a cancel at our price removes: everyone "ahead" of us, nobody ("behind"), or
    # "exact": ahead only if that order was submitted before we joined, found by LOBSTER order id.
    cancels: Literal["ahead", "behind", "exact"] = "ahead"
    # Hidden (type 5) executions at our price also shorten the visible queue in front of us.
    hidden_trades_eat_queue: bool = True
    # A trade through our price means our level was cleared, so it fills us in full.
    trade_through_fills: bool = False
    # Queue ahead when we rest deeper than the visible book: the last level's size, or none.
    unseen_queue: Literal["last_level", "empty"] = "last_level"

    def queue_ahead(self, side: int, price: int, px_levels, sz_levels) -> int:
        """Displayed size at our price on our side of the book: we join the back of that queue."""
        for level_px, level_sz in zip(px_levels, sz_levels):
            if level_px == price:
                return int(level_sz)
        if self.unseen_queue == "last_level" and side * (px_levels[-1] - price) > 0:
            return int(sz_levels[-1])
        return 0

    def replace_order(self, side: int, order: RestingOrder | None, price: int, size: int, forced: bool,
                      px_levels, sz_levels, now: int = -1) -> RestingOrder:
        """Exchange priority for a replaced quote: same price and no larger size keeps our queue place,
        a new price or a larger size joins the back of the queue."""
        if order is not None and order.price == price and size <= order.size:
            return replace(order, size=size, forced=forced)
        return RestingOrder(side, price, size, self.queue_ahead(side, price, px_levels, sz_levels), forced, now)

    def on_event(self, order: RestingOrder, event_type: int, price: int, size: int, direction: int,
                 submitted_at: int = -1):
        """Apply one market event to our order. `submitted_at` is the event index where the event's
        order was submitted (-1 before the open). Returns (order or None if fully filled, shares filled)."""
        # LOBSTER direction is the side of the book the event happened on. For executions
        # that is the resting order that got hit, so a trade on our side can reach us.
        if direction != order.side:
            return order, 0

        if event_type in (CANCEL, DELETE):
            if price != order.price or self.cancels == "behind":
                return order, 0
            if self.cancels == "exact" and submitted_at > order.placed_at:
                return order, 0
            return replace(order, ahead=order.ahead - size), 0

        if event_type in (EXECUTE, EXECUTE_HIDDEN):
            through = order.side * (order.price - price)  # > 0: traded through us, 0: at our price
            if through < 0:
                return order, 0
            if through > 0 and self.trade_through_fills:
                return None, order.size
            if through == 0 and event_type == EXECUTE_HIDDEN and not self.hidden_trades_eat_queue:
                return order, 0
            # A trade at our price, or through it, eats the queue in front of us first.
            ahead = order.ahead - size
            if ahead >= 0:
                return replace(order, ahead=ahead), 0
            filled = min(order.size, size, -ahead)
            remaining = order.size - filled
            return (replace(order, ahead=ahead, size=remaining) if remaining > 0 else None), filled

        return order, 0


PESSIMISTIC = FillModel(cancels="behind", hidden_trades_eat_queue=False, trade_through_fills=False,
                        unseen_queue="last_level")
OPTIMISTIC = FillModel(cancels="ahead", hidden_trades_eat_queue=True, trade_through_fills=True,
                       unseen_queue="empty")


def take(side: int, limit: int, size: int, px_levels, sz_levels) -> list[tuple[int, int]]:
    """Fills for a marketable order against the opposite side's visible levels, best first,
    at each level's price and no worse than `limit`: [(price, shares)].
    The recorded book doesn't know we took this liquidity, so later events can reuse it."""
    fills = []
    for level_px, level_sz in zip(px_levels, sz_levels):
        if size <= 0 or side * (limit - level_px) < 0:
            break
        if level_sz > 0:
            qty = min(size, int(level_sz))
            fills.append((int(level_px), qty))
            size -= qty
    return fills
