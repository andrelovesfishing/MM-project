# Can gentler inventory control keep the gain from event requoting?

Every cell is **pessimistic / optimistic** fills. Dollars over one day (LOBSTER, 2012-06-21).
Regenerate with `python -m experiments.inventory_control`.

- **6s timer (Phase B):** the Phase B baseline.
- **1-tick requote:** #1's winner. Requote when the micro-price moves 1 tick, with Phase B inventory controls.
- **+ ...:** 1-tick requote with one inventory control changed.

## Sweep on AAPL (the only ticker tuned on)

| | Total P&L | Net ¢/share | Crossing cost | Passive shares | Forced shares |
|---|---|---|---|---|---|
| 6s timer (Phase B) | -509 / -411 | -1.91 / -1.17 | -77 / -90 | 28,370 / 32,838 | 1,156 / 1,222 |
| 1-tick requote | -464 / -661 | -0.34 / -0.10 | -528 / -971 | 40,330 / 60,488 | 7,374 / 13,161 |
| + inventory skew 10 ticks/100sh | -443 / -686 | -0.37 / -0.17 | -488 / -962 | 40,181 / 60,131 | 6,733 / 12,791 |
| + inventory skew 20 ticks/100sh | -377 / -698 | -0.39 / -0.16 | -460 / -877 | 39,607 / 59,214 | 6,249 / 11,542 |
| + inventory skew 40 ticks/100sh | -329 / -600 | -0.39 / -0.15 | -429 / -843 | 39,528 / 59,016 | 5,934 / 11,156 |
| + flatten at 0.75x limit | 7 / -386 | -0.32 / -0.13 | -249 / -513 | 41,590 / 61,634 | 3,557 / 6,620 |
| + flatten only past the limit | 289 / 9 | -0.31 / -0.15 | -127 / -230 | 42,547 / 62,932 | 1,625 / 3,066 |
| + size skew to 0 | -217 / -481 | -0.51 / -0.32 | -137 / -249 | 35,513 / 51,565 | 1,820 / 3,193 |

**Chosen: 1-tick requote + flatten only past the limit**, the best total P&L averaged over both presets.

## All five tickers

| | Total P&L | Net ¢/share | Crossing cost | Passive shares | Forced shares |
|---|---|---|---|---|---|
| AAPL, 6s timer (Phase B) | -509 / -411 | -1.91 / -1.17 | -77 / -90 | 28,370 / 32,838 | 1,156 / 1,222 |
| AAPL, 1-tick requote | -464 / -661 | -0.34 / -0.10 | -528 / -971 | 40,330 / 60,488 | 7,374 / 13,161 |
| AAPL, + flatten only past the limit | 289 / 9 | -0.31 / -0.15 | -127 / -230 | 42,547 / 62,932 | 1,625 / 3,066 |
| AMZN, 6s timer (Phase B) | -317 / -296 | -1.68 / -0.90 | -49 / -60 | 11,207 / 14,474 | 690 / 889 |
| AMZN, 1-tick requote | -209 / -310 | -0.24 / +0.13 | -268 / -382 | 13,934 / 20,034 | 3,113 / 4,492 |
| AMZN, + flatten only past the limit | -8 / -189 | -0.17 / +0.26 | -71 / -123 | 14,306 / 20,754 | 741 / 1,347 |
| GOOG, 6s timer (Phase B) | -319 / -506 | -2.40 / -1.63 | -95 / -110 | 11,152 / 13,710 | 647 / 756 |
| GOOG, 1-tick requote | -244 / -592 | -0.68 / -0.73 | -441 / -762 | 15,071 / 23,137 | 2,780 / 4,948 |
| GOOG, + flatten only past the limit | 154 / -169 | -0.55 / -0.74 | -136 / -214 | 15,395 / 23,618 | 643 / 1,180 |
| INTC, 6s timer (Phase B) | -630 / -1,021 | -0.40 / +0.03 | 0 / -5 | 81,178 / 304,483 | 0 / 1,000 |
| INTC, 1-tick requote | -303 / -904 | -0.16 / +0.09 | 0 / 0 | 63,462 / 350,196 | 0 / 0 |
| INTC, + flatten only past the limit | -398 / -878 | -0.15 / +0.09 | 0 / 0 | 63,329 / 355,477 | 0 / 0 |
| MSFT, 6s timer (Phase B) | -625 / -1,575 | -0.62 / -0.10 | -2 / -12 | 87,337 / 390,208 | 500 / 2,000 |
| MSFT, 1-tick requote | -332 / -1,744 | -0.21 / -0.07 | 0 / -4 | 57,517 / 446,431 | 0 / 800 |
| MSFT, + flatten only past the limit | -232 / -1,748 | -0.23 / -0.08 | 0 / 0 | 59,131 / 457,721 | 0 / 0 |

Tickers where the chosen setup does better, pessimistic / optimistic:

| | vs 6s timer (Phase B) | vs 1-tick requote |
|---|---|---|
| Total P&L | 5 / 4 of 5 | 4 / 4 of 5 |
| Total P&L excluding inventory mark-to-market | 5 / 5 of 5 | 4 / 3 of 5 |
| Net per passive share | 5 / 5 of 5 | 4 / 1 of 5 |
| Crossing cost | 1 / 2 of 5 | 3 / 4 of 5 |

Column meanings are as in [event-requote.md](event-requote.md). **Forced shares** were crossed by a flatten.
