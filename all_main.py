"""
Sections 1-4 (load_lobster_data, compute_ofi/_side_ofi/_validate_ofi, rolling_sum,
forward_return, compute_ic_table, decile_analysis, plot_decile_staircase,
plot_ic_decay) are UNCHANGED from your last version. Paste them above this file,
or import them, before running __main__ below. They are omitted here for brevity
since nothing about them needed to change.
"""

import numpy as np
import pandas as pd
import polars as pl
import matplotlib.pyplot as plt
from scipy import stats
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 1. DATA LOADING
# ---------------------------------------------------------------------------
def load_lobster_data(msg_path: str, ob_path: str, num_levels: int = 10):
    """
    Parses LOBSTER message and orderbook CSV files into clean, vectorized NumPy structures.
    """
    print("Parsing LOBSTER files with Polars...")

    msg_cols = ["time", "event_type", "order_id", "size", "price", "direction"]
    df_msg = pl.read_csv(
        msg_path,
        has_header=False,
        new_columns=msg_cols,
        schema={
            "time": pl.Float64,
            "event_type": pl.Int32,
            "order_id": pl.Int64,
            "size": pl.Int64,
            "price": pl.Float64,
            "direction": pl.Int32
        }
    )

    ob_cols = []
    for i in range(1, num_levels + 1):
        ob_cols.extend([f"ask_price_{i}", f"ask_size_{i}", f"bid_price_{i}", f"bid_size_{i}"])

    df_ob = pl.read_csv(ob_path, has_header=False, new_columns=ob_cols)

    df_msg = df_msg.with_columns(pl.col("price") / 10000.0)
    price_cols = [c for c in ob_cols if "price" in c]
    df_ob = df_ob.with_columns([pl.col(c) / 10000.0 for c in price_cols])

    assert len(df_msg) == len(df_ob), "Message and orderbook files misaligned — check download integrity"

    ask_p1 = df_ob["ask_price_1"].to_numpy()
    ask_v1 = df_ob["ask_size_1"].to_numpy()
    bid_p1 = df_ob["bid_price_1"].to_numpy()
    bid_v1 = df_ob["bid_size_1"].to_numpy()

    mid_price = (ask_p1 + bid_p1) / 2.0
    spread = ask_p1 - bid_p1

    total_top_vol = ask_v1 + bid_v1
    micro_price = np.where(
        total_top_vol > 0,
        (bid_v1 * ask_p1 + ask_v1 * bid_p1) / total_top_vol,
        mid_price
    )

    ofi = compute_ofi(bid_p1, bid_v1, ask_p1, ask_v1)

    print(f"Successfully loaded {len(df_msg):,} events!")

    return {
        "messages": df_msg.to_pandas(),
        "orderbook": df_ob.to_pandas(),
        "mid_price": mid_price,
        "micro_price": micro_price,
        "spread": spread,
        "ofi": ofi,
    }


# ---------------------------------------------------------------------------
# 2. ORDER FLOW IMBALANCE (unchanged — this part of your code was already correct)
# ---------------------------------------------------------------------------
def _side_ofi(price: np.ndarray, size: np.ndarray, better_when: str) -> np.ndarray:
    price_diff = np.diff(price, prepend=price[0])
    size_diff = np.diff(size, prepend=size[0])
    prev_size = np.concatenate(([size[0]], size[:-1]))

    improved = price_diff > 0 if better_when == "up" else price_diff < 0
    same = price_diff == 0

    return np.where(improved, size, np.where(same, size_diff, -prev_size))


def compute_ofi(bid_p: np.ndarray, bid_v: np.ndarray, ask_p: np.ndarray, ask_v: np.ndarray) -> np.ndarray:
    bid_e = _side_ofi(bid_p, bid_v, better_when="up")
    ask_e = _side_ofi(ask_p, ask_v, better_when="down")
    return bid_e - ask_e


def _validate_ofi():
    bid_p = np.array([100.0, 100.0, 99.9, 100.0, 100.0])
    bid_v = np.array([10, 15, 15, 5, 5])
    ask_p = np.array([100.1, 100.1, 100.1, 100.2, 100.2])
    ask_v = np.array([8, 8, 20, 20, 12])

    ofi = compute_ofi(bid_p, bid_v, ask_p, ask_v)
    expected = np.array([0, 5, -27, 25, 8])

    print("OFI validation array:", ofi)
    assert np.allclose(ofi[1:], expected[1:]), f"OFI mismatch: {ofi} vs {expected}"
    print("OFI unit test passed.\n")


# ---------------------------------------------------------------------------
# 3. SIGNAL RESEARCH (unchanged from your version — IC ~0.21 at 50 events was solid)
# ---------------------------------------------------------------------------
def rolling_sum(arr: np.ndarray, window: int) -> np.ndarray:
    cs = np.cumsum(np.insert(arr, 0, 0))
    out = np.full(len(arr), np.nan)
    out[window - 1:] = cs[window:] - cs[:-window]
    return out


