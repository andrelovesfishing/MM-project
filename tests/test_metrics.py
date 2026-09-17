import numpy as np
import pytest

from mm.metrics import sharpe_annualized


def test_sharpe_uses_one_minute_bars_and_annualises_by_trading_minutes():
    time = np.arange(0.0, 601.0, 1.0)                        # ten minutes, sampled every second
    per_minute = np.cumsum([0] + [1.0, 3.0] * 5)             # P&L changes of 1, 3, 1, 3... per minute
    series = np.interp(time, np.arange(0.0, 601.0, 60.0), per_minute)
    assert sharpe_annualized(time, series) == pytest.approx(2.0 * np.sqrt(252 * 390))


def test_sharpe_is_nan_for_flat_pnl():
    assert np.isnan(sharpe_annualized(np.arange(0.0, 601.0), np.zeros(601)))
