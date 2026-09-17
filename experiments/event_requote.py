"""Hypothesis 1: quotes lose money mainly because they go stale. Requoting when the micro-price moves, on top
of the 6-second timer, should cut adverse selection.

Rule fixed before running: sweep the move threshold on AAPL and pick the one with the best total P&L averaged
over both fill presets. Run it unchanged on the other four. Supported if adverse selection per passive share
and total P&L both improve at both presets. Writes docs/event-requote.md.

Usage: python -m experiments.event_requote
"""

import gc
from dataclasses import dataclass, replace

import pandas as pd

from experiments.common import ROOT, Setup, backtest, load, quoter, save
from mm.queue import OPTIMISTIC, PESSIMISTIC

PRESETS = {"pessimistic": PESSIMISTIC, "optimistic": OPTIMISTIC}
KEEP = ("pnl_total_at_close", "pnl_spread_passive", "pnl_adverse_selection", "pnl_adverse_selection_passive",
        "pnl_crossing", "pnl_inventory", "shares_passive", "shares_forced", "n_fills", "n_quotes_placed")


@dataclass(frozen=True)
class Config(Setup):
    thresholds: tuple = (None, 3.0, 2.0, 1.0, 0.5)  # None = timer only, the baseline


def runs(m, ticker: str, cfg: Config, thresholds) -> list[dict]:
    rows = []
    for ticks in thresholds:
        for name, model in PRESETS.items():
            run = replace(cfg, fill_model=model, requote_move_ticks=ticks)
            s = backtest(m, quoter(m, run), run)
            row = {"ticker": ticker, "move_ticks": ticks, "fills": name, **{k: s.get(k) for k in KEEP}}
            shares = max(1, row["shares_passive"])
            row["spread_cents_per_passive_share"] = 100 * row["pnl_spread_passive"] / shares
            row["adverse_cents_per_passive_share"] = 100 * row["pnl_adverse_selection_passive"] / shares
            row["net_cents_per_passive_share"] = (row["spread_cents_per_passive_share"]
                                                  + row["adverse_cents_per_passive_share"])
            rows.append(row)
    return rows


def measure(cfg: Config) -> tuple[pd.DataFrame, float]:
    m = load(cfg.train_ticker, cfg)
    sweep = pd.DataFrame(runs(m, cfg.train_ticker, cfg, cfg.thresholds))
    del m
    gc.collect()
    tried = sweep[sweep.move_ticks.notna()]
    chosen = float(tried.groupby("move_ticks").pnl_total_at_close.mean().idxmax())

    rows = []
    for ticker in cfg.tickers:  # one ticker in memory at a time
        if ticker == cfg.train_ticker:
            continue
        m = load(ticker, cfg)
        rows += runs(m, ticker, cfg, (None, chosen))
        del m
        gc.collect()
    return pd.concat([sweep, pd.DataFrame(rows)], ignore_index=True), chosen


def _pair(df, col, fmt):
    lo, hi = (df[df.fills == f][col].iloc[0] for f in PRESETS)
    return f"{fmt(lo)} / {fmt(hi)}"


def markdown(df: pd.DataFrame, chosen: float, cfg: Config) -> str:
    money, cents, count = "{:,.0f}".format, "{:+.2f}".format, (lambda v: f"{int(v):,}")
    label = lambda t: "timer only" if pd.isna(t) else f"{t:g} tick" + ("" if t == 1 else "s")
    cols = [("pnl_total_at_close", "Total P&L", money),
            ("spread_cents_per_passive_share", "Spread ¢/share", cents),
            ("adverse_cents_per_passive_share", "Adverse sel. ¢/share", cents),
            ("net_cents_per_passive_share", "Net ¢/share", cents),
            ("pnl_crossing", "Crossing cost", money), ("n_quotes_placed", "Quotes sent", count)]
    head = "| | " + " | ".join(c[1] for c in cols) + " |\n" + "|---" * (len(cols) + 1) + "|"

    train = df[df.ticker == cfg.train_ticker]
    sweep = [f"| {label(t)} | " + " | ".join(_pair(g, c, f) for c, _, f in cols) + " |"
             for t, g in train.groupby("move_ticks", dropna=False, sort=False)]

    oos = []
    better = {(crit, f): 0 for crit in ("pnl_total_at_close", "adverse_cents_per_passive_share",
                                        "net_cents_per_passive_share", "pnl_crossing") for f in PRESETS}
    for ticker in cfg.tickers:
        g = df[(df.ticker == ticker) & (df.move_ticks.isna() | (df.move_ticks == chosen))]
        for t, h in g.groupby("move_ticks", dropna=False, sort=False):
            oos.append(f"| {ticker}, {label(t)} | " + " | ".join(_pair(h, c, f) for c, _, f in cols) + " |")
        base, new = g[g.move_ticks.isna()].set_index("fills"), g[g.move_ticks == chosen].set_index("fills")
        for crit, f in better:
            better[crit, f] += new.loc[f, crit] > base.loc[f, crit]
    n = len(cfg.tickers)
    tally = lambda crit: f"{better[crit, 'pessimistic']} / {better[crit, 'optimistic']} of {n}"

    return f"""# Does requoting on price moves cut adverse selection?

Every cell is **pessimistic / optimistic** fills. Dollars over one day (LOBSTER, 2012-06-21).
Regenerate with `python -m experiments.event_requote`.

## Sweep on {cfg.train_ticker} (the only ticker tuned on)

Each row requotes every {cfg.requote_seconds:g}s and also whenever the micro-price moves that far since the last quote.

{head}
{chr(10).join(sweep)}

**Chosen: {label(chosen)}**, the best total P&L averaged over both presets.

## All five tickers at {label(chosen)}

{head}
{chr(10).join(oos)}

Tickers improved, pessimistic / optimistic:

- Net per passive share: {tally('net_cents_per_passive_share')}
- Adverse selection per passive share: {tally('adverse_cents_per_passive_share')}
- Crossing cost: {tally('pnl_crossing')}
- Total P&L: {tally('pnl_total_at_close')}

Column meanings:

- **Spread ¢/share:** what each passive share earned against the mid at the moment it filled.
- **Adverse sel. ¢/share:** how far the mid then moved against it over the next 100 events. Closer to zero is better.
- **Net ¢/share:** the two together: what a passive share was worth 100 events after it filled.
- **Crossing cost:** what forced flattens paid to cross the spread once inventory passed the threshold.
- **Quotes sent:** requote decisions. An exchange sees each one as cancel-and-replace messages.
"""


def main(cfg=Config()):
    df, chosen = measure(cfg)
    text = markdown(df, chosen, cfg)
    with open(ROOT / "docs" / "event-requote.md", "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(text)
    save("event_requote", cfg, {"runs": df})


if __name__ == "__main__":
    main()