def forward_return(price: np.ndarray, horizon: int) -> np.ndarray:
    fwd = np.full(len(price), np.nan)
    fwd[:-horizon] = price[horizon:] - price[:-horizon]
    return fwd


def compute_ic_table(data: dict, ofi_window: int = 50, horizons=(10, 50, 200, 500)) -> pd.DataFrame:
    roll_ofi = rolling_sum(data["ofi"], ofi_window)
    mid = data["mid_price"]

    rows = []
    for h in horizons:
        fwd_ret = forward_return(mid, h)
        valid = ~np.isnan(roll_ofi) & ~np.isnan(fwd_ret)
        x = roll_ofi[valid]
        y = fwd_ret[valid]

        ic, pval = stats.spearmanr(x, y)
        n = len(x)
        t_stat = ic * np.sqrt((n - 2) / (1 - ic**2))

        rows.append({
            "horizon_events": h,
            "n_obs": n,
            "spearman_IC": ic,
            "t_stat": t_stat,
            "p_value": pval,
        })

    return pd.DataFrame(rows)


def decile_analysis(data: dict, ofi_window: int = 50, horizon: int = 50) -> pd.DataFrame:
    roll_ofi = rolling_sum(data["ofi"], ofi_window)
    fwd_ret = forward_return(data["mid_price"], horizon)

    valid = ~np.isnan(roll_ofi) & ~np.isnan(fwd_ret)
    df = pd.DataFrame({"roll_ofi": roll_ofi[valid], "fwd_ret": fwd_ret[valid]})
    df["decile"] = pd.qcut(df["roll_ofi"], 10, labels=False, duplicates="drop")

    summary = df.groupby("decile").agg(
        mean_ofi=("roll_ofi", "mean"),
        mean_fwd_ret=("fwd_ret", "mean"),
        n=("fwd_ret", "count"),
    ).reset_index()

    return summary


def plot_decile_staircase(summary: pd.DataFrame, horizon: int, save_path: str = "decile_staircase.png"):
    plt.figure(figsize=(8, 5))
    plt.bar(summary["decile"], summary["mean_fwd_ret"], color="steelblue")
    plt.axhline(0, color="black", linewidth=0.8)
    plt.xlabel("Rolling OFI Decile (0 = most negative, 9 = most positive)")
    plt.ylabel(f"Mean Forward Mid-Price Return ({horizon} events ahead)")
    plt.title("OFI Decile vs. Forward Return — Monotonicity Check")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    print(f"Saved decile staircase plot to {save_path}")


def plot_ic_decay(ic_table: pd.DataFrame, save_path: str = "ic_decay.png"):
    plt.figure(figsize=(8, 5))
    plt.plot(ic_table["horizon_events"], ic_table["spearman_IC"], marker="o", color="darkred")
    plt.axhline(0, color="black", linewidth=0.8)
    plt.xlabel("Forward Horizon (events)")
    plt.ylabel("Spearman IC (rolling OFI vs. forward return)")
    plt.title("Signal Decay: IC vs. Prediction Horizon")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    print(f"Saved IC decay plot to {save_path}")


# The five tickers LOBSTER provides for free, all on the same session (2012-06-21).
# AAPL is your TRAIN ticker (all prior tuning happened here). The other four are
# genuine out-of-sample cross-sectional tests: same parameters, zero retuning.
ALL_TICKERS = ["AAPL", "AMZN", "GOOG", "INTC", "MSFT"]
TRAIN_TICKER = "AAPL"


def load_ticker(ticker: str, data_dir: str = "data", num_levels: int = 10) -> dict:
    """Thin wrapper around load_lobster_data using LOBSTER's standard free-sample naming."""
    msg_path = f"{data_dir}/{ticker}_2012-06-21_34200000_57600000_message_10.csv"
    ob_path = f"{data_dir}/{ticker}_2012-06-21_34200000_57600000_orderbook_10.csv"
    return load_lobster_data(msg_path, ob_path, num_levels=num_levels)


