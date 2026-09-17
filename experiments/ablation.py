"""Add one quoting component at a time on AAPL, so each row's change is down to that component."""

import pandas as pd

from experiments.common import Setup, backtest, load, quoter, save

STEPS = [
    ("baseline (touch-join + hard flatten only)", dict(inventory_skew=None, size_skew=None, ofi_guard=None)),
    ("+ inventory skew", dict(size_skew=None, ofi_guard=None)),
    ("+ size skew", dict(ofi_guard=None)),
    ("+ OFI adverse-selection widen (full model)", dict()),
]


def main(cfg=Setup()):
    m = load(cfg.train_ticker, cfg)
    rows = [{**backtest(m, quoter(m, cfg, **components), cfg), "config": label}
            for label, components in STEPS]
    df = pd.DataFrame(rows)
    print(df[["config", "final_pnl_realized", "fill_rate", "inventory_std",
              "n_forced_flatten_crosses", "frac_quotes_touch_snapped"]].to_string(index=False))
    save("ablation", cfg, {"ablation": df})


if __name__ == "__main__":
    main()
