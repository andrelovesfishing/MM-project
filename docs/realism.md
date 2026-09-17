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
