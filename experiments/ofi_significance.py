"""Hypothesis 4: the OFI IC t-stats (~133 at h=50 on AAPL) are overstated, because ~400k overlapping,
autocorrelated observations were treated as independent.

Supported if the Newey-West t-stats come out several times smaller. Nothing is tuned here, so all five
tickers are reported. Writes docs/ofi-significance.md.

Usage: python -m experiments.ofi_significance
"""

import gc
from dataclasses import dataclass

import numpy as np
import pandas as pd

from experiments.common import ROOT, Setup, load, save
from mm import signals


@dataclass(frozen=True)
class Config(Setup):
    ofi_window: int = 50
    horizons: tuple = (10, 50, 200, 500, 1000)
    lag_check_horizon: int = 50  # also rerun this horizon at double the lags, to show the choice doesn't matter


def measure(cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    tables, checks = [], []
    for ticker in cfg.tickers:  # one ticker in memory at a time
        m = load(ticker, cfg)
        roll = signals.rolling_sum(m.ofi, cfg.ofi_window)
        tables.append(signals.ic_table(roll, m.mid, cfg.horizons, cfg.ofi_window).assign(ticker=ticker))
        h = cfg.lag_check_horizon
        fwd = signals.forward_change(m.mid, h)
        ok = ~np.isnan(roll) & ~np.isnan(fwd)
        for lags in (h + cfg.ofi_window, 2 * (h + cfg.ofi_window)):
            _, t = signals.spearman_ic_newey_west(roll[ok], fwd[ok], lags)
            checks.append({"ticker": ticker, "horizon_events": h, "lags": lags, "t_stat_newey_west": t})
        del m, roll, fwd
        gc.collect()
    return pd.concat(tables, ignore_index=True), pd.DataFrame(checks)


def markdown(df: pd.DataFrame, checks: pd.DataFrame, cfg: Config) -> str:
    tickers = list(cfg.tickers)
    head = "| Horizon (events) | " + " | ".join(tickers) + " |"
    rule = "|---" * (len(tickers) + 1) + "|"
    wide = df.set_index(["horizon_events", "ticker"])
    rows = []
    for h in cfg.horizons:
        cells = [f"{wide.loc[(h, t), 'spearman_IC']:.3f} · {wide.loc[(h, t), 't_stat']:.0f} → "
                 f"**{wide.loc[(h, t), 't_stat_newey_west']:.1f}**" for t in tickers]
        rows.append(f"| {h} | " + " | ".join(cells) + " |")
    ratio = (df.t_stat / df.t_stat_newey_west)
    c = checks.pivot(index="ticker", columns="lags", values="t_stat_newey_west")
    lag_lo, lag_hi = c.columns
    lag_line = ", ".join(f"{t} {c.loc[t, lag_lo]:.1f} → {c.loc[t, lag_hi]:.1f}" for t in tickers)
    at_h = df[df.horizon_events == cfg.lag_check_horizon].t_stat_newey_west
    weak = df[df.p_value_newey_west >= 0.05]
    weak_line = (", ".join(f"{r.ticker} at h={r.horizon_events}" for r in weak.itertuples())
                 if len(weak) else "none")
    return f"""# Is the OFI signal statistically real?

**Yes, but far less emphatically than the naive numbers claimed.** Correcting for overlapping windows shrinks the
t-stats {ratio.min():.0f}–{ratio.max():.0f}x, yet at h={cfg.lag_check_horizon} they still run {at_h.min():.0f}–{at_h.max():.0f} on all five stocks.
Not significant at 5% after correction: {weak_line}. One day of data per stock, so this says the effect was real that day, not that it persists.

Rolling {cfg.ofi_window}-event OFI against the mid-price change h events ahead, on one day per stock (LOBSTER, 2012-06-21).
Each cell: **Spearman IC · naive t-stat → Newey-West t-stat**. Regenerate with `python -m experiments.ofi_significance`.

{head}
{rule}
{chr(10).join(rows)}

- **Naive t-stat:** treats every event as an independent observation.
- **Newey-West t-stat:** allows for the overlap. Consecutive {cfg.ofi_window}-event sums and h-event forward changes share almost all their data, so neighbouring observations are nearly copies of each other. It uses h + {cfg.ofi_window} lags (`mm.signals.spearman_ic_newey_west`).
- **Overstatement:** the naive t-stat is {ratio.min():.0f}–{ratio.max():.0f}x too large across these cells.
- **Lag choice barely matters:** at h={cfg.lag_check_horizon}, doubling the lags from {lag_lo} to {lag_hi} moves the Newey-West t-stat {lag_line}.
"""


def main(cfg=Config()):
    df, checks = measure(cfg)
    text = markdown(df, checks, cfg)
    with open(ROOT / "docs" / "ofi-significance.md", "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(text)
    save("ofi_significance", cfg, {"ic": df, "lag_check": checks})


if __name__ == "__main__":
    main()
