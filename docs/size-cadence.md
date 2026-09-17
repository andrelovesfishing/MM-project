# Which change fixed the cross-ticker results: order size or requote cadence?

Every cell is **pessimistic / optimistic** fills. Dollars over one day (LOBSTER, 2012-06-21).
Regenerate with `python -m experiments.size_cadence`.

- **Fixed size:** 200 shares, inventory limit 1,000, on every ticker (the old setting).
- **Adaptive size:** 8% of the ticker's average touch depth, clipped to 20–500, limit 5x that.
- **Every 100 events** vs **every 6s** of market time.

## Effects on total P&L

Each effect is the P&L change from switching that factor to its new level (adaptive size, or time cadence), averaged over both settings of the other. **Interaction** is how much the cadence effect differs between the two sizes.

| | 100 events lasts | Size effect | Cadence effect | Interaction |
|---|---|---|---|---|
| AAPL | 5.8s | 5,654 / 4,619 | 754 / 691 | -652 / -614 |
| AMZN | 8.7s | 2,476 / 2,362 | -848 / -388 | 737 / 301 |
| GOOG | 15.8s | 3,154 / 3,784 | -387 / -246 | 315 / 136 |
| INTC | 3.7s | -249 / -569 | -260 / 33 | -165 / -7 |
| MSFT | 3.5s | -312 / -1,003 | -276 / 216 | -50 / 99 |

Predictions written before running, pessimistic / optimistic:

- INTC: size effect larger than cadence: no / yes
- MSFT: size effect larger than cadence: yes / yes
- GOOG: cadence effect larger than size: no / no

Spread of total P&L across the five tickers (best minus worst):

- Fixed size, every 100 events (the old setup): 6,881 / 5,236
- Adaptive size, every 6s (the current setup): 313 / 1,279

## All four combinations

| | Order size | Total P&L | Net ¢/share | Crossing cost | Passive shares | Quotes sent |
|---|---|---|---|---|---|---|
| AAPL, fixed size, every 100 events | 200 | -6,918 / -5,721 | -2.16 / -1.15 | -1,559 / -1,799 | 275,233 / 377,377 | 4,004 / 4,004 |
| AAPL, fixed size, every 6s | 200 | -5,512 / -4,417 | -2.61 / -1.46 | -938 / -993 | 239,769 / 316,771 | 3,655 / 3,655 |
| AAPL, adaptive size, every 100 events | 20 | -612 / -488 | -1.58 / -0.96 | -154 / -167 | 32,700 / 39,406 | 4,004 / 4,004 |
| AAPL, adaptive size, every 6s | 20 | -509 / -411 | -1.91 / -1.17 | -77 / -90 | 28,370 / 32,838 | 3,655 / 3,655 |
| AMZN, fixed size, every 100 events | 200 | -1,946 / -2,270 | -1.53 / -0.88 | -515 / -726 | 94,669 / 146,854 | 2,698 / 2,698 |
| AMZN, fixed size, every 6s | 200 | -3,530 / -2,959 | -2.12 / -1.04 | -406 / -477 | 89,913 / 136,062 | 3,537 / 3,537 |
| AMZN, adaptive size, every 100 events | 20 | -206 / -208 | -1.19 / -0.76 | -64 / -82 | 11,996 / 16,326 | 2,698 / 2,698 |
| AMZN, adaptive size, every 6s | 20 | -317 / -296 | -1.68 / -0.90 | -49 / -60 | 11,207 / 14,474 | 3,537 / 3,537 |
| GOOG, fixed size, every 100 events | 200 | -3,087 / -4,044 | -3.78 / -2.63 | -707 / -863 | 79,235 / 113,664 | 1,480 / 1,480 |
| GOOG, fixed size, every 6s | 200 | -3,788 / -4,425 | -3.38 / -2.24 | -754 / -866 | 87,326 / 128,436 | 3,374 / 3,374 |
| GOOG, adaptive size, every 100 events | 20 | -248 / -396 | -2.80 / -2.08 | -65 / -105 | 9,697 / 11,939 | 1,480 / 1,480 |
| GOOG, adaptive size, every 6s | 20 | -319 / -506 | -2.40 / -1.63 | -95 / -110 | 11,152 / 13,710 | 3,374 / 3,374 |
| INTC, fixed size, every 100 events | 200 | -120 / -485 | -0.13 / +0.07 | 0 / -4 | 31,358 / 204,107 | 6,241 / 6,241 |
| INTC, fixed size, every 6s | 200 | -215 / -446 | -0.37 / +0.06 | 0 / -3 | 38,087 / 143,702 | 3,691 / 3,691 |
| INTC, adaptive size, every 100 events | 500 | -204 / -1,048 | -0.14 / +0.04 | 0 / -9 | 63,178 / 407,369 | 6,241 / 6,241 |
| INTC, adaptive size, every 6s | 500 | -630 / -1,021 | -0.40 / +0.03 | 0 / -5 | 81,178 / 304,483 | 3,691 / 3,691 |
| MSFT, fixed size, every 100 events | 200 | -37 / -789 | -0.23 / -0.02 | 0 / -5 | 23,755 / 249,745 | 6,688 / 6,688 |
| MSFT, fixed size, every 6s | 200 | -264 / -671 | -0.58 / -0.04 | 0 / -5 | 41,647 / 185,334 | 3,704 / 3,704 |
| MSFT, adaptive size, every 100 events | 500 | -299 / -1,891 | -0.31 / -0.06 | 0 / -2 | 47,450 / 496,481 | 6,688 / 6,688 |
| MSFT, adaptive size, every 6s | 500 | -625 / -1,575 | -0.62 / -0.10 | -2 / -12 | 87,337 / 390,208 | 3,704 / 3,704 |
