"""Inventory, cash and average-cost P&L. Cash is an exact integer (price units x shares)."""

from dataclasses import dataclass


@dataclass
class Ledger:
    inventory: int = 0
    cash: int = 0
    avg_cost: float = 0.0
    realized: float = 0.0

    def fill(self, side: int, price: int, qty: int):
        """Record a fill. side is +1 for a buy, -1 for a sell."""
        signed = side * qty
        prev = self.inventory
        if prev == 0 or (prev > 0) == (signed > 0):
            total = abs(prev) + qty
            self.avg_cost = (self.avg_cost * abs(prev) + price * qty) / total
        else:
            closing = min(qty, abs(prev))
            self.realized += closing * (price - self.avg_cost) * (1 if prev > 0 else -1)
            if qty > closing:  # flipped through flat: the rest opens a new position
                self.avg_cost = price
        self.inventory = prev + signed
        self.cash -= signed * price

    def unrealized(self, mark: float) -> float:
        return self.inventory * (mark - self.avg_cost) if self.inventory else 0.0

    def total(self, mark: float) -> float:
        return self.cash + self.inventory * mark
