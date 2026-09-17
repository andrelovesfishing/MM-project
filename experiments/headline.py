"""Headline result: the full model on all five tickers under both ends of the fill assumptions,
with P&L split into where it came from. Writes docs/headline.md.

Usage: python -m experiments.headline
"""

import gc
from dataclasses import replace

import pandas as pd

from experiments.common import ROOT, Setup, backtest, load, quoter, save
from mm.queue import OPTIMISTIC, PESSIMISTIC

PRESETS = {"pessimistic": PESSIMISTIC, "optimistic": OPTIMISTIC}
PARTS = [("pnl_total_at_close", "Total P&L"), ("pnl_spread_passive", "Spread captured"),
         ("pnl_adverse_selection", "Adverse selection"), ("pnl_crossing", "Crossing cost"),
         ("pnl_inventory", "Inventory")]


def measure(cfg: Setup) -> pd.DataFrame:
    rows = []
    for ticker in cfg.tickers:  # one ticker in memory at a time
        m = load(ticker, cfg)
        for name, model in PRESETS.items():
            run = replace(cfg, fill_model=model)
            rows.append({**backtest(m, quoter(m, run), run), "ticker": ticker, "fills": name})
        del m
        gc.collect()
    return pd.DataFrame(rows)


def markdown(df: pd.DataFrame, cfg: Setup) -> str:
    wide = df.set_index(["ticker", "fills"])
    tickers = list(cfg.tickers)

    def cell(ticker, col, fmt):
        lo, hi = (wide.loc[(ticker, f), col] for f in PRESETS)
        return f"{fmt(lo)} / {fmt(hi)}"

    money = "{:,.0f}".format
    lines = ["| | " + " | ".join(tickers) + " | All five |", "|---" * (len(tickers) + 2) + "|"]
    for col, label in PARTS:
        totals = [f"{money(df[df.fills == f][col].sum())}" for f in PRESETS]
        lines.append(f"| {label} | " + " | ".join(cell(t, col, money) for t in tickers)
                     + f" | {' / '.join(totals)} |")
    fills = [f"{int(df[df.fills == f].n_fills.sum()):,}" for f in PRESETS]
    lines.append("| Fills | " + " | ".join(cell(t, "n_fills", lambda v: f"{int(v):,}") for t in tickers)
                 + f" | {' / '.join(fills)} |")
    return f"""# Headline: the full model on five stocks

Dollars over one day (LOBSTER sample, 2012-06-21), shown as **pessimistic / optimistic** fills (`mm/queue.py` presets).
Strategy tuned on {cfg.train_ticker} only; the other four are out of sample. Regenerate with `python -m experiments.headline`.

{chr(10).join(lines)}

- **Spread captured:** what passive fills earned against the mid at the moment they filled.
- **Adverse selection:** how far the mid moved against those fills over the next 100 events.
- **Crossing cost:** what forced flattens paid to cross the spread.
- **Inventory:** the mid's move from 100 events after each fill to the close.
- The four parts add up exactly to total P&L, marked at the closing mid (`mm.metrics.attribution`).
"""


def main(cfg=Setup()):
    df = measure(cfg)
    text = markdown(df, cfg)
    with open(ROOT / "docs" / "headline.md", "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(text)
    save("headline", cfg, {"headline": df})


if __name__ == "__main__":
    main()
