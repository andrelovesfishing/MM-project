"""Fill model: how a resting order moves up the queue and gets filled.

Pure functions of (order, event), with no strategy or loop state, so every fill rule
can be tested on hand-built events. All three historical fill bugs lived in logic that
was tangled into the backtest loop. See docs/adr/0002.
"""

from dataclasses import dataclass, replace

from mm.data import CANCEL, DELETE, EXECUTE, EXECUTE_HIDDEN

BID, ASK = 1, -1  # same sign convention as LOBSTER's direction column


@dataclass(frozen=True)
class RestingOrder:
    side: int
    price: int
    size: int
    ahead: int          # visible shares queued in front of us; negative once trades reach us
    forced: bool = False


def queue_ahead(side: int, price: int, px_levels, sz_levels) -> int:
    """Displayed size at our price on our side of the book: we join the back of that queue."""
    for level_px, level_sz in zip(px_levels, sz_levels):
        if level_px == price:
            return int(level_sz)
    # Deeper than the visible book: assume the last visible level's size is ahead of us.
    if side * (px_levels[-1] - price) > 0:
        return int(sz_levels[-1])
    return 0


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


def on_event(order: RestingOrder, event_type: int, price: int, size: int, direction: int):
    """Apply one market event to our order. Returns (order or None if fully filled, shares filled)."""
    # LOBSTER direction is the side of the book the event happened on. For executions
    # that is the resting order that got hit, so a trade on our side can reach us.
    if direction != order.side:
        return order, 0

    if event_type in (CANCEL, DELETE):
        if price == order.price:
            return replace(order, ahead=order.ahead - size), 0
        return order, 0

    if event_type in (EXECUTE, EXECUTE_HIDDEN):
        # A trade at our price, or through it, eats the queue in front of us first.
        if order.side * (order.price - price) < 0:
            return order, 0
        ahead = order.ahead - size
        if ahead >= 0:
            return replace(order, ahead=ahead), 0
        filled = min(order.size, size, -ahead)
        remaining = order.size - filled
        return (replace(order, ahead=ahead, size=remaining) if remaining > 0 else None), filled

    return order, 0
