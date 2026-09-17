# Is the OFI signal statistically real?

**Yes, but far less emphatically than the naive numbers claimed.** Correcting for overlapping windows shrinks the
t-stats 3–11x, yet at h=50 they still run 13–33 on all five stocks.
Not significant at 5% after correction: GOOG at h=1000. One day of data per stock, so this says the effect was real that day, not that it persists.

Rolling 50-event OFI against the mid-price change h events ahead, on one day per stock (LOBSTER, 2012-06-21).
Each cell: **Spearman IC · naive t-stat → Newey-West t-stat**. Regenerate with `python -m experiments.ofi_significance`.

| Horizon (events) | AAPL | AMZN | GOOG | INTC | MSFT |
|---|---|---|---|---|---|
| 10 | 0.160 · 103 → **31.8** | 0.171 · 90 → **26.8** | 0.173 · 67 → **21.0** | 0.104 · 83 → **25.4** | 0.120 · 99 → **30.7** |
| 50 | 0.207 · 134 → **22.5** | 0.223 · 119 → **19.9** | 0.185 · 72 → **13.0** | 0.204 · 165 → **25.8** | 0.241 · 203 → **32.7** |
| 200 | 0.143 · 92 → **11.3** | 0.180 · 95 → **11.7** | 0.137 · 53 → **6.9** | 0.273 · 224 → **29.1** | 0.300 · 257 → **37.0** |
| 500 | 0.086 · 55 → **5.7** | 0.095 · 50 → **5.4** | 0.053 · 20 → **2.2** | 0.219 · 177 → **20.5** | 0.213 · 178 → **20.8** |
| 1000 | 0.066 · 42 → **4.0** | 0.062 · 32 → **3.2** | 0.010 · 4 → **0.4** | 0.167 · 134 → **14.0** | 0.154 · 127 → **14.2** |

- **Naive t-stat:** treats every event as an independent observation.
- **Newey-West t-stat:** allows for the overlap. Consecutive 50-event sums and h-event forward changes share almost all their data, so neighbouring observations are nearly copies of each other. It uses h + 50 lags (`mm.signals.spearman_ic_newey_west`).
- **Overstatement:** the naive t-stat is 3–11x too large across these cells.
- **Lag choice barely matters:** at h=50, doubling the lags from 100 to 200 moves the Newey-West t-stat AAPL 22.5 → 21.2, AMZN 19.9 → 18.4, GOOG 13.0 → 12.3, INTC 25.8 → 24.6, MSFT 32.7 → 31.5.
