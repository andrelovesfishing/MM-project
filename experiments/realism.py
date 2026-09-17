"""Measure one realism change: run the full model on all five tickers and add a row to docs/realism.md.

Usage: python -m experiments.realism "what changed" [pessimistic | optimistic | fill_switch=value ...]
Each simulator fix lands in its own commit with its row, so the table reads as a ladder of assumptions.
"""

import gc
import sys
from dataclasses import replace

import pandas as pd

from experiments.common import ROOT, Setup, backtest, load, quoter, save
from mm.queue import OPTIMISTIC, PESSIMISTIC, FillModel

TABLE = ROOT / "docs" / "realism.md"
COLUMNS = ("| Change | AAPL realized | AAPL total | AAPL fills | AAPL forced flattens "
           "| 5-ticker realized | 5-ticker total | 5-ticker fills |")


def measure(cfg: Setup) -> pd.DataFrame:
    rows = []
    for ticker in cfg.tickers:  # one ticker in memory at a time
        m = load(ticker, cfg)
        rows.append({**backtest(m, quoter(m, cfg), cfg), "ticker": ticker})
        del m
        gc.collect()
    return pd.DataFrame(rows)


def table_row(change: str, df: pd.DataFrame, train: str) -> str:
    a = df.set_index("ticker").loc[train]
    return (f"| {change} | {a.final_pnl_realized:,.2f} | {a.final_pnl_total:,.2f} | {int(a.n_fills):,} "
            f"| {int(a.n_forced_flatten_crosses):,} | {df.final_pnl_realized.sum():,.2f} "
            f"| {df.final_pnl_total.sum():,.2f} | {df.n_fills.sum():,} |")


def fill_model(args: list[str]) -> FillModel:
    presets = {"pessimistic": PESSIMISTIC, "optimistic": OPTIMISTIC}
    model = FillModel()
    for arg in args:
        if arg in presets:
            model = presets[arg]
        else:
            key, value = arg.split("=")
            model = replace(model, **{key: {"true": True, "false": False}.get(value, value)})
    return model


def main(change: str, cfg=Setup()):
    df = measure(cfg)
    print(df[["ticker", "final_pnl_realized", "final_pnl_total", "n_fills", "n_forced_flatten_crosses"]]
          .to_string(index=False))
    row = table_row(change, df, cfg.train_ticker)
    with open(TABLE, "a", encoding="utf-8", newline="") as f:
        f.write(row + "\n")
    print(row)
    save("realism", cfg, {"realism": df})


if __name__ == "__main__":
    main(sys.argv[1], Setup(fill_model=fill_model(sys.argv[2:])))
