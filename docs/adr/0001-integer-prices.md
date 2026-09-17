# 1. Prices are integers in LOBSTER units

**Decision:** keep every price as LOBSTER's integer (1/10,000 dollar) inside the package. A tick is 100. Dollars appear only in `mm/metrics.py`.

**Why:**
- The old code stored prices as float dollars. That caused two separate bugs:
  - A tick-vs-dollar mix-up made kappa inert.
  - Rounding noise decided whether a quote exactly one tick behind the touch counted as "more than one tick", so 21% of INTC and MSFT quotes were snapped to the touch by accident (see `docs/parity.md`).
- With integers, equal prices compare equal, and a unit mix-up is a visible `* TICK` or `/ PX_PER_DOLLAR` rather than a silent 100x.
- Cash is an exact integer, so P&L never drifts.

**Why not whole ticks:** hidden executions (type 5) can print at half-cent midpoints (2,140 of 3,559 on INTC), so tick units would not be exact.
