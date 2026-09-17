# Realism ladder: what each simulator assumption is worth

A backtest is only as honest as its fill simulation. Each row below changes one assumption, in its own commit, and re-runs the full model on all five tickers (LOBSTER sample, 2012-06-21).

- **Realized:** P&L locked in by closing trades. **Total:** realized plus open inventory marked at the mid.
- **Forced flattens:** requote decisions that cross the spread to cut inventory.
- Dollars; AAPL is where the strategy was tuned, the other four are out of sample.
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
