# Phase C: strategy experiments

Ground rules, as agreed before Phase A:

- **One hypothesis per experiment.** Write it down, with what would count as support, before running anything.
- **Tune on AAPL only,** then run the same settings unchanged on AMZN, GOOG, INTC and MSFT.
- **Report the pessimistic–optimistic `FillModel` range,** not a single number (Phase B).
- **One script per experiment** in `experiments/`, driven by a config dataclass. Results go to `results/<name>/` next to their config.
- **Run order: 4, 1, 2, 3, 5.** #4 is cheap and decides whether the OFI signal is real before #2 builds a strategy on it. #5 was added after #1's result and runs last.
- **Default `FillModel` stays as the original fill rules.** Every result here is reported at both presets anyway, and changing the default would break comparisons along the realism ladder.

## 1. Requote on events instead of a 6-second timer

**Hypothesis:** quotes lose money mainly because they go stale. Requoting when the best price or micro-price moves by more than a threshold, instead of every 6s, should cut adverse selection.

**Evidence:** on AAPL, 1,890 of 2,697 passive fills landed 1–19 ticks past the prior best price. Only 84 fills came from a quote that had crossed the market. So the market was running through quotes that were up to 6s old.
*Those counts come from the old `all_main.py` after the fill fixes. Recheck them on the Phase B simulator before relying on them.*

**Test:** add an event-driven requote trigger next to `engine.Timer` and compare adverse selection (markouts) and P&L attribution against the timer. Sweep the threshold on AAPL only.

**Result ([event-requote.md](event-requote.md)):** not supported as stated, but the staleness idea was right about something else.
- Requoting on 1-tick micro-price moves (chosen on AAPL) turned passive quoting from losing 1–2.4¢ a share to about break-even, on all five tickers at both presets.
- The gain came from **spread at the moment of the fill**, not from less adverse selection afterwards. Adverse selection per share barely moved (3 of 5 tickers better). Stale quotes had been getting hit after the mid had already moved through them.
- Total P&L improved on 5 of 5 tickers with pessimistic fills but only 1 of 5 with optimistic ones. The extra volume pushes inventory past the flatten threshold far more often: on AAPL, forced-flatten shares rise from about 1.2k to 13k, and crossing cost from $90 to $971.
- So the bottleneck moves from quote staleness to inventory control. The large-tick stocks (INTC, MSFT) barely requote more, because their micro-price seldom moves a full tick.
- The old `all_main.py` counts above were never rechecked; this experiment tests the claim directly instead.

## 2. OFI as a reservation-price skew, not only widening

**Hypothesis:** rolling OFI predicts the mid-price about 50 events ahead (Spearman IC 0.2066 at h=50 on AAPL). Moving both quotes in the predicted direction should beat the current `OFIGuard`, which only widens the side about to be run over.

**Test:** a new strategy component that shifts the reservation price by a multiple of OFI z, compared against `OFIGuard` and against no OFI use.

