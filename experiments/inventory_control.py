"""Hypothesis 5: with 1-tick event requoting, the extra volume trips the hard flatten far more often, and its
crossing cost eats the per-share gain. Controlling inventory earlier and more gently should keep the gain.

The Phase B inventory skew barely acts: gamma 0.1 x 1 tick per 100 shares moves quotes ~0.05 ticks at the AAPL
flatten threshold. Candidates, each one change on top of event requoting: a stronger inventory skew, a later
flatten (flatten_frac 1.0 crosses only when latency lets inventory overshoot the limit), or a size skew that
stops quoting the side that adds inventory.

Rule fixed before running: pick the candidate with the best total P&L averaged over both presets on AAPL. Run it
unchanged on the other four. Supported if event requoting plus that control beats the Phase B 6s timer on total
P&L at both presets on at least 4 of 5 tickers, and also beats it on net cents per passive share at both presets
on at least 4 of 5 (so the gain doesn't come from simply trading less). Writes docs/inventory-control.md.

Usage: python -m experiments.inventory_control
"""

import gc
from dataclasses import dataclass, replace

import pandas as pd

from experiments.common import ROOT, Setup, backtest, load, quoter, save
from experiments.event_requote import KEEP, PRESETS, _pair
from mm.strategy import InventorySkew, SizeSkew

TIMER, EVENT = "6s timer (Phase B)", "1-tick requote"


@dataclass(frozen=True)
class Config(Setup):
    move_ticks: float = 1.0
    skew_ticks_per_100: tuple = (10.0, 20.0, 40.0)
    flatten_fracs: tuple = (0.75, 1.0)
    size_skew_min_frac: float = 0.0


def candidates(cfg: Config) -> dict[str, dict]:
    out = {f"+ inventory skew {k:g} ticks/100sh": dict(inventory_skew=InventorySkew(ticks_per_100_shares=k))
           for k in cfg.skew_ticks_per_100}
    out |= {("+ flatten only past the limit" if f >= 1 else f"+ flatten at {f:g}x limit"): dict(flatten_frac=f)
            for f in cfg.flatten_fracs}
    out[f"+ size skew to {cfg.size_skew_min_frac:g}"] = dict(size_skew=SizeSkew(cfg.size_skew_min_frac))
    return out


def runs(m, ticker: str, cfg: Config, arms: dict[str, dict]) -> list[dict]:
    rows = []
    for arm, overrides in arms.items():
        move = None if arm == TIMER else cfg.move_ticks
        for name, model in PRESETS.items():
            run = replace(cfg, fill_model=model, requote_move_ticks=move)
            s = backtest(m, quoter(m, run, **overrides), run)
            row = {"ticker": ticker, "arm": arm, "fills": name, **{k: s.get(k) for k in KEEP}}
            shares = max(1, row["shares_passive"])
            row["spread_cents_per_passive_share"] = 100 * row["pnl_spread_passive"] / shares
            row["adverse_cents_per_passive_share"] = 100 * row["pnl_adverse_selection_passive"] / shares
            row["net_cents_per_passive_share"] = (row["spread_cents_per_passive_share"]
                                                  + row["adverse_cents_per_passive_share"])
            # Mark-to-market on inventory held is mostly the day's price path, not quoting skill
            row["pnl_ex_inventory"] = row["pnl_total_at_close"] - row["pnl_inventory"]
            rows.append(row)
    return rows


def measure(cfg: Config) -> tuple[pd.DataFrame, str]:
    cands = candidates(cfg)
    m = load(cfg.train_ticker, cfg)
    sweep = pd.DataFrame(runs(m, cfg.train_ticker, cfg, {TIMER: {}, EVENT: {}, **cands}))
    del m
    gc.collect()
    chosen = sweep[sweep.arm.isin(cands)].groupby("arm").pnl_total_at_close.mean().idxmax()

    rows = []
    for ticker in cfg.tickers:  # one ticker in memory at a time
        if ticker == cfg.train_ticker:
            continue
        m = load(ticker, cfg)
        rows += runs(m, ticker, cfg, {TIMER: {}, EVENT: {}, chosen: cands[chosen]})
        del m
        gc.collect()
    return pd.concat([sweep, pd.DataFrame(rows)], ignore_index=True), chosen