# ---------------------------------------------------------------------------
# 5. ARRIVAL INTENSITY CALIBRATION
# (unchanged logic, still diagnostic-only — see honesty note in docstring)
# ---------------------------------------------------------------------------
def calibrate_arrival_intensity(data: dict, n_buckets: int = 15, max_ticks: int = 20, tick_size: float = 0.01):
    """
    DIAGNOSTIC ONLY, not fed into the live quoting loop. This fits lambda(delta) from
    the distribution of *executed trade* distances from mid, not true queue-reactive
    arrival/cancellation rates at each price level -- it measures "how far from mid do
    fills happen", which concentrates mass near the touch and produces a kappa that
    implies spreads wider than the market's real ~1-tick spread. kappa_fixed=3.2 is
    used instead in ASParams as an order-of-magnitude match to the observed market
    spread. State this explicitly in any writeup -- do not imply the printed A/kappa
    below were used in the backtest.
    """
    msg = data["messages"]
    mid = data["mid_price"]

    exec_mask = msg["event_type"].isin([4, 5]).to_numpy()
    exec_prices = msg["price"].to_numpy()[exec_mask]
    exec_mid = mid[exec_mask]

    distance_ticks = np.abs(exec_prices - exec_mid) / tick_size
    distance_ticks = distance_ticks[distance_ticks <= max_ticks]

    bucket_edges = np.linspace(0, max_ticks, n_buckets + 1)
    counts, edges = np.histogram(distance_ticks, bins=bucket_edges)
    bucket_centers = (edges[:-1] + edges[1:]) / 2

    valid = counts > 0
    log_counts = np.log(counts[valid])
    x = bucket_centers[valid]

    slope, intercept, r_value, p_value, std_err = stats.linregress(x, log_counts)
    kappa = -slope
    A = np.exp(intercept)

    print(f"  [diagnostic only, not used] calibrated A={A:.2f}, kappa={kappa:.4f}, R^2={r_value**2:.3f}")
    return A, kappa


# ---------------------------------------------------------------------------
# 6. AVELLANEDA-STOIKOV QUOTING LOGIC
# ---------------------------------------------------------------------------
@dataclass
class ASParams:
    gamma: float = 0.1
    kappa: float = 3.2                 # hand-set, see calibrate_arrival_intensity docstring
    T: float = 23400.0
    ofi_z_threshold: float = 2.0

    use_ofi_signal: bool = True        # toggle for ablation
    use_inventory_skew: bool = True    # toggle for ablation
    use_size_skew: bool = True         # toggle for ablation

    max_half_spread_ticks: float = 3.0
    min_half_spread_ticks: float = 0.5
    touch_join_ticks: float = 1.0

    aggressive_inventory_frac: float = 0.5   # fraction of inventory_limit -> hard flatten threshold
    inventory_skew_ticks_per_100_per_gamma: float = 1.0
    max_inventory_skew_ticks: float = 3.0

    min_size_frac_at_flatten: float = 0.2
    protective_widen_ticks: float = 4.0


def compute_optimal_half_spread(gamma: float, sigma: float, time_remaining: float, kappa: float) -> float:
    inventory_term = gamma * (sigma ** 2) * time_remaining
    spread_term = (2.0 / gamma) * np.log(1.0 + gamma / kappa)
    return (inventory_term + spread_term) / 2.0


def rolling_volatility(mid_price: np.ndarray, window: int = 500) -> np.ndarray:
    log_ret = np.diff(np.log(mid_price), prepend=np.log(mid_price[0]))
    sq = log_ret ** 2
    roll = rolling_sum(sq, window) / window
    roll = np.where(np.isnan(roll), np.nanmean(roll), roll)
    return np.sqrt(roll)


