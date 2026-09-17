# Does skewing quotes with OFI beat widening against it?

Every cell is **pessimistic / optimistic** fills. Dollars over one day (LOBSTER, 2012-06-21).
All runs requote on the 6s timer. Regenerate with `python -m experiments.ofi_skew`.

- **OFI guard:** the Phase B baseline. Widens the side about to be run over when |OFI z| > 2.
- **Skew k tick/z:** no guard. The reservation price moves k ticks per unit of OFI z (capped at 4), so both quotes lean the predicted way.
- **No OFI:** neither.

## Sweep on AAPL (the only ticker tuned on)

| | Total P&L | Spread ¢/share | Adverse sel. ¢/share | Net ¢/share | Crossing cost | Passive shares |
|---|---|---|---|---|---|---|
| no OFI | -508 / -409 | +2.32 / +2.98 | -4.25 / -4.13 | -1.93 / -1.15 | -77 / -92 | 28,600 / 33,028 |
| OFI guard | -509 / -411 | +2.33 / +2.97 | -4.24 / -4.14 | -1.91 / -1.17 | -77 / -90 | 28,370 / 32,838 |
| skew 0.25 tick/z | -502 / -404 | +2.32 / +2.98 | -4.23 / -4.13 | -1.90 / -1.15 | -80 / -92 | 28,598 / 32,932 |
| skew 0.5 tick/z | -509 / -408 | +2.33 / +2.99 | -4.22 / -4.15 | -1.90 / -1.16 | -79 / -92 | 28,556 / 32,836 |
| skew 1 tick/z | -491 / -430 | +2.35 / +3.01 | -4.27 / -4.19 | -1.92 / -1.19 | -78 / -91 | 28,113 / 32,529 |
| skew 2 tick/z | -484 / -419 | +2.36 / +3.02 | -4.33 / -4.26 | -1.98 / -1.25 | -72 / -95 | 27,549 / 31,693 |

**Chosen: skew 2 tick/z**, the best total P&L averaged over both presets.

## All five tickers

| | Total P&L | Spread ¢/share | Adverse sel. ¢/share | Net ¢/share | Crossing cost | Passive shares |
|---|---|---|---|---|---|---|
| AAPL, no OFI | -508 / -409 | +2.32 / +2.98 | -4.25 / -4.13 | -1.93 / -1.15 | -77 / -92 | 28,600 / 33,028 |
| AAPL, OFI guard | -509 / -411 | +2.33 / +2.97 | -4.24 / -4.14 | -1.91 / -1.17 | -77 / -90 | 28,370 / 32,838 |
| AAPL, skew 2 tick/z | -484 / -419 | +2.36 / +3.02 | -4.33 / -4.26 | -1.98 / -1.25 | -72 / -95 | 27,549 / 31,693 |
| AMZN, no OFI | -315 / -302 | +2.22 / +2.71 | -3.91 / -3.62 | -1.69 / -0.90 | -46 / -62 | 11,341 / 14,730 |
| AMZN, OFI guard | -317 / -296 | +2.22 / +2.71 | -3.89 / -3.60 | -1.68 / -0.90 | -49 / -60 | 11,207 / 14,474 |
| AMZN, skew 2 tick/z | -333 / -282 | +2.30 / +2.77 | -3.92 / -3.64 | -1.62 / -0.86 | -53 / -54 | 10,574 / 14,023 |
| GOOG, no OFI | -293 / -497 | +5.32 / +6.07 | -7.68 / -7.75 | -2.35 / -1.68 | -95 / -110 | 11,231 / 13,853 |
| GOOG, OFI guard | -319 / -506 | +5.30 / +6.04 | -7.70 / -7.67 | -2.40 / -1.63 | -95 / -110 | 11,152 / 13,710 |
| GOOG, skew 2 tick/z | -320 / -504 | +5.27 / +6.03 | -7.66 / -7.76 | -2.39 / -1.73 | -92 / -106 | 11,063 / 13,521 |
| INTC, no OFI | -509 / -1,101 | +0.16 / +0.47 | -0.56 / -0.44 | -0.40 / +0.03 | 0 / -8 | 89,357 / 328,509 |
| INTC, OFI guard | -630 / -1,021 | +0.15 / +0.47 | -0.55 / -0.45 | -0.40 / +0.03 | 0 / -5 | 81,178 / 304,483 |
| INTC, skew 2 tick/z | -565 / -891 | +0.15 / +0.45 | -0.51 / -0.46 | -0.37 / -0.01 | -30 / -95 | 79,047 / 236,005 |
| MSFT, no OFI | -629 / -1,678 | -0.03 / +0.43 | -0.57 / -0.53 | -0.60 / -0.10 | -2 / -15 | 98,239 / 401,078 |
| MSFT, OFI guard | -625 / -1,575 | -0.03 / +0.43 | -0.58 / -0.53 | -0.62 / -0.10 | -2 / -12 | 87,337 / 390,208 |
| MSFT, skew 2 tick/z | -385 / -1,562 | -0.11 / +0.40 | -0.54 / -0.51 | -0.64 / -0.11 | -9 / -104 | 76,828 / 301,910 |

Tickers where the chosen skew does better, pessimistic / optimistic:

| | vs OFI guard | vs no OFI |
|---|---|---|
| Total P&L | 3 / 4 of 5 | 2 / 3 of 5 |
| Net per passive share | 3 / 1 of 5 | 2 / 1 of 5 |
| Adverse selection per passive share | 3 / 1 of 5 | 3 / 1 of 5 |

Column meanings are as in [event-requote.md](event-requote.md). **Passive shares** is volume filled by resting quotes.
