# 2. The fill model is a pure function of (order, event)

**Decision:** `mm/queue.py` holds all queue and fill rules as `on_event(order, event) -> (order, filled)`. It knows nothing about strategies, latency or P&L.

**Why:**
- All three fill bugs found in the old code lived in fill logic tangled into the backtest loop:
  - trade direction read backwards
  - deletes (type 3) not shortening the queue
  - partial fills sized wrongly
- None could be tested without running a whole day.
- Now each rule has a test built from a few hand-made events (`tests/test_queue.py`), including every LOBSTER event type.
- Alternative fill assumptions (Phase B) become options on this module, not edits to the loop.