def rolling_zscore(arr: np.ndarray, window: int = 200) -> np.ndarray:
    s = pd.Series(arr)
    mean = s.rolling(window, min_periods=window // 4).mean()
    std = s.rolling(window, min_periods=window // 4).std()
    z = (s - mean) / std.replace(0, np.nan)
    return z.fillna(0.0).to_numpy()


# ---------------------------------------------------------------------------
# 7. FIFO QUEUE-AWARE FILL SIMULATOR
# ---------------------------------------------------------------------------
@dataclass
class RestingOrder:
    price: float
    size: int
    ahead_volume: float
    is_forced: bool = False


@dataclass
class SimState:
    inventory: int = 0
    cash: float = 0.0
    avg_cost: float = 0.0
    realized_pnl: float = 0.0
    pnl_history: list = field(default_factory=list)
    realized_pnl_history: list = field(default_factory=list)
    unrealized_pnl_history: list = field(default_factory=list)
    inventory_history: list = field(default_factory=list)
    time_history: list = field(default_factory=list)
    fill_log: list = field(default_factory=list)  # (time, side, price, size, event_idx, is_forced)
    n_quotes_placed: int = 0
    n_fills: int = 0
    n_requotes_same_price: int = 0
    n_requotes_new_price: int = 0
    quote_touch_distance_ticks: list = field(default_factory=list)
    n_forced_flatten_crosses: int = 0
    forced_flatten_z_values: list = field(default_factory=list)
    # NEW: transparency counters -- how much of the "AS model" survives the touch-join snap
    n_quotes_touch_snapped: int = 0
    n_quotes_organic: int = 0


def update_avg_cost_and_realized(state: SimState, prev_inventory: int, signed_fill: int, price: float):
    if prev_inventory == 0 or np.sign(prev_inventory) == np.sign(signed_fill):
        total_size = abs(prev_inventory) + abs(signed_fill)
        state.avg_cost = (
            (state.avg_cost * abs(prev_inventory) + price * abs(signed_fill)) / total_size
            if total_size > 0 else price
        )
    else:
        closing_size = min(abs(signed_fill), abs(prev_inventory))
        direction = np.sign(prev_inventory)
        state.realized_pnl += closing_size * (price - state.avg_cost) * direction
        remaining = abs(signed_fill) - closing_size
        if remaining > 0:
            state.avg_cost = price
    state.inventory = prev_inventory + signed_fill


def lookup_displayed_size(orderbook_row, price: float, side: str, num_levels: int = 10) -> float:
    prefix = "bid" if side == "bid" else "ask"
    worst_visible_price = None
    for lvl in range(1, num_levels + 1):
        lvl_price = orderbook_row[f"{prefix}_price_{lvl}"]
        lvl_size = orderbook_row[f"{prefix}_size_{lvl}"]
        if abs(price - lvl_price) < 1e-9:
            return lvl_size
        worst_visible_price = lvl_price
    if (side == "bid" and price < worst_visible_price) or (side == "ask" and price > worst_visible_price):
        return orderbook_row[f"{prefix}_size_{num_levels}"]
    return 0.0


def run_backtest(
    data: dict,
    params: ASParams,
    order_size: int = 200,
    requote_every_n_events: int = 100,
    latency_events: int = 2,
    inventory_limit: int = 1000,
    ofi_window: int = 50,
    tick_size: float = 0.01,
):
    msg = data["messages"]
    mid = data["mid_price"]
    n = len(mid)

    sigma_series = rolling_volatility(mid, window=500)
    ofi_roll = rolling_sum(data["ofi"], ofi_window)
    ofi_z = rolling_zscore(ofi_roll, window=200)

    session_start = msg["time"].iloc[0]
    session_end = msg["time"].iloc[-1]
    total_T = session_end - session_start

    event_type = msg["event_type"].to_numpy()
    direction = msg["direction"].to_numpy()
    ev_price = msg["price"].to_numpy()
    ev_size = msg["size"].to_numpy()
    ev_time = msg["time"].to_numpy()

    micro_price = data["micro_price"]
    best_bid_arr = data["orderbook"]["bid_price_1"].to_numpy()
    best_ask_arr = data["orderbook"]["ask_price_1"].to_numpy()

    state = SimState()
    our_bid: RestingOrder | None = None
    our_ask: RestingOrder | None = None
    pending_quotes = None
    pending_quote_event = -1

    flatten_threshold = max(params.aggressive_inventory_frac * inventory_limit, 2 * order_size)

    for i in range(n):
        t_remaining = max(session_end - ev_time[i], 1.0)

        # --- 0. Cancel handling ---
        if event_type[i] == 2:
            px, sz, d = ev_price[i], ev_size[i], direction[i]
            if our_bid is not None and abs(our_bid.price - px) < 1e-9 and d == 1:
                our_bid.ahead_volume -= sz
            if our_ask is not None and abs(our_ask.price - px) < 1e-9 and d == -1:
                our_ask.ahead_volume -= sz

        # --- 1. Fill checks ---
        if event_type[i] in (4, 5):
            px, sz, d = ev_price[i], ev_size[i], direction[i]

            if our_bid is not None and d == -1 and px <= our_bid.price + 1e-9:
                our_bid.ahead_volume -= sz
                if our_bid.ahead_volume <= 0:
                    fill_size = max(min(our_bid.size, sz - max(int(our_bid.ahead_volume), -sz + our_bid.size)), 1)
                    prev_inv = state.inventory
                    update_avg_cost_and_realized(state, prev_inv, fill_size, our_bid.price)
                    state.cash -= fill_size * our_bid.price
                    state.n_fills += 1
                    state.fill_log.append((ev_time[i], "BUY", our_bid.price, fill_size, i, our_bid.is_forced))
                    our_bid.size -= fill_size
                    if our_bid.size <= 0:
                        our_bid = None

            if our_ask is not None and d == 1 and px >= our_ask.price - 1e-9:
                our_ask.ahead_volume -= sz
                if our_ask.ahead_volume <= 0:
                    fill_size = max(min(our_ask.size, sz - max(int(our_ask.ahead_volume), -sz + our_ask.size)), 1)
                    prev_inv = state.inventory
                    update_avg_cost_and_realized(state, prev_inv, -fill_size, our_ask.price)
                    state.cash += fill_size * our_ask.price
                    state.n_fills += 1
                    state.fill_log.append((ev_time[i], "SELL", our_ask.price, fill_size, i, our_ask.is_forced))
                    our_ask.size -= fill_size
                    if our_ask.size <= 0:
                        our_ask = None

        # --- 1b. Enforce inventory limits (on RESTING orders too, not just new quotes) ---
        if state.inventory >= inventory_limit and our_bid is not None:
            our_bid = None
        if state.inventory <= -inventory_limit and our_ask is not None:
            our_ask = None

        # --- 2. Recompute desired quotes periodically ---
        if i % requote_every_n_events == 0:
            sigma = sigma_series[i]
            z = ofi_z[i]
            best_bid, best_ask = best_bid_arr[i], best_ask_arr[i]

            r = micro_price[i]
            as_half_spread = compute_optimal_half_spread(params.gamma, sigma, t_remaining / total_T * params.T, params.kappa)
            half_spread = np.clip(as_half_spread, params.min_half_spread_ticks * tick_size, params.max_half_spread_ticks * tick_size)

            if params.use_inventory_skew:
                raw_skew = params.gamma * params.inventory_skew_ticks_per_100_per_gamma * (state.inventory / 100.0)
                inventory_skew = np.clip(raw_skew, -params.max_inventory_skew_ticks, params.max_inventory_skew_ticks) * tick_size
                r -= inventory_skew

            protect_ask = params.use_ofi_signal and z > params.ofi_z_threshold
            protect_bid = params.use_ofi_signal and z < -params.ofi_z_threshold
            bid_half_spread = max(half_spread, params.protective_widen_ticks * tick_size) if protect_bid else half_spread
            ask_half_spread = max(half_spread, params.protective_widen_ticks * tick_size) if protect_ask else half_spread

            if params.use_size_skew:
                imbalance_frac = min(1.0, abs(state.inventory) / max(1.0, flatten_threshold))
                shrunk_size = max(1, int(order_size * (1.0 - imbalance_frac * (1.0 - params.min_size_frac_at_flatten))))
                if state.inventory > 0:
                    bid_size, ask_size = shrunk_size, order_size
                elif state.inventory < 0:
                    bid_size, ask_size = order_size, shrunk_size
                else:
                    bid_size, ask_size = order_size, order_size
            else:
                bid_size, ask_size = order_size, order_size

            can_buy = state.inventory < inventory_limit
            can_sell = state.inventory > -inventory_limit

            new_bid_px = round((r - bid_half_spread) / tick_size) * tick_size if can_buy else None
            new_ask_px = round((r + ask_half_spread) / tick_size) * tick_size if can_sell else None

            if new_bid_px is not None and new_bid_px >= best_ask:
                new_bid_px = round((best_ask - tick_size) / tick_size) * tick_size
            if new_ask_px is not None and new_ask_px <= best_bid:
                new_ask_px = round((best_bid + tick_size) / tick_size) * tick_size

            if new_bid_px is not None:
                new_bid_px = min(new_bid_px, best_bid)
            if new_ask_px is not None:
                new_ask_px = max(new_ask_px, best_ask)

            # NEW: track how often the touch-join rule OVERRIDES the organic AS price,
            # i.e. how much of "Avellaneda-Stoikov" survives contact with the market.
            if new_bid_px is not None and not protect_bid:
                was_behind = (best_bid - new_bid_px) > params.touch_join_ticks * tick_size
                if was_behind:
                    new_bid_px = best_bid
                    state.n_quotes_touch_snapped += 1
                else:
                    state.n_quotes_organic += 1
            if new_ask_px is not None and not protect_ask:
                was_behind = (new_ask_px - best_ask) > params.touch_join_ticks * tick_size
                if was_behind:
                    new_ask_px = best_ask
                    state.n_quotes_touch_snapped += 1
                else:
                    state.n_quotes_organic += 1

            if new_bid_px is not None:
                state.quote_touch_distance_ticks.append((best_bid - new_bid_px) / tick_size)
            if new_ask_px is not None:
                state.quote_touch_distance_ticks.append((new_ask_px - best_ask) / tick_size)

            forced_bid = False
            forced_ask = False
            if state.inventory < -flatten_threshold and can_buy:
                new_bid_px = best_ask
                new_ask_px = None
                bid_size = order_size
                forced_bid = True
                state.n_forced_flatten_crosses += 1
                state.forced_flatten_z_values.append(z)
            if state.inventory > flatten_threshold and can_sell:
                new_ask_px = best_bid
                new_bid_px = None
                ask_size = order_size
                forced_ask = True
                state.n_forced_flatten_crosses += 1
                state.forced_flatten_z_values.append(z)

            pending_quotes = (new_bid_px, new_ask_px, bid_size, ask_size, forced_bid, forced_ask)
            pending_quote_event = i + latency_events
            state.n_quotes_placed += 1

        # --- 3. Apply pending quotes ---
        if pending_quotes is not None and i >= pending_quote_event:
            new_bid_px, new_ask_px, bid_sz, ask_sz, forced_bid, forced_ask = pending_quotes

            if new_bid_px is not None:
                if our_bid is not None and abs(our_bid.price - new_bid_px) < 1e-9:
                    state.n_requotes_same_price += 1
                else:
                    state.n_requotes_new_price += 1
                    displayed = lookup_displayed_size(data["orderbook"].iloc[i], new_bid_px, "bid")
                    our_bid = RestingOrder(price=new_bid_px, size=bid_sz, ahead_volume=displayed, is_forced=forced_bid)

            if new_ask_px is not None:
                if not (our_ask is not None and abs(our_ask.price - new_ask_px) < 1e-9):
                    displayed = lookup_displayed_size(data["orderbook"].iloc[i], new_ask_px, "ask")
                    our_ask = RestingOrder(price=new_ask_px, size=ask_sz, ahead_volume=displayed, is_forced=forced_ask)

            pending_quotes = None

        if i % 50 == 0:
            mtm_pnl = state.cash + state.inventory * mid[i]
            unrealized = state.inventory * (mid[i] - state.avg_cost) if state.inventory != 0 else 0.0
            state.pnl_history.append(mtm_pnl)
            state.realized_pnl_history.append(state.realized_pnl)
            state.unrealized_pnl_history.append(unrealized)
            state.inventory_history.append(state.inventory)
            state.time_history.append(ev_time[i])

    return state


# ---------------------------------------------------------------------------
# 8. MARKOUT & CROSSING-COST ANALYSIS
# ---------------------------------------------------------------------------
def compute_markouts(state: SimState, mid_price: np.ndarray, horizons=(100, 500, 1000)) -> pd.DataFrame:
    rows = []
    n = len(mid_price)
    for (t, side, price, size, idx, is_forced) in state.fill_log:
        row = {"time": t, "side": side, "price": price, "size": size, "is_forced": is_forced}
        for h in horizons:
            j = idx + h
            if j < n:
                fut_mid = mid_price[j]
                row[f"markout_{h}"] = (fut_mid - price) if side == "BUY" else (price - fut_mid)
        rows.append(row)
    return pd.DataFrame(rows)


def compute_crossing_cost(state: SimState, mid_price: np.ndarray) -> dict:
    """
    FIX from previous version: report both TOTAL and PER-FILL crossing cost. The total
    alone is misleading -- it can rise even as the number of forced crosses falls, simply
    because average size-per-cross changed. Per-fill cost isolates "how expensive is each
    emergency flatten" from "how often do we need one" -- these are different levers
    (size-skew addresses frequency; per-fill cost is closer to a fixed function of spread).
    """
    total_cost = 0.0
    n_forced = 0
    for (t, side, price, size, idx, is_forced) in state.fill_log:
        if not is_forced:
            continue
        m = mid_price[idx]
        cost_per_share = (price - m) if side == "BUY" else (m - price)
        total_cost += cost_per_share * size
        n_forced += 1
    return {
        "total_crossing_cost": total_cost,
        "mean_crossing_cost_per_forced_fill": total_cost / n_forced if n_forced > 0 else np.nan,
        "n_forced_fills_for_crossing_cost": n_forced,
    }


# ---------------------------------------------------------------------------
# 9. PERFORMANCE METRICS
# ---------------------------------------------------------------------------
def compute_backtest_metrics(state: SimState, mid_price: np.ndarray = None, markout_horizons=(100, 500, 1000)) -> dict:
    pnl = np.array(state.pnl_history)
    realized = np.array(state.realized_pnl_history)
    inv = np.array(state.inventory_history)

    pnl_changes = np.diff(pnl, prepend=pnl[0])
    sharpe_total_raw = np.mean(pnl_changes) / (np.std(pnl_changes) + 1e-9)
    sharpe_total_annualized = sharpe_total_raw * np.sqrt(252 * 6.5 * 3600 / max(1, len(pnl)))

    realized_changes = np.diff(realized, prepend=realized[0])
    sharpe_realized_raw = np.mean(realized_changes) / (np.std(realized_changes) + 1e-9)
    sharpe_realized_annualized = sharpe_realized_raw * np.sqrt(252 * 6.5 * 3600 / max(1, len(realized)))

    max_drawdown = np.max(np.maximum.accumulate(pnl) - pnl)

    total_touch_tracked = state.n_quotes_touch_snapped + state.n_quotes_organic
    frac_touch_snapped = state.n_quotes_touch_snapped / total_touch_tracked if total_touch_tracked > 0 else np.nan

    metrics = {
        "final_pnl_total": pnl[-1],
        "final_pnl_realized": realized[-1],
        "final_pnl_unrealized": pnl[-1] - realized[-1],
        "sharpe_total_raw_per_sample": sharpe_total_raw,
        "sharpe_total_annualized_approx": sharpe_total_annualized,
        "sharpe_realized_raw_per_sample": sharpe_realized_raw,
        "sharpe_realized_annualized_approx": sharpe_realized_annualized,
        "max_drawdown": max_drawdown,
        "max_abs_inventory": np.max(np.abs(inv)),
        "inventory_std": np.std(inv),
        "n_fills": state.n_fills,
        "n_quotes_placed": state.n_quotes_placed,
        "fill_rate": state.n_fills / max(1, state.n_quotes_placed),
        "mean_quote_distance_from_touch_ticks": (
            np.mean(state.quote_touch_distance_ticks) if state.quote_touch_distance_ticks else np.nan
        ),
        # NEW: honesty metric -- what fraction of quotes were snapped to the touch rather
        # than genuinely determined by the AS reservation-price/spread formula.
        "frac_quotes_touch_snapped": frac_touch_snapped,
        "n_forced_flatten_crosses": state.n_forced_flatten_crosses,
        "mean_ofi_z_at_forced_flatten": (
            np.mean(state.forced_flatten_z_values) if state.forced_flatten_z_values else np.nan
        ),
    }

    if mid_price is not None and len(state.fill_log) > 0:
        markout_df = compute_markouts(state, mid_price, markout_horizons)
        for h in markout_horizons:
            col = f"markout_{h}"
            if col in markout_df.columns:
                metrics[f"mean_{col}"] = markout_df[col].mean()
                passive = markout_df[~markout_df["is_forced"]]
                forced = markout_df[markout_df["is_forced"]]
                if len(passive) > 0:
                    metrics[f"mean_{col}_passive"] = passive[col].mean()
                if len(forced) > 0:
                    metrics[f"mean_{col}_forced"] = forced[col].mean()

        metrics["n_forced_fills"] = int(markout_df["is_forced"].sum())
        metrics["n_passive_fills"] = int((~markout_df["is_forced"]).sum())
        metrics.update(compute_crossing_cost(state, mid_price))

    return metrics


def plot_backtest_results(state: SimState, ticker: str = "AAPL", save_path: str = None):
    save_path = save_path or f"backtest_pnl_{ticker}.png"
    fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True)

    axes[0].plot(state.time_history, state.pnl_history, color="darkgreen", label="Total (mark-to-market)")
    axes[0].plot(state.time_history, state.realized_pnl_history, color="black", linestyle="--", label="Realized only")
    axes[0].set_ylabel("PnL ($)")
    axes[0].set_title(f"Avellaneda-Stoikov Market Maker — {ticker} Backtest")
    axes[0].axhline(0, color="black", linewidth=0.6)
    axes[0].legend(loc="upper left", fontsize=8)

    axes[1].plot(state.time_history, state.unrealized_pnl_history, color="darkorange")
    axes[1].set_ylabel("Unrealized PnL ($)")
    axes[1].axhline(0, color="black", linewidth=0.6)

    axes[2].plot(state.time_history, state.inventory_history, color="steelblue")
    axes[2].set_ylabel("Inventory (shares)")
    axes[2].set_xlabel("Time (seconds since midnight)")
    axes[2].axhline(0, color="black", linewidth=0.6)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    print(f"Saved backtest plot to {save_path}")


# ---------------------------------------------------------------------------
# 10. CROSS-SECTIONAL OUT-OF-SAMPLE VALIDATION (the key new addition)
# ---------------------------------------------------------------------------
def run_cross_sectional_validation(
    params: ASParams,
    tickers=ALL_TICKERS,
    train_ticker: str = TRAIN_TICKER,
    data_dir: str = "data",
    **backtest_kwargs,
) -> pd.DataFrame:
    """
    Runs the EXACT same, already-tuned parameters (tuned on AAPL) against every other
    free LOBSTER ticker with ZERO retuning. This is the honest test of whether the
    strategy generalizes or was curve-fit to one day's AAPL order flow. Report this
    table directly in your writeup -- it's more convincing than any single-ticker number.
    """
    rows = []
    for tkr in tickers:
        print(f"\n--- Validating on {tkr} ({'TRAIN' if tkr == train_ticker else 'OUT-OF-SAMPLE'}) ---")
        try:
            data = load_ticker(tkr, data_dir=data_dir)
        except FileNotFoundError:
            print(f"  [skipped] data files for {tkr} not found in {data_dir}/")
            continue
        state = run_backtest(data, params, **backtest_kwargs)
        m = compute_backtest_metrics(state, mid_price=data["mid_price"])
        m["ticker"] = tkr
        m["is_train"] = (tkr == train_ticker)
        rows.append(m)
        plot_backtest_results(state, ticker=tkr)
    return pd.DataFrame(rows)


def plot_cross_sectional_results(cs_df: pd.DataFrame, save_path: str = "cross_sectional_validation.png"):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    colors = ["darkred" if train else "steelblue" for train in cs_df["is_train"]]

    axes[0].bar(cs_df["ticker"], cs_df["final_pnl_realized"], color=colors)
    axes[0].axhline(0, color="black", linewidth=0.6)
    axes[0].set_ylabel("Realized PnL ($)")
    axes[0].set_title("Realized PnL by Ticker\n(red = in-sample/train, blue = out-of-sample)")

    axes[1].bar(cs_df["ticker"], cs_df["fill_rate"], color=colors)
    axes[1].set_ylabel("Fill Rate")
    axes[1].set_title("Fill Rate by Ticker")

    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    print(f"Saved cross-sectional validation plot to {save_path}")


# ---------------------------------------------------------------------------
# 11. ABLATION HARNESS (one change at a time, as you originally wanted)
# ---------------------------------------------------------------------------
def run_ablation(data: dict, base_params: ASParams, **backtest_kwargs) -> pd.DataFrame:
    """
    Cumulative ablation: start from the simplest version (touch-joining + hard flatten
    only, no OFI/inventory-skew/size-skew), then add each mechanism one at a time, so
    each row's delta vs. the previous row is directly attributable to ONE change.
    """
    configs = [
        ("baseline (touch-join + hard flatten only)", dict(use_ofi_signal=False, use_inventory_skew=False, use_size_skew=False)),
        ("+ inventory skew", dict(use_ofi_signal=False, use_inventory_skew=True, use_size_skew=False)),
        ("+ size skew", dict(use_ofi_signal=False, use_inventory_skew=True, use_size_skew=True)),
        ("+ OFI adverse-selection widen (full model)", dict(use_ofi_signal=True, use_inventory_skew=True, use_size_skew=True)),
    ]

    rows = []
    for label, overrides in configs:
        p = ASParams(**{**base_params.__dict__, **overrides})
        state = run_backtest(data, p, **backtest_kwargs)
        m = compute_backtest_metrics(state, mid_price=data["mid_price"])
        m["config"] = label
        rows.append(m)

    return pd.DataFrame(rows)


def run_gamma_sweep(data: dict, gammas, base_params: ASParams, **backtest_kwargs) -> pd.DataFrame:
    rows = []
    for g in gammas:
        p = ASParams(**{**base_params.__dict__, "gamma": g})
        state = run_backtest(data, p, **backtest_kwargs)
        m = compute_backtest_metrics(state, mid_price=data["mid_price"])
        m["gamma"] = g
        rows.append(m)
    return pd.DataFrame(rows)


def plot_gamma_sweep(sweep_df: pd.DataFrame, save_path: str = "gamma_sweep.png"):
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(sweep_df["gamma"], sweep_df["final_pnl_realized"], marker="o", color="darkgreen", label="Realized PnL")
    ax1.set_xlabel("Gamma (risk aversion)")
    ax1.set_ylabel("Realized PnL ($)", color="darkgreen")
    ax2 = ax1.twinx()
    ax2.plot(sweep_df["gamma"], sweep_df["inventory_std"], marker="s", color="steelblue", label="Inventory Std")
    ax2.set_ylabel("Inventory Std (shares)", color="steelblue")
    plt.title("Gamma Sweep: Risk-Return Trade-off\n(non-monotonicity reflects genuine regime-switching around the flatten threshold)")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    print(f"Saved gamma sweep plot to {save_path}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    _validate_ofi()

    # Load AAPL (train ticker) for signal research + ablation + gamma sweep
    data = load_ticker(TRAIN_TICKER)

    print("\n--- Information Coefficient (AAPL, train ticker) ---")
    ic_table = compute_ic_table(data, ofi_window=50, horizons=(10, 50, 200, 500, 1000))
    print(ic_table.to_string(index=False))

    deciles = decile_analysis(data, ofi_window=50, horizon=50)
    plot_decile_staircase(deciles, horizon=50)
    plot_ic_decay(ic_table)

    calibrate_arrival_intensity(data)  # printed for transparency, not used

    params = ASParams(gamma=0.1, kappa=3.2)
    backtest_kwargs = dict(order_size=200, requote_every_n_events=100, latency_events=2, inventory_limit=1000)

    print("\n=== Ablation (AAPL, one mechanism at a time) ===")
    ablation = run_ablation(data, params, **backtest_kwargs)
    print(ablation[["config", "final_pnl_realized", "fill_rate", "inventory_std",
                     "n_forced_flatten_crosses", "frac_quotes_touch_snapped"]].to_string(index=False))

    print("\n=== Gamma sweep (AAPL) ===")
    sweep = run_gamma_sweep(data, gammas=[0.01, 0.05, 0.1, 0.3, 0.5, 1.0], base_params=params, **backtest_kwargs)
    print(sweep[["gamma", "final_pnl_realized", "inventory_std", "max_abs_inventory", "fill_rate"]].to_string(index=False))
    plot_gamma_sweep(sweep)

    print("\n=== CROSS-SECTIONAL OUT-OF-SAMPLE VALIDATION ===")
    print("Same tuned params (AAPL-tuned), zero retuning, tested on all 5 free LOBSTER tickers.")
    cs_results = run_cross_sectional_validation(params, **backtest_kwargs)
    print(cs_results[["ticker", "is_train", "final_pnl_realized", "fill_rate",
                       "mean_markout_500", "frac_quotes_touch_snapped"]].to_string(index=False))
    plot_cross_sectional_results(cs_results)

    cs_results.to_csv("cross_sectional_results.csv", index=False)
    ablation.to_csv("ablation_results.csv", index=False)
    print("\nSaved cross_sectional_results.csv and ablation_results.csv")