def markdown(df: pd.DataFrame, chosen: str, cfg: Config) -> str:
    money, cents = "{:,.0f}".format, "{:+.2f}".format
    cols = [("pnl_total_at_close", "Total P&L", money),
            ("net_cents_per_passive_share", "Net ¢/share", cents),
            ("pnl_crossing", "Crossing cost", money),
            ("shares_passive", "Passive shares", money),
            ("shares_forced", "Forced shares", money)]
    head = "| | " + " | ".join(c[1] for c in cols) + " |\n" + "|---" * (len(cols) + 1) + "|"
    line = lambda name, g: f"| {name} | " + " | ".join(_pair(g, c, f) for c, _, f in cols) + " |"

    train = df[df.ticker == cfg.train_ticker]
    sweep = [line(arm, g) for arm, g in train.groupby("arm", sort=False)]

    oos = []
    crits = ("pnl_total_at_close", "pnl_ex_inventory", "net_cents_per_passive_share", "pnl_crossing")
    vs = {(base, crit, f): 0 for base in (TIMER, EVENT) for crit in crits for f in PRESETS}
    for ticker in cfg.tickers:
        g = df[(df.ticker == ticker) & df.arm.isin((TIMER, EVENT, chosen))]
        for arm, h in g.groupby("arm", sort=False):
            oos.append(line(f"{ticker}, {arm}", h))
        new = g[g.arm == chosen].set_index("fills")
        for base, crit, f in vs:
            vs[base, crit, f] += new.loc[f, crit] > g[g.arm == base].set_index("fills").loc[f, crit]
    n = len(cfg.tickers)
    tally = lambda base, crit: f"{vs[base, crit, 'pessimistic']} / {vs[base, crit, 'optimistic']} of {n}"

    return f"""# Can gentler inventory control keep the gain from event requoting?

Every cell is **pessimistic / optimistic** fills. Dollars over one day (LOBSTER, 2012-06-21).
Regenerate with `python -m experiments.inventory_control`.

- **{TIMER}:** the Phase B baseline.
- **{EVENT}:** #1's winner. Requote when the micro-price moves {cfg.move_ticks:g} tick, with Phase B inventory controls.
- **+ ...:** {EVENT} with one inventory control changed.

## Sweep on {cfg.train_ticker} (the only ticker tuned on)

{head}
{chr(10).join(sweep)}

**Chosen: {EVENT} {chosen}**, the best total P&L averaged over both presets.

## All five tickers

{head}
{chr(10).join(oos)}

Tickers where the chosen setup does better, pessimistic / optimistic:

| | vs {TIMER} | vs {EVENT} |
|---|---|---|
| Total P&L | {tally(TIMER, 'pnl_total_at_close')} | {tally(EVENT, 'pnl_total_at_close')} |
| Total P&L excluding inventory mark-to-market | {tally(TIMER, 'pnl_ex_inventory')} | {tally(EVENT, 'pnl_ex_inventory')} |
| Net per passive share | {tally(TIMER, 'net_cents_per_passive_share')} | {tally(EVENT, 'net_cents_per_passive_share')} |
| Crossing cost | {tally(TIMER, 'pnl_crossing')} | {tally(EVENT, 'pnl_crossing')} |

Column meanings are as in [event-requote.md](event-requote.md). **Forced shares** were crossed by a flatten.
"""


def main(cfg=Config()):
    df, chosen = measure(cfg)
    text = markdown(df, chosen, cfg)
    with open(ROOT / "docs" / "inventory-control.md", "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(text)
    save("inventory_control", cfg, {"runs": df})


if __name__ == "__main__":
    main()
