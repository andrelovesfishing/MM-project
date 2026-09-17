# Headline: the full model on five stocks

Dollars over one day (LOBSTER sample, 2012-06-21), shown as **pessimistic / optimistic** fills (`mm/queue.py` presets).
Strategy tuned on AAPL only; the other four are out of sample. Regenerate with `python -m experiments.headline`.

| | AAPL | AMZN | GOOG | INTC | MSFT | All five |
|---|---|---|---|---|---|---|
| Total P&L | -509 / -411 | -317 / -296 | -319 / -506 | -630 / -1,021 | -625 / -1,575 | -2,400 / -3,809 |
| Spread captured | 661 / 976 | 248 / 392 | 591 / 828 | 122 / 1,445 | -29 / 1,665 | 1,594 / 5,306 |
| Adverse selection | -1,213 / -1,376 | -423 / -504 | -862 / -1,040 | -446 / -1,367 | -516 / -2,062 | -3,461 / -6,349 |
| Crossing cost | -77 / -90 | -49 / -60 | -95 / -110 | 0 / -5 | -2 / -12 | -223 / -277 |
| Inventory | 119 / 79 | -94 / -124 | 47 / -184 | -305 / -1,095 | -77 / -1,166 | -311 / -2,489 |
| Fills | 2,416 / 2,394 | 1,017 / 1,100 | 1,145 / 1,087 | 424 / 1,578 | 500 / 1,993 | 5,502 / 8,152 |

- **Spread captured:** what passive fills earned against the mid at the moment they filled.
- **Adverse selection:** how far the mid moved against those fills over the next 100 events.
- **Crossing cost:** what forced flattens paid to cross the spread.
- **Inventory:** the mid's move from 100 events after each fill to the close.
- The four parts add up exactly to total P&L, marked at the closing mid (`mm.metrics.attribution`).
