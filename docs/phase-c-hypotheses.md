# Phase C: strategy experiments

Ground rules, as agreed before Phase A:

- **One hypothesis per experiment.** Write it down, with what would count as support, before running anything.
- **Tune on AAPL only,** then run the same settings unchanged on AMZN, GOOG, INTC and MSFT.
- **Report the pessimistic–optimistic `FillModel` range,** not a single number (Phase B).
- **One script per experiment** in `experiments/`, driven by a config dataclass. Results go to `results/<name>/` next to their config.
- **Run order: 4, 1, 3, 2.** #4 is cheap and decides whether the OFI signal is real before #2 builds a strategy on it.
- **Default `FillModel` stays as the original fill rules.** Every result here is reported at both presets anyway, and changing the default would break comparisons along the realism ladder.

## 1. Requote on events instead of a 6-second timer

**Hypothesis:** quotes lose money mainly because they go stale. Requoting when the best price or micro-price moves by more than a threshold, instead of every 6s, should cut adverse selection.

**Evidence:** on AAPL, 1,890 of 2,697 passive fills landed 1–19 ticks past the prior best price. Only 84 fills came from a quote that had crossed the market. So the market was running through quotes that were up to 6s old.
*Those counts come from the old `all_main.py` after the fill fixes. Recheck them on the Phase B simulator before relying on them.*

**Test:** add an event-driven requote trigger next to `engine.Timer` and compare adverse selection (markouts) and P&L attribution against the timer. Sweep the threshold on AAPL only.

## 2. OFI as a reservation-price skew, not only widening

**Hypothesis:** rolling OFI predicts the mid-price about 50 events ahead (Spearman IC 0.2066 at h=50 on AAPL). Moving both quotes in the predicted direction should beat the current `OFIGuard`, which only widens the side about to be run over.

**Test:** a new strategy component that shifts the reservation price by a multiple of OFI z, compared against `OFIGuard` and against no OFI use.

## 3. The 2x2: adaptive size vs requote cadence

**Hypothesis:** the old cross-ticker improvement came from two changes made at the same time, and their effects were never separated:

- order size moved from a fixed share count to a fraction of each ticker's touch depth (`adaptive_limits`)
- requoting moved from every N events to every N seconds of market time

**Test:** all four combinations (fixed / adaptive size × event-count / time cadence) on all five tickers. This shows which change mattered, and on which tickers.

## 4. Newey-West-corrected IC t-stats

**Hypothesis:** the OFI IC t-stats (~133 at h=50) are hugely overstated. They treat about 400k overlapping, autocorrelated observations as independent.

**Test:** recompute the t-stats with Newey-West (HAC) standard errors, with the lag at least the forecast horizon. Report both. If significance survives, say so plainly; if it shrinks, lead with the corrected number.
