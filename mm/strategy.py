"""Quoting policy: sees the market and inventory, returns the quotes it wants resting.

The Avellaneda-Stoikov quoter is built from optional components (inventory skew, size
skew, OFI guard). An ablation removes a component with dataclasses.replace instead of
flipping flags inside the pricing code. See docs/adr/0003.
"""

import math
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from mm.data import TICK, Market
from mm.signals import rolling_sum, rolling_zscore


@dataclass(frozen=True)
class Quote:
    price: int
    size: int
    forced: bool = False  # a cross to cut inventory, not a passive quote


@dataclass(frozen=True)
class Quotes:
    bid: Quote | None
    ask: Quote | None
    # Diagnostics on the passive quotes sent, so empty when a forced flatten replaces them
    touch_gaps_ticks: tuple = ()
    n_snapped: int = 0
    n_organic: int = 0


class Strategy(Protocol):
    inventory_limit: int  # the engine pulls resting orders that would breach it

    def quote(self, market: Market, i: int, inventory: int) -> Quotes: ...


@dataclass(frozen=True)
class InventorySkew:
    """Shift the reservation price against inventory, so we lean towards flattening."""
    ticks_per_100_shares: float = 1.0
    max_ticks: float = 3.0

    def shift_ticks(self, gamma: float, inventory: int) -> float:
        raw = gamma * self.ticks_per_100_shares * inventory / 100.0
        return float(np.clip(raw, -self.max_ticks, self.max_ticks))


@dataclass(frozen=True)
class SizeSkew:
    """Shrink the side that would add to inventory, down to min_frac at the flatten threshold."""
    min_frac: float = 0.2

    def sizes(self, order_size: int, inventory: int, flatten_at: float) -> tuple[int, int]:
        imbalance = min(1.0, abs(inventory) / max(1.0, flatten_at))
        shrunk = max(1, int(order_size * (1.0 - imbalance * (1.0 - self.min_frac))))
        if inventory > 0:
            return shrunk, order_size
        if inventory < 0:
            return order_size, shrunk
        return order_size, order_size


@dataclass(frozen=True)
class OFIGuard:
    """Widen the side about to be run over when order flow imbalance is extreme."""
    window: int = 50
    z_window: int = 200
    z_threshold: float = 2.0
    widen_ticks: float = 4.0

    def z(self, market: Market, i: int) -> float:
        return ofi_z(market, self.window, self.z_window)[i]


@dataclass(frozen=True)
class OFISkew:
    """Shift the reservation price towards where order flow imbalance predicts the mid is going."""
    window: int = 50
    z_window: int = 200
    ticks_per_z: float = 0.5
    max_ticks: float = 4.0

    def shift_ticks(self, market: Market, i: int) -> float:
        z = ofi_z(market, self.window, self.z_window)[i]
        return float(np.clip(self.ticks_per_z * z, -self.max_ticks, self.max_ticks))


def ofi_z(market: Market, window: int = 50, z_window: int = 200):
    return market.cached(("ofi_z", window, z_window),
                         lambda: rolling_zscore(rolling_sum(market.ofi, window), z_window))


def as_half_spread_ticks(gamma: float, kappa: float) -> float:
    """Avellaneda-Stoikov spread term (1/gamma) ln(1 + gamma/kappa) per side, x2 as in the
    original code, with kappa in per-tick units. The sigma^2 inventory term is negligible at
    this scale and inventory is handled by InventorySkew instead."""
    return (2.0 / gamma) * math.log(1.0 + gamma / kappa)


@dataclass(frozen=True)
class ASQuoter:
    order_size: int
    inventory_limit: int
    gamma: float = 0.1
    kappa: float = 3.2
    min_half_spread_ticks: float = 0.25
    max_half_spread_ticks: float = 12.0
    touch_join_ticks: float = 1.0        # rest at most this far behind the touch, else join it
    flatten_frac: float = 0.5            # cross the spread once |inventory| passes this x limit
    inventory_skew: InventorySkew | None = field(default_factory=InventorySkew)
    size_skew: SizeSkew | None = field(default_factory=SizeSkew)
    ofi_guard: OFIGuard | None = field(default_factory=OFIGuard)
    ofi_skew: OFISkew | None = None

    @property
    def flatten_at(self) -> float:
        return max(self.flatten_frac * self.inventory_limit, 2 * self.order_size)

    def quote(self, market: Market, i: int, inventory: int) -> Quotes:
        best_bid, best_ask = int(market.best_bid[i]), int(market.best_ask[i])

        r = float(market.micro[i])
        half = float(np.clip(as_half_spread_ticks(self.gamma, self.kappa),
                             self.min_half_spread_ticks, self.max_half_spread_ticks)) * TICK
        if self.inventory_skew:
            r -= self.inventory_skew.shift_ticks(self.gamma, inventory) * TICK
        ofi_shift = self.ofi_skew.shift_ticks(market, i) if self.ofi_skew else 0.0
        r += ofi_shift * TICK

        protect_bid = protect_ask = False
        bid_half = ask_half = half
        if self.ofi_guard:
            z = self.ofi_guard.z(market, i)
            protect_ask = z > self.ofi_guard.z_threshold
            protect_bid = z < -self.ofi_guard.z_threshold
            widened = max(half, self.ofi_guard.widen_ticks * TICK)
            bid_half = widened if protect_bid else half
            ask_half = widened if protect_ask else half

        if self.size_skew:
            bid_size, ask_size = self.size_skew.sizes(self.order_size, inventory, self.flatten_at)
        else:
            bid_size = ask_size = self.order_size

        if inventory < -self.flatten_at and inventory < self.inventory_limit:
            return Quotes(Quote(best_ask, self.order_size, forced=True), None)
        if inventory > self.flatten_at and inventory > -self.inventory_limit:
            return Quotes(None, Quote(best_bid, self.order_size, forced=True))

        bid = ask = None
        if inventory < self.inventory_limit:
            bid = min(min(round((r - bid_half) / TICK) * TICK, best_ask - TICK), best_bid)
        if inventory > -self.inventory_limit:
            ask = max(max(round((r + ask_half) / TICK) * TICK, best_bid + TICK), best_ask)

        # Join the touch rather than rest far behind it, unless the OFI guard pulled us back.
        # The side the OFI skew pushes back may rest that much further out before snapping.
        gaps, snapped, organic = [], 0, 0
        join_gap = self.touch_join_ticks * TICK
        if bid is not None and not protect_bid:
            if best_bid - bid > join_gap + max(0.0, -ofi_shift) * TICK:
                bid, snapped = best_bid, snapped + 1
            else:
                organic += 1
        if ask is not None and not protect_ask:
            if ask - best_ask > join_gap + max(0.0, ofi_shift) * TICK:
                ask, snapped = best_ask, snapped + 1
            else:
                organic += 1
        if bid is not None:
            gaps.append((best_bid - bid) / TICK)
        if ask is not None:
            gaps.append((ask - best_ask) / TICK)

        bid_q = Quote(bid, bid_size) if bid is not None else None
        ask_q = Quote(ask, ask_size) if ask is not None else None
        return Quotes(bid_q, ask_q, tuple(gaps), snapped, organic)


def adaptive_limits(profile: dict, depth_fraction=0.08, min_size=20, max_size=500,
                    limit_multiple=5.0) -> dict:
    """Order size as a fraction of this ticker's touch depth; inventory limit scales with it."""
    order_size = int(np.clip(depth_fraction * profile["avg_touch_depth_shares"], min_size, max_size))
    return {"order_size": order_size, "inventory_limit": int(order_size * limit_multiple)}
