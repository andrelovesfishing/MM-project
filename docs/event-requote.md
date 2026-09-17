# Does requoting on price moves cut adverse selection?

Every cell is **pessimistic / optimistic** fills. Dollars over one day (LOBSTER, 2012-06-21).
Regenerate with `python -m experiments.event_requote`.

## Sweep on AAPL (the only ticker tuned on)

Each row requotes every 6s and also whenever the micro-price moves that far since the last quote.

| | Total P&L | Spread ¢/share | Adverse sel. ¢/share | Net ¢/share | Crossing cost | Quotes sent |
|---|---|---|---|---|---|---|
| timer only | -509 / -411 | +2.33 / +2.97 | -4.24 / -4.14 | -1.91 / -1.17 | -77 / -90 | 3,655 / 3,655 |
| 3 ticks | -546 / -770 | +3.58 / +3.75 | -4.27 / -3.93 | -0.69 / -0.18 | -454 / -769 | 36,951 / 36,951 |
| 2 ticks | -386 / -775 | +3.55 / +3.70 | -4.04 / -3.86 | -0.49 / -0.16 | -482 / -882 | 48,239 / 48,239 |
| 1 tick | -464 / -661 | +3.56 / +3.68 | -3.90 / -3.78 | -0.34 / -0.10 | -528 / -971 | 65,645 / 65,645 |
| 0.5 ticks | -371 / -857 | +3.58 / +3.62 | -3.82 / -3.64 | -0.24 / -0.02 | -586 / -1,138 | 82,277 / 82,277 |

**Chosen: 1 tick**, the best total P&L averaged over both presets.

## All five tickers at 1 tick

| | Total P&L | Spread ¢/share | Adverse sel. ¢/share | Net ¢/share | Crossing cost | Quotes sent |
|---|---|---|---|---|---|---|
| AAPL, timer only | -509 / -411 | +2.33 / +2.97 | -4.24 / -4.14 | -1.91 / -1.17 | -77 / -90 | 3,655 / 3,655 |
| AAPL, 1 tick | -464 / -661 | +3.56 / +3.68 | -3.90 / -3.78 | -0.34 / -0.10 | -528 / -971 | 65,645 / 65,645 |
| AMZN, timer only | -317 / -296 | +2.22 / +2.71 | -3.89 / -3.60 | -1.68 / -0.90 | -49 / -60 | 3,537 / 3,537 |
| AMZN, 1 tick | -209 / -310 | +4.08 / +3.89 | -4.32 / -3.77 | -0.24 / +0.13 | -268 / -382 | 32,584 / 32,584 |
| GOOG, timer only | -319 / -506 | +5.30 / +6.04 | -7.70 / -7.67 | -2.40 / -1.63 | -95 / -110 | 3,374 / 3,374 |
| GOOG, 1 tick | -244 / -592 | +7.12 / +6.90 | -7.80 / -7.63 | -0.68 / -0.73 | -441 / -762 | 33,178 / 33,178 |
| INTC, timer only | -630 / -1,021 | +0.15 / +0.47 | -0.55 / -0.45 | -0.40 / +0.03 | 0 / -5 | 3,691 / 3,691 |
| INTC, 1 tick | -303 / -904 | +0.36 / +0.52 | -0.52 / -0.43 | -0.16 / +0.09 | 0 / 0 | 4,158 / 4,158 |
| MSFT, timer only | -625 / -1,575 | -0.03 / +0.43 | -0.58 / -0.53 | -0.62 / -0.10 | -2 / -12 | 3,704 / 3,704 |
| MSFT, 1 tick | -332 / -1,744 | +0.29 / +0.47 | -0.50 / -0.55 | -0.21 / -0.07 | 0 / -4 | 4,364 / 4,364 |

Tickers improved, pessimistic / optimistic:

- Net per passive share: 5 / 5 of 5
- Adverse selection per passive share: 3 / 3 of 5
- Crossing cost: 1 / 2 of 5
- Total P&L: 5 / 1 of 5

Column meanings:

- **Spread ¢/share:** what each passive share earned against the mid at the moment it filled.
- **Adverse sel. ¢/share:** how far the mid then moved against it over the next 100 events. Closer to zero is better.
- **Net ¢/share:** the two together: what a passive share was worth 100 events after it filled.
- **Crossing cost:** what forced flattens paid to cross the spread once inventory passed the threshold.
- **Quotes sent:** requote decisions. An exchange sees each one as cancel-and-replace messages.
