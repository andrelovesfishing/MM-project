# 4. A rewrite is reconciled against the old results, not just tested

**Decision:** before the new package replaced `all_main.py`, it was run on the old settings and every output compared. Each difference either disappeared or was traced to a named cause. `docs/parity.md` records the result.

**Why:**
- Unit tests only cover cases someone thought of. The earlier bugs were cases nobody had.
- A full-day comparison against a trusted run catches the rest.
- Later experiments change P&L on purpose. Without a reconciled starting point, a new bug and a real improvement look the same.
- Old quirks were not copied to make numbers match: float rounding in the touch-snap rule was dropped, and its effect measured instead.
