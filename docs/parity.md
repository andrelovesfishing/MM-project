# Parity: new `mm/` package vs old `all_main.py`

Reference: `all_main.py` at commit `42aa1c5`, with fill fixes, run in full.

**Result:** every backtest metric matches exactly, once one float comparison in the old code is made exact. This covers ablation (4 x 32 columns), cross-section (5 tickers x 41 columns) and the gamma, kappa and touch-join sweeps.

To reproduce:

1. Take `all_main.py` from that commit.
2. Replace the two touch-join comparisons with `round((best_bid - new_bid_px) / tick_size, 6) > params.touch_join_ticks` (and the ask-side equivalent).
3. Run it, then run `python -m experiments.parity <its output dir>`.

`experiments/parity.py` was removed once Phase B started changing results on purpose (`docs/realism.md`). It is at commit `ad8208a`.

## Differences from the original run, and why

### 1. Touch-snap rule: float noise

The old code tested `best_bid - bid > 1 tick` in float dollars. A quote exactly one tick back could land either side of the threshold.

| Ticker | Quotes snapped, old | Quotes snapped, new | Realized P&L, old | Realized P&L, new |
|---|---|---|---|---|
| AAPL | 0.03% | 0.00% | -532.94 | -532.94 |
| AMZN | 0.43% | 0.00% | -337.27 | -341.74 |
| GOOG | 0.22% | 0.00% | -516.32 | -515.68 |
| INTC | 21.6% | 0.24% | -1081.16 | -912.06 |
| MSFT | 21.2% | 0.40% | -2232.66 | -1641.09 |

- AAPL ablation: baseline -958.50 → -962.70; + size skew -533.68 → -533.58. The other two rows are unchanged.
- Gamma sweep: only gamma = 0.01 moves (-537.75 → -533.50).
- Kappa sweep: rows with kappa ≤ 1 move by about $5 at most.

### 2. OFI information coefficient: float ties

- IC at 50 events: 0.206416 → 0.206595.
- OFI and its rolling sum are bit-identical to the old arrays. The old mid price differed from exact mids by up to 2e-13, which split 172 distinct 50-event mid changes into 412 and so changed Spearman ranks.
- The new figure is the exact one.

### 3. Trade-distance kappa fit (diagnostic, not used in quoting)

kappa 0.3215 → 0.3172. Same cause: float distances land on different sides of histogram bucket edges.

## Kept on purpose, to review in Phase B

All resolved in Phase B, each measured in `docs/realism.md`: the engine and quoter defects are fixed, and the fill assumptions are `FillModel` switches.

These behaviours were ported unchanged so parity could be checked. They look unrealistic and each changes results, so each should become a deliberate, measured change:

- **Forced flattens don't cross.** A "cross" is a bid resting at the best ask with nothing queued ahead. It fills only when a later trade hits the bid side, instead of executing at once against the ask.
- **A side with no new quote keeps its old order resting.** During a forced flatten, the opposite passive quote stays live.
- **A requote at an unchanged price keeps the old size and forced flag,** so size skew only takes effect when the price moves.
- **Queue position below the visible book** assumes the 10th level's size is ahead of us.
- **Touch-snap diagnostics count quotes before a forced flatten replaces them.**
- **A delayed quote can breach the inventory limit.** The limit pull runs before a pending quote lands, so the quote can re-place a bid right after the limit was hit. Pinned by an `xfail` test.
- **Requotes faster than the latency starve quotes.** Each new decision replaces the pending one and pushes its landing time back, so if events are 6s or more apart, nothing ever rests. Pinned by an `xfail` test.
- **Sharpe annualisation** scales by `sqrt(252 * 6.5 * 3600 / n_samples)`, which is not a standard annualisation for 50-event samples.
