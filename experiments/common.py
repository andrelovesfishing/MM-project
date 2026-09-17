"""Shared setup for experiments: one config dataclass, results saved next to the config that made them."""

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import pandas as pd

from mm import data, engine, metrics
from mm.queue import FillModel
from mm.strategy import ASQuoter, adaptive_limits

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Setup:
    tickers: tuple = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT")
    train_ticker: str = "AAPL"   # all tuning happens here; the rest are out-of-sample
    data_dir: str = str(ROOT / "data")
    gamma: float = 0.1
    kappa: float = 3.2
    requote_seconds: float = 6.0
    requote_move_ticks: float | None = None  # also requote when the micro-price moves this far (engine.OnMove)
    latency_events: int = 2
    fill_model: FillModel = FillModel()


def load(ticker: str, setup: Setup) -> data.Market:
    return data.load(ticker, setup.data_dir)


def quoter(market: data.Market, setup: Setup, **overrides) -> ASQuoter:
    limits = adaptive_limits(data.liquidity_profile(market))
    return replace(ASQuoter(gamma=setup.gamma, kappa=setup.kappa, **limits), **overrides)


def backtest(market: data.Market, strategy, setup: Setup) -> dict:
    requote = (engine.Timer(setup.requote_seconds) if setup.requote_move_ticks is None
               else engine.OnMove(setup.requote_move_ticks, setup.requote_seconds))
    result = engine.run(market, strategy, requote, setup.latency_events, fill_model=setup.fill_model)
    return metrics.summary(result, market)


def save(name: str, setup, tables: dict[str, pd.DataFrame]) -> Path:
    out = ROOT / "results" / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.json").write_text(json.dumps(asdict(setup), indent=2))
    for table, df in tables.items():
        df.to_csv(out / f"{table}.csv", index=False)
    print(f"saved {', '.join(tables)} to {out}")
    return out
