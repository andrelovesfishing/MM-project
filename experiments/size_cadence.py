"""Hypothesis 3: the old cross-ticker fix made two changes at once. Separate them with a 2x2 on all five tickers:
order size (fixed 200 shares vs adaptive to touch depth) x requote cadence (every 100 events vs every 6s).

Nothing is tuned: both levels of each factor are the historical settings. 100 events is about 6s on AAPL.

Rule fixed before running: for each ticker and fill preset, a factor's effect is the change in total P&L from
switching it to the new level, averaged over both levels of the other factor. The old diagnosis predicted size
was what mattered on INTC and MSFT (a fixed 200 shares never reached the front of their queues) and cadence on
GOOG (100 events is ~16s there). Supported if the size effect is larger than the cadence effect on INTC and MSFT,
and the cadence effect larger on GOOG, at both presets. Writes docs/size-cadence.md.

Usage: python -m experiments.size_cadence
"""

import gc
from dataclasses import dataclass, replace

import pandas as pd

from experiments.common import ROOT, Setup, backtest, load, quoter, save
from experiments.event_requote import PRESETS
from mm import data

KEEP = ("pnl_total_at_close", "pnl_spread_passive", "pnl_adverse_selection_passive", "pnl_crossing",
        "shares_passive", "shares_forced", "n_quotes_placed")


@dataclass(frozen=True)
class Config(Setup):
    fixed_order_size: int = 200
    fixed_inventory_limit: int = 1000
    every_events: int = 100


def runs(m, ticker: str, cfg: Config) -> list[dict]:
    rows = []
    hours = (m.time[-1] - m.time[0]) / 3600
    for size in ("fixed", "adaptive"):
        limits = ({} if size == "adaptive" else
                  dict(order_size=cfg.fixed_order_size, inventory_limit=cfg.fixed_inventory_limit))
        for cadence in ("events", "seconds"):
            every = cfg.every_events if cadence == "events" else None
            for name, model in PRESETS.items():
                run = replace(cfg, fill_model=model, requote_every_events=every)
                q = quoter(m, run, **limits)
                s = backtest(m, q, run)
                shares = max(1, s["shares_passive"])
                rows.append({"ticker": ticker, "size": size, "cadence": cadence, "fills": name,
                             "order_size": q.order_size, **{k: s.get(k) for k in KEEP},
                             "net_cents_per_passive_share":
                                 100 * (s["pnl_spread_passive"] + s["pnl_adverse_selection_passive"]) / shares,
                             "seconds_per_100_events": 100 * hours * 3600 / len(m)})
    return rows


def measure(cfg: Config) -> pd.DataFrame:
    rows = []
    for ticker in cfg.tickers:  # one ticker in memory at a time
        m = load(ticker, cfg)
        rows += runs(m, ticker, cfg)
        del m
        gc.collect()
    return pd.DataFrame(rows)


def effects(df: pd.DataFrame) -> pd.DataFrame:
    """Main effects and interaction on total P&L, per ticker and preset."""
    out = []
    for (ticker, fills), g in df.groupby(["ticker", "fills"], sort=False):
        p = g.set_index(["size", "cadence"]).pnl_total_at_close
        fe, fs, ae, as_ = p["fixed", "events"], p["fixed", "seconds"], p["adaptive", "events"], p["adaptive", "seconds"]
        out.append({"ticker": ticker, "fills": fills,
                    "size_effect": ((ae - fe) + (as_ - fs)) / 2,
                    "cadence_effect": ((fs - fe) + (as_ - ae)) / 2,
                    "interaction": ((as_ - ae) - (fs - fe)) / 2})
    return pd.DataFrame(out)


def markdown(df: pd.DataFrame, fx: pd.DataFrame, cfg: Config) -> str:
    money, cents = "{:,.0f}".format, "{:+.2f}".format
    pair = lambda g, col, fmt: " / ".join(fmt(g[g.fills == f][col].iloc[0]) for f in PRESETS)
    cols = [("pnl_total_at_close", "Total P&L", money), ("net_cents_per_passive_share", "Net ¢/share", cents),
            ("pnl_crossing", "Crossing cost", money), ("shares_passive", "Passive shares", money),
            ("n_quotes_placed", "Quotes sent", money)]
    head = "| | Order size | " + " | ".join(c[1] for c in cols) + " |\n" + "|---" * (len(cols) + 2) + "|"
    grid = []
    for (ticker, size, cadence), g in df.groupby(["ticker", "size", "cadence"], sort=False):
        every = f"{cfg.every_events} events" if cadence == "events" else f"{cfg.requote_seconds:g}s"
        grid.append(f"| {ticker}, {size} size, every {every} | {int(g.order_size.iloc[0])} | "
                    + " | ".join(pair(g, c, f) for c, _, f in cols) + " |")

    fx_rows = []
    for ticker, g in fx.groupby("ticker", sort=False):
        secs = df[df.ticker == ticker].seconds_per_100_events.iloc[0]
        fx_rows.append(f"| {ticker} | {secs:.1f}s | " + " | ".join(pair(g, c, money) for c in
                       ("size_effect", "cadence_effect", "interaction")) + " |")

    bigger = lambda t, f, a, b: (lambda r: abs(r[a]) > abs(r[b]))(fx[(fx.ticker == t) & (fx.fills == f)].iloc[0])
    checks = [("INTC", "size_effect", "cadence_effect"), ("MSFT", "size_effect", "cadence_effect"),
              ("GOOG", "cadence_effect", "size_effect")]
    verdict = [f"- {t}: {a.split('_')[0]} effect larger than {b.split('_')[0]}: "
               + " / ".join("yes" if bigger(t, f, a, b) else "no" for f in PRESETS) for t, a, b in checks]
    span = lambda size, cadence: pair(
        df[(df["size"] == size) & (df.cadence == cadence)].groupby("fills", sort=False)
        .pnl_total_at_close.agg(lambda s: s.max() - s.min()).reset_index(), "pnl_total_at_close", money)

    return f"""# Which change fixed the cross-ticker results: order size or requote cadence?

Every cell is **pessimistic / optimistic** fills. Dollars over one day (LOBSTER, 2012-06-21).
Regenerate with `python -m experiments.size_cadence`.

- **Fixed size:** {cfg.fixed_order_size} shares, inventory limit {cfg.fixed_inventory_limit:,}, on every ticker (the old setting).
- **Adaptive size:** 8% of the ticker's average touch depth, clipped to 20–500, limit 5x that.
- **Every {cfg.every_events} events** vs **every {cfg.requote_seconds:g}s** of market time.

## Effects on total P&L

Each effect is the P&L change from switching that factor to its new level (adaptive size, or time cadence), averaged over both settings of the other. **Interaction** is how much the cadence effect differs between the two sizes.

| | 100 events lasts | Size effect | Cadence effect | Interaction |
|---|---|---|---|---|
{chr(10).join(fx_rows)}

Predictions written before running, pessimistic / optimistic:

{chr(10).join(verdict)}

Spread of total P&L across the five tickers (best minus worst):

- Fixed size, every {cfg.every_events} events (the old setup): {span('fixed', 'events')}
- Adaptive size, every {cfg.requote_seconds:g}s (the current setup): {span('adaptive', 'seconds')}

## All four combinations

{head}
{chr(10).join(grid)}
"""


def main(cfg=Config()):
    df = measure(cfg)
    fx = effects(df)
    text = markdown(df, fx, cfg)
    with open(ROOT / "docs" / "size-cadence.md", "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(text)
    save("size_cadence", cfg, {"runs": df, "effects": fx})


if __name__ == "__main__":
    main()
