"""Hypothesis 2: moving both quotes towards where OFI predicts the mid is going beats OFIGuard, which only widens
the side about to be run over.

Rule fixed before running: sweep ticks_per_z on AAPL and pick the one with the best total P&L averaged over both
fill presets. Run it unchanged on the other four, against OFIGuard (the Phase B baseline) and against no OFI use.
Supported if the skew beats OFIGuard on both total P&L and net cents per passive share, at both presets, on at
least 4 of 5 tickers. Writes docs/ofi-skew.md.

Usage: python -m experiments.ofi_skew
"""

import gc
from dataclasses import dataclass, replace

import pandas as pd

from experiments.common import ROOT, Setup, backtest, load, quoter, save
from experiments.event_requote import KEEP, PRESETS, _pair
from mm.strategy import OFISkew

GUARD, NONE = "OFI guard", "no OFI"


@dataclass(frozen=True)
class Config(Setup):
    ticks_per_z: tuple = (0.25, 0.5, 1.0, 2.0)
    max_ticks: float = 4.0


def skew_label(k: float) -> str:
    return f"skew {k:g} tick/z"


def arms(cfg: Config, ks) -> dict[str, dict]:
    out = {NONE: dict(ofi_guard=None), GUARD: {}}
    for k in ks:
        out[skew_label(k)] = dict(ofi_guard=None, ofi_skew=OFISkew(ticks_per_z=k, max_ticks=cfg.max_ticks))
    return out


def runs(m, ticker: str, cfg: Config, ks) -> list[dict]:
    rows = []
    for arm, overrides in arms(cfg, ks).items():
        for name, model in PRESETS.items():
            run = replace(cfg, fill_model=model)
            s = backtest(m, quoter(m, run, **overrides), run)
            row = {"ticker": ticker, "arm": arm, "fills": name, **{k: s.get(k) for k in KEEP}}
            shares = max(1, row["shares_passive"])
            row["spread_cents_per_passive_share"] = 100 * row["pnl_spread_passive"] / shares
            row["adverse_cents_per_passive_share"] = 100 * row["pnl_adverse_selection_passive"] / shares
            row["net_cents_per_passive_share"] = (row["spread_cents_per_passive_share"]
                                                  + row["adverse_cents_per_passive_share"])
            rows.append(row)
    return rows


def measure(cfg: Config) -> tuple[pd.DataFrame, str]:
    m = load(cfg.train_ticker, cfg)
    sweep = pd.DataFrame(runs(m, cfg.train_ticker, cfg, cfg.ticks_per_z))
    del m
    gc.collect()
    tried = sweep[sweep.arm.str.startswith("skew")]
    chosen = tried.groupby("arm").pnl_total_at_close.mean().idxmax()
    k = cfg.ticks_per_z[[skew_label(k) for k in cfg.ticks_per_z].index(chosen)]

    rows = []
    for ticker in cfg.tickers:  # one ticker in memory at a time
        if ticker == cfg.train_ticker:
            continue
        m = load(ticker, cfg)
        rows += runs(m, ticker, cfg, (k,))
        del m
        gc.collect()
    return pd.concat([sweep, pd.DataFrame(rows)], ignore_index=True), chosen


def markdown(df: pd.DataFrame, chosen: str, cfg: Config) -> str:
    money, cents = "{:,.0f}".format, "{:+.2f}".format
    cols = [("pnl_total_at_close", "Total P&L", money),
            ("spread_cents_per_passive_share", "Spread ¢/share", cents),
            ("adverse_cents_per_passive_share", "Adverse sel. ¢/share", cents),
            ("net_cents_per_passive_share", "Net ¢/share", cents),
            ("pnl_crossing", "Crossing cost", money),
            ("shares_passive", "Passive shares", "{:,.0f}".format)]
    head = "| | " + " | ".join(c[1] for c in cols) + " |\n" + "|---" * (len(cols) + 1) + "|"
    line = lambda name, g: f"| {name} | " + " | ".join(_pair(g, c, f) for c, _, f in cols) + " |"

    train = df[df.ticker == cfg.train_ticker]
    sweep = [line(arm, g) for arm, g in train.groupby("arm", sort=False)]

    oos = []
    crits = ("pnl_total_at_close", "net_cents_per_passive_share", "adverse_cents_per_passive_share")
    vs = {(base, crit, f): 0 for base in (GUARD, NONE) for crit in crits for f in PRESETS}
    for ticker in cfg.tickers:
        g = df[(df.ticker == ticker) & df.arm.isin((NONE, GUARD, chosen))]
        for arm, h in g.groupby("arm", sort=False):
            oos.append(line(f"{ticker}, {arm}", h))
        new = g[g.arm == chosen].set_index("fills")
        for base, crit, f in vs:
            vs[base, crit, f] += new.loc[f, crit] > g[g.arm == base].set_index("fills").loc[f, crit]
    n = len(cfg.tickers)
    tally = lambda base, crit: f"{vs[base, crit, 'pessimistic']} / {vs[base, crit, 'optimistic']} of {n}"

    return f"""# Does skewing quotes with OFI beat widening against it?

Every cell is **pessimistic / optimistic** fills. Dollars over one day (LOBSTER, 2012-06-21).
All runs requote on the {cfg.requote_seconds:g}s timer. Regenerate with `python -m experiments.ofi_skew`.

- **OFI guard:** the Phase B baseline. Widens the side about to be run over when |OFI z| > 2.
- **Skew k tick/z:** no guard. The reservation price moves k ticks per unit of OFI z (capped at {cfg.max_ticks:g}), so both quotes lean the predicted way.
- **No OFI:** neither.

## Sweep on {cfg.train_ticker} (the only ticker tuned on)

{head}
{chr(10).join(sweep)}

**Chosen: {chosen}**, the best total P&L averaged over both presets.

## All five tickers

{head}
{chr(10).join(oos)}

Tickers where the chosen skew does better, pessimistic / optimistic:

| | vs OFI guard | vs no OFI |
|---|---|---|
| Total P&L | {tally(GUARD, 'pnl_total_at_close')} | {tally(NONE, 'pnl_total_at_close')} |
| Net per passive share | {tally(GUARD, 'net_cents_per_passive_share')} | {tally(NONE, 'net_cents_per_passive_share')} |
| Adverse selection per passive share | {tally(GUARD, 'adverse_cents_per_passive_share')} | {tally(NONE, 'adverse_cents_per_passive_share')} |

Column meanings are as in [event-requote.md](event-requote.md). **Passive shares** is volume filled by resting quotes.
"""


def main(cfg=Config()):
    df, chosen = measure(cfg)
    text = markdown(df, chosen, cfg)
    with open(ROOT / "docs" / "ofi-skew.md", "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(text)
    save("ofi_skew", cfg, {"runs": df})


if __name__ == "__main__":
    main()
