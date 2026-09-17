import numpy as np

from mm import signals


def test_ofi_matches_hand_calculation():
    bid_px = np.array([10000, 10000, 9990, 10000, 10000])
    bid_sz = np.array([10, 15, 15, 5, 5])
    ask_px = np.array([10010, 10010, 10010, 10020, 10020])
    ask_sz = np.array([8, 8, 20, 20, 12])
    # bid grows 5; bid drops a level (-15) and ask grows 12; bid improves (+5) and ask backs off (+20); ask shrinks 8
    assert signals.ofi(bid_px, bid_sz, ask_px, ask_sz)[1:].tolist() == [5, -27, 25, 8]


def test_rolling_sum_is_nan_until_window_full():
    out = signals.rolling_sum(np.array([1, 2, 3, 4]), 3)
    assert np.isnan(out[:2]).all() and out[2:].tolist() == [6, 9]


def test_newey_west_t_stat_holds_its_size_where_naive_t_does_not():
    # No true relationship, but both series are 50-event overlapping changes, like rolling OFI vs forward mid
    rng = np.random.default_rng(0)
    naive = nw = 0
    for _ in range(200):
        a, b = np.cumsum(rng.standard_normal((2, 2000)), axis=1)
        signal = np.roll(signals.forward_change(a, 50), 50)  # past 50-event change
        fwd = signals.forward_change(b, 50)
        signal[:50] = np.nan
        ok = ~np.isnan(signal) & ~np.isnan(fwd)
        ic, t_nw = signals.spearman_ic_newey_west(signal[ok], fwd[ok], lags=100)
        naive += abs(ic * np.sqrt(ok.sum())) > 1.96
        nw += abs(t_nw) > 1.96
    assert naive / 200 > 0.5 and nw / 200 < 0.15


def test_newey_west_with_no_lags_matches_iid_t_stat():
    rng = np.random.default_rng(1)
    x = rng.standard_normal(5000)
    y = 0.1 * x + rng.standard_normal(5000)
    ic, t = signals.spearman_ic_newey_west(x, y, lags=0)
    assert abs(t / (ic * np.sqrt(5000)) - 1) < 0.05


def test_forward_change_looks_ahead():
    out = signals.forward_change(np.array([1.0, 4.0, 9.0]), 1)
    assert out[:2].tolist() == [3.0, 5.0] and np.isnan(out[2])
