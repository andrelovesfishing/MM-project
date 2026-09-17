"""Order flow imbalance (OFI) and tools for testing whether a signal predicts returns."""

import numpy as np
import pandas as pd
from scipy import stats


def _side_ofi(price, size, better_when_up: bool):
    price_diff = np.diff(price, prepend=price[0])
    size_diff = np.diff(size, prepend=size[0])
    prev_size = np.concatenate(([size[0]], size[:-1]))
    improved = price_diff > 0 if better_when_up else price_diff < 0
    return np.where(improved, size, np.where(price_diff == 0, size_diff, -prev_size))


def ofi(bid_px, bid_sz, ask_px, ask_sz):
    """Cont-Kukanov-Stoikov OFI per event: net buying pressure added at the touch."""
    return _side_ofi(bid_px, bid_sz, True) - _side_ofi(ask_px, ask_sz, False)


def rolling_sum(x, window: int):
    cs = np.cumsum(np.insert(x, 0, 0))
    out = np.full(len(x), np.nan)
    out[window - 1:] = cs[window:] - cs[:-window]
    return out


def rolling_zscore(x, window: int):
    s = pd.Series(x)
    roll = s.rolling(window, min_periods=window // 4)
    z = (s - roll.mean()) / roll.std().replace(0, np.nan)
    return z.fillna(0.0).to_numpy()


def forward_change(x, horizon: int):
    out = np.full(len(x), np.nan)
    out[:-horizon] = x[horizon:] - x[:-horizon]
    return out


def ic_table(signal, price, horizons) -> pd.DataFrame:
    """Spearman rank correlation between the signal and the price change h events ahead."""
    rows = []
    for h in horizons:
        fwd = forward_change(price, h)
        ok = ~np.isnan(signal) & ~np.isnan(fwd)
        ic, p = stats.spearmanr(signal[ok], fwd[ok])
        n = int(ok.sum())
        rows.append({"horizon_events": h, "n_obs": n, "spearman_IC": ic,
                     "t_stat": ic * np.sqrt((n - 2) / (1 - ic**2)), "p_value": p})
    return pd.DataFrame(rows)


def deciles(signal, price, horizon: int) -> pd.DataFrame:
    fwd = forward_change(price, horizon)
    ok = ~np.isnan(signal) & ~np.isnan(fwd)
    df = pd.DataFrame({"signal": signal[ok], "fwd": fwd[ok]})
    df["decile"] = pd.qcut(df["signal"], 10, labels=False, duplicates="drop")
    return df.groupby("decile").agg(mean_signal=("signal", "mean"), mean_fwd=("fwd", "mean"),
                                    n=("fwd", "count")).reset_index()


def trade_distance_kappa(trade_px, mid_at_trade, tick: int, n_buckets=15, max_ticks=20):
    """Fit count ~ A exp(-kappa * ticks from mid) to executed trades.

    Diagnostic only. It measures where trades happen, not true arrival rates, so it is
    not used to set kappa in the strategy.
    """
    dist = np.abs(trade_px - mid_at_trade) / tick
    counts, edges = np.histogram(dist[dist <= max_ticks], bins=np.linspace(0, max_ticks, n_buckets + 1))
    centers = (edges[:-1] + edges[1:]) / 2
    ok = counts > 0
    fit = stats.linregress(centers[ok], np.log(counts[ok]))
    return {"A": np.exp(fit.intercept), "kappa": -fit.slope, "r2": fit.rvalue**2}
