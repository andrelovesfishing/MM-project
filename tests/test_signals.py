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


def test_forward_change_looks_ahead():
    out = signals.forward_change(np.array([1.0, 4.0, 9.0]), 1)
    assert out[:2].tolist() == [3.0, 5.0] and np.isnan(out[2])
