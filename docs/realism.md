# Realism ladder: what each simulator assumption is worth

A backtest is only as honest as its fill simulation. Each row below changes one assumption, in its own commit, and re-runs the full model on all five tickers (LOBSTER sample, 2012-06-21).

- **Realized:** P&L locked in by closing trades. **Total:** realized plus open inventory marked at the mid.
- **Fills:** fill records; one order can fill in several pieces.
- **Forced flattens:** requote decisions that cross the spread to cut inventory.
- Dollars; AAPL is where the strategy was tuned, the other four are out of sample.
- The resulting pessimistic–optimistic range, with P&L split by source, is in `docs/headline.md`.
- Reproduce a row with `python -m experiments.realism "<change>"` at that commit.

| Change | AAPL realized | AAPL total | AAPL fills | AAPL forced flattens | 5-ticker realized | 5-ticker total | 5-ticker fills |
|---|---|---|---|---|---|---|---|
| Baseline: Phase A port of the old simulator | -532.94 | -533.30 | 2,779 | 95 | -3,943.51 | -3,952.24 | 9,071 |
| Delayed quotes can't breach the inventory limit (no effect: forced flattens keep inventory near half the limit) | -532.94 | -533.30 | 2,779 | 95 | -3,943.51 | -3,952.24 | 9,071 |
| Quotes in flight each land after their own latency (rarely matters: 6s requotes vs a 2-event latency) | -532.94 | -533.30 | 2,779 | 95 | -3,940.76 | -3,949.49 | 9,071 |
| Forced flattens cross the spread at once, at the far side's prices | -505.31 | -505.67 | 2,788 | 71 | -3,856.59 | -3,865.31 | 9,130 |
| A side with no new quote cancels its resting order (small, now that flattens fill at once) | -505.31 | -505.67 | 2,788 | 71 | -3,856.20 | -3,864.93 | 9,129 |
| Requote at the same price: a smaller size keeps queue place, a larger one rejoins at the back (size skew now applies without a price move) | -470.33 | -470.69 | 2,792 | 68 | -3,815.76 | -3,824.40 | 9,128 |
| Diagnostics: snap rate counts quotes actually sent; Sharpe from 1-minute bars (no P&L change; AAPL Sharpe −1.0 → −48.8, the old scaling hid a steady bleed) | -470.33 | -470.69 | 2,792 | 68 | -3,815.76 | -3,824.40 | 9,128 |

## Fill assumptions the data can't settle

Our order was never in the real book, so some fill rules are guesses. Each is a `FillModel` switch in `mm/queue.py`. Rows change one switch from the defaults above, then both ends together.

"Pessimistic" and "optimistic" mean fewer or more generous fills, not worse or better P&L. Across the five tickers the generous end loses more: extra passive fills tend to be the ones the market is about to run over (adverse selection).

| Change | AAPL realized | AAPL total | AAPL fills | AAPL forced flattens | 5-ticker realized | 5-ticker total | 5-ticker fills |
|---|---|---|---|---|---|---|---|
| Cancels at our price all come from behind us | -490.82 | -491.06 | 2,499 | 66 | -2,435.07 | -2,436.01 | 5,738 |
| Cancels judged by order id: only orders placed before ours are ahead | -462.71 | -463.07 | 2,728 | 65 | -4,334.41 | -4,341.94 | 8,714 |
| Hidden trades at our price leave the visible queue alone | -473.87 | -474.23 | 2,725 | 65 | -3,796.46 | -3,805.62 | 8,934 |
| A trade through our price fills us in full | -410.91 | -411.27 | 2,394 | 64 | -3,800.10 | -3,808.74 | 8,152 |
| Nothing queued ahead when resting below the visible book (no effect: quotes never rest that deep) | -470.33 | -470.69 | 2,792 | 68 | -3,815.76 | -3,824.40 | 9,128 |
| **Pessimistic:** all four switches at the cautious end | -509.30 | -509.54 | 2,416 | 61 | -2,399.02 | -2,400.17 | 5,502 |
| **Optimistic:** all four switches at the generous end | -410.91 | -411.27 | 2,394 | 64 | -3,800.10 | -3,808.74 | 8,152 |
