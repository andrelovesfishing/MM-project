"""Does rolling OFI predict the mid-price, and over what horizon? (AAPL, train ticker)"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from experiments.common import Setup, load, save
from mm import signals
from mm.data import EXECUTE, EXECUTE_HIDDEN, TICK


@dataclass(frozen=True)
class Config(Setup):
    ofi_window: int = 50
    horizons: tuple = (10, 50, 200, 500, 1000)
    decile_horizon: int = 50


def main(cfg=Config()):
    m = load(cfg.train_ticker, cfg)
    roll = signals.rolling_sum(m.ofi, cfg.ofi_window)
    ic = signals.ic_table(roll, m.mid, cfg.horizons)
    print(ic.to_string(index=False))

    trades = np.isin(m.event_type, (EXECUTE, EXECUTE_HIDDEN))
    fit = signals.trade_distance_kappa(m.price[trades], m.mid[trades], TICK)
    print(f"[diagnostic only, not used] A={fit['A']:.2f}, kappa={fit['kappa']:.4f}, R^2={fit['r2']:.3f}")

    save("signal_research", cfg, {
        "ic": ic,
        "deciles": signals.deciles(roll, m.mid, cfg.decile_horizon),
        "trade_distance_fit": pd.DataFrame([fit]),
    })


if __name__ == "__main__":
    main()
