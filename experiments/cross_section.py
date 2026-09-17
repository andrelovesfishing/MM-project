"""Run the AAPL-tuned strategy unchanged on all five tickers. Only size limits scale with each book's depth."""

import gc

import pandas as pd

from experiments.common import Setup, backtest, load, quoter, save
from mm import data


def main(cfg=Setup()):
    rows = []
    for ticker in cfg.tickers:  # one ticker in memory at a time
        m = load(ticker, cfg)
        profile = data.liquidity_profile(m)
        q = quoter(m, cfg)
        row = backtest(m, q, cfg)
        row.update(ticker=ticker, is_train=ticker == cfg.train_ticker,
                   **{f"profile_{k}": v for k, v in profile.items()},
                   used_latency_events=cfg.latency_events, used_order_size=q.order_size,
                   used_inventory_limit=q.inventory_limit, used_requote_every_seconds=cfg.requote_seconds)
        rows.append(row)
        print(f"{ticker}: realized {row['final_pnl_realized']:.2f}, fills {row['n_fills']}")
        del m
        gc.collect()
    save("cross_section", cfg, {"cross_section": pd.DataFrame(rows)})


if __name__ == "__main__":
    main()
