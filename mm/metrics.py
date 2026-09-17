"""Turn a backtest result into dollar-denominated performance and diagnostic numbers."""

import numpy as np

from mm.data import Market, dollars
from mm.engine import Result
from mm.strategy import ofi_z

MARKOUT_HORIZONS = (100, 500, 1000)
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600


def pnl_series(result: Result, market: Market) -> dict:
    s = result.samples
    mid = market.mid[s["idx"]]
    total = dollars(s["cash"] + s["inventory"] * mid)
    realized = dollars(s["realized"])
    unrealized = np.where(s["inventory"] != 0, dollars(s["inventory"] * (mid - s["avg_cost"])), 0.0)
    return {"time": market.time[s["idx"]], "total": total, "realized": realized,
            "unrealized": unrealized, "inventory": s["inventory"]}


def markouts(result: Result, market: Market, horizons=MARKOUT_HORIZONS) -> dict:
    """Dollars per share gained h events after each fill, marked at mid. NaN past the session end."""
    f = result.fills
    out = {}
    for h in horizons:
        j = f["idx"] + h
        fut = np.full(len(j), np.nan)
        ok = j < len(market)
        fut[ok] = market.mid[j[ok]]
        out[h] = dollars(f["side"] * (fut - f["price"]))
    return out


def sharpe_annualized(time, series, bar_seconds=60.0) -> float:
    """Sharpe of P&L changes over fixed time bars, scaled by sqrt(bars per trading year).
    Event samples are uneven in time, so they are resampled first. One day of data: indicative only."""
    edges = np.arange(time[0], time[-1] + 1e-9, bar_seconds)
    bars = np.diff(series[np.searchsorted(time, edges, side="right") - 1])
    sd = np.std(bars)
    return float(np.mean(bars) / sd * np.sqrt(TRADING_SECONDS_PER_YEAR / bar_seconds)) if sd > 0 else np.nan


def summary(result: Result, market: Market) -> dict:
    pnl = pnl_series(result, market)
    quotes = [q for _, q in result.quotes]
    f = result.fills
    n_fills = len(f["idx"])

    gaps = [g for q in quotes for g in q.touch_gaps_ticks]
    snapped = sum(q.n_snapped for q in quotes)
    tracked = snapped + sum(q.n_organic for q in quotes)
    forced_at = [i for i, q in result.quotes if (q.bid and q.bid.forced) or (q.ask and q.ask.forced)]
    z = ofi_z(market)

    m = {
        "final_pnl_total": pnl["total"][-1],
        "final_pnl_realized": pnl["realized"][-1],
        "final_pnl_unrealized": pnl["total"][-1] - pnl["realized"][-1],
        "sharpe_total_annualized": sharpe_annualized(pnl["time"], pnl["total"]),
        "sharpe_realized_annualized": sharpe_annualized(pnl["time"], pnl["realized"]),
        "max_drawdown": np.max(np.maximum.accumulate(pnl["total"]) - pnl["total"]),
        "max_abs_inventory": np.max(np.abs(pnl["inventory"])),
        "inventory_std": np.std(pnl["inventory"]),
        "n_fills": n_fills,
        "n_quotes_placed": len(quotes),
        "fill_rate": n_fills / max(1, len(quotes)),
        "mean_quote_distance_from_touch_ticks": np.mean(gaps) if gaps else np.nan,
        "frac_quotes_touch_snapped": snapped / tracked if tracked else np.nan,
        "n_forced_flatten_crosses": len(forced_at),
        "mean_ofi_z_at_forced_flatten": np.mean(z[forced_at]) if forced_at else np.nan,
    }
    if n_fills == 0:
        return m

    forced = f["forced"].astype(bool)
    for h, mk in markouts(result, market).items():
        m[f"mean_markout_{h}"] = np.nanmean(mk)
        if (~forced).any():
            m[f"mean_markout_{h}_passive"] = np.nanmean(mk[~forced])
        if forced.any():
            m[f"mean_markout_{h}_forced"] = np.nanmean(mk[forced])
    m["n_forced_fills"] = int(forced.sum())
    m["n_passive_fills"] = int((~forced).sum())
    m.update(crossing_cost(result, market))
    return m


def crossing_cost(result: Result, market: Market) -> dict:
    """What forced flattens paid versus mid, in total and per forced fill."""
    f = result.fills
    forced = f["forced"].astype(bool)
    per_share = f["side"][forced] * (f["price"][forced] - market.mid[f["idx"][forced]])
    total = float(dollars(np.sum(per_share * f["size"][forced])))
    n = int(forced.sum())
    return {"total_crossing_cost": total,
            "mean_crossing_cost_per_forced_fill": total / n if n else np.nan,
            "n_forced_fills_for_crossing_cost": n}
