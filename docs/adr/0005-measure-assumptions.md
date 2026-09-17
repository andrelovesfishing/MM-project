# 5. Simulator assumptions are measured one at a time, and unknowable ones are reported as a range

**Decision:** every change to how the simulator fills or places orders lands in its own commit, with a row in `docs/realism.md` showing its P&L effect. Fill rules the data can't settle are `FillModel` switches in `mm/queue.py`. Headline results are reported at both ends (`docs/headline.md`), not at one chosen setting.

**Why:**
- A backtest's P&L is mostly its fill assumptions. Our order was never in the real book, so we can't know where it sat in the queue or whether a given trade would have reached it.
- Fixing defects silently would mix up "the strategy got better" with "the simulator got kinder". The ladder keeps them apart.
- A single setting invites tuning it until the numbers look good. A range doesn't.
- Where the data does answer a question, it's used: LOBSTER order ids tell exactly whether a cancelled order joined before or after ours (`cancels="exact"`).
- The P&L split (`mm.metrics.attribution`) sums exactly to total P&L, so the range can be explained, not just quoted: the extra fills from generous assumptions are mostly adversely selected.
