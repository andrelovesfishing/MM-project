"""One-parameter sweeps on AAPL: gamma, kappa, and how far behind the touch we may rest."""

from dataclasses import dataclass

import pandas as pd

from experiments.common import Setup, backtest, load, quoter, save


@dataclass(frozen=True)
class Config(Setup):
    gammas: tuple = (0.01, 0.05, 0.1, 0.3, 0.5, 1.0)
    kappas: tuple = (0.1, 0.32, 1.0, 3.2, 10.0, 30.0)
    touch_joins: tuple = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
    touch_join_kappa: float = 0.32  # the fitted kappa, so the natural spread can sit behind the touch


def sweep(m, cfg, param, values, **fixed):
    return pd.DataFrame([{**backtest(m, quoter(m, cfg, **fixed, **{param: v}), cfg), param: v}
                         for v in values])


def main(cfg=Config()):
    m = load(cfg.train_ticker, cfg)
    tables = {
        "gamma": sweep(m, cfg, "gamma", cfg.gammas),
        "kappa": sweep(m, cfg, "kappa", cfg.kappas),
        "touch_join": sweep(m, cfg, "touch_join_ticks", cfg.touch_joins, kappa=cfg.touch_join_kappa),
    }
    for name, df in tables.items():
        print(df[[df.columns[-1], "final_pnl_realized", "fill_rate", "frac_quotes_touch_snapped"]]
              .to_string(index=False))
    save("sweeps", cfg, tables)


if __name__ == "__main__":
    main()