**Result ([ofi-skew.md](ofi-skew.md)):** not supported. The signal is real but too small to trade on.
- The skew (2 ticks per z, chosen on AAPL) beat the guard on total P&L on 3 of 5 tickers pessimistic and 4 of 5 optimistic. Per passive share it won only 3 of 5 and 1 of 5, so it misses the bar.
- The per-share numbers barely move between skew, guard, and no OFI at all: usually within 0.1¢. Most of the P&L gaps on INTC and MSFT come from volume (the skew fills 10–25% fewer passive shares), not from better prices.
- Why: one unit of OFI z predicts about 0.6¢ of mid move on AAPL over the next 50 events, and 1.7¢ when |z| > 2. That's against a 15¢ average spread and about 4¢ a share of adverse selection. On INTC and MSFT it predicts 0.02¢ against a 1-tick spread.
- So statistical significance (#4) is not an edge. Newey-West t-stats of 13–33 come from hundreds of thousands of observations, not from a move large enough to pay for quoting around it.
- Caveat: the chosen strength was the largest in the sweep. Going past it after seeing the results would be tuning on the answer, so it's left as is.

## 3. The 2x2: adaptive size vs requote cadence

**Hypothesis:** the old cross-ticker improvement came from two changes made at the same time, and their effects were never separated:

- order size moved from a fixed share count to a fraction of each ticker's touch depth (`adaptive_limits`)
- requoting moved from every N events to every N seconds of market time

**Test:** all four combinations (fixed / adaptive size × event-count / time cadence) on all five tickers. This shows which change mattered, and on which tickers.

**Result ([size-cadence.md](size-cadence.md)):** not supported. The old diagnosis was wrong on every ticker it named, and the "fix" was mostly trading less.
- Size is the bigger effect almost everywhere, but not for the reason given. On AAPL, AMZN and GOOG, adaptive sizing cut orders from 200 to 20 shares. The strategy loses money on each share, so trading a tenth of the volume lost about a tenth as much ($5.7k better on AAPL).
- INTC and MSFT: "adaptive" means 500 shares, more than the fixed 200, and total P&L got *worse*. The old claim that 200 shares never reached the front of their queues doesn't hold on the Phase B simulator: they fill 24k–250k passive shares a day.
- GOOG: the predicted cadence effect points the wrong way. Requoting every 6s instead of every ~16s (100 events) lost more in total ($387 / $246), because fresher quotes filled more shares of a losing strategy. Per share it did help, by 0.4¢.
- Per share, cadence has no clean pattern: fresher quotes were better on four tickers and worse on AMZN.
- The P&L spread across tickers fell from $6.9k to $0.3k (pessimistic), but that is mostly every ticker losing less because of smaller size. It isn't evidence the strategy generalises.
- The lesson for every other comparison here: while passive quoting loses money per share, total P&L rewards whatever trades less. Judge strategy changes on per-share numbers first.

## 4. Newey-West-corrected IC t-stats

**Hypothesis:** the OFI IC t-stats (~133 at h=50) are hugely overstated. They treat about 400k overlapping, autocorrelated observations as independent.

**Test:** recompute the t-stats with Newey-West (HAC) standard errors, with the lag at least the forecast horizon. Report both. If significance survives, say so plainly; if it shrinks, lead with the corrected number.

**Result ([ofi-significance.md](ofi-significance.md)):** supported. The naive t-stats were 3–11x too large, but the signal survives: Newey-West t-stats of 13–33 at h=50 on all five stocks.

## 5. Inventory control under event requoting

Added after #1's result, before running anything for it.

**Hypothesis:** with 1-tick event requoting, the passive quotes are about break-even per share, but the extra volume trips the hard flatten far more often (AAPL forced shares 1.2k → 13k, crossing cost $90 → $971). Controlling inventory earlier and more gently should keep the per-share gain without paying the crossing cost.

**Test:** on top of 1-tick event requoting, compare the Phase B inventory controls against stronger passive ones (inventory skew, size skew) and a later flatten threshold. The baseline here is event requoting at 1 tick, not the 6s timer, since the question only exists once #1's change is in.

**Result ([inventory-control.md](inventory-control.md)):** supported. Event requoting plus flattening only past the hard limit is the first setup that beats the Phase B baseline across the board.
- Chosen on AAPL out of six candidates: stop flattening at half the limit, and cross only when latency lets inventory overshoot it. Forced shares on AAPL fall from 7.4k to 1.6k (pessimistic), and crossing cost from $528 to $127.
- Against the 6s timer: better total P&L on 5 of 5 tickers pessimistic and 4 of 5 optimistic (MSFT optimistic is the miss), and better net ¢ per passive share on 5 of 5 at both. AAPL makes money for the first time: +$289 / +$9.
- Luck check: about half of AAPL's gain is mark-to-market on inventory held while the price drifted, which is one day's price path, not skill. With that term removed it still beats the timer on 5 of 5 tickers at both presets.
- The Phase B inventory skew was doing almost nothing: at gamma 0.1 it moves quotes about 0.05 ticks at the flatten threshold. Making it 40x stronger helped AAPL a little but far less than removing the early flatten. The early flatten itself was the cost.
- The size skew had the lowest crossing cost but trades 12% fewer shares at worse per-share prices. After #3, that's the pattern to be suspicious of.
- Risk not priced here: letting inventory run to the full limit means holding bigger positions through the day. One day of data can't say whether that risk pays on average.
