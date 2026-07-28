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


# ---------------------------------------------------------------------------
# 5. ARRIVAL INTENSITY CALIBRATION
# ---------------------------------------------------------------------------
def calibrate_arrival_intensity(data: dict, n_buckets: int = 15, max_ticks: int = 20, tick_size: float = 0.01):
    """
    NOTE / CAVEAT (add this to your writeup — it's an honest limitation, not a bug):
    This fits lambda(delta) from the distribution of *executed trade* distances from mid,
    not from limit-order arrival/cancellation rates at each price level. That measures
    "how far from mid do fills happen" rather than "how quickly would a resting quote at
    distance delta get filled" (queue-reactive arrival intensity). It's a reasonable proxy
    and standard in intro treatments of A-S, but it systematically concentrates mass near
    the touch (because almost all trades print at or near best bid/ask), which is part of
    why the fitted kappa pushed quotes further from touch than the real market ever is.
    We now treat kappa as informational / a diagnostic rather than feeding the raw fitted
    value directly into a spread that can dominate the actual tick-size market spread.
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

    print(f"Calibrated arrival intensity (diagnostic only): A={A:.2f}, kappa={kappa:.4f}, R^2={r_value**2:.3f}")
    return A, kappa


# ---------------------------------------------------------------------------
# 6. AVELLANEDA-STOIKOV QUOTING LOGIC
# ---------------------------------------------------------------------------
@dataclass
class ASParams:
    gamma: float = 0.1                 # risk aversion
    kappa: float = 3.2                 # order arrival decay (calibrated, but now capped in use — see max_half_spread_ticks)
    A: float = 10000.0                 # order arrival base rate (informational only)
    T: float = 23400.0                 # trading session length in seconds (6.5h)
    sigma: float = 0.02                # rolling volatility estimate (recalibrated live)
    ofi_z_threshold: float = 2.0       # widen/skew when |OFI z-score| exceeds this
    use_ofi_signal: bool = True        # NEW: toggle for the OFI on/off A-B comparison
    max_half_spread_ticks: float = 3.0 # NEW: hard cap on how far the A-S half-spread can push us from mid
    min_half_spread_ticks: float = 0.5 # NEW: floor so we still capture *some* edge when vol is near zero
    touch_join_ticks: float = 1.0      # NEW: if theoretical quote sits more than this many ticks behind
                                        # touch, just join the touch instead of quoting into empty space
    aggressive_inventory_frac: float = 0.5  # NEW: fraction of inventory_limit that triggers spread-crossing
    inventory_skew_ticks_per_100_per_gamma: float = 1.0
    max_inventory_skew_ticks: float = 3.0
    # NEW: at this tick size / event-level volatility, the textbook A-S inventory term
    # (inventory * gamma * sigma^2 * time_remaining) is numerically negligible -- it never
    # gets large enough to actually lean quotes against a growing position. This parameter
    # replaces it with an explicit, gamma-scaled skew in tick units so (a) gamma has a
    # visible effect in the gamma sweep, and (b) inventory is actually managed by price
    # skew rather than only by the hard flatten-override. max_inventory_skew_ticks caps it
    # so a high gamma can't grow large enough to force an involuntary spread-crossing trade
    # on its own -- only the explicit flatten override (below) is allowed to do that.
    protective_widen_ticks: float = 4.0
    # NEW: when OFI signals adverse selection risk on one side, that side is WIDENED to this
    # many ticks behind the touch rather than skipped outright. Being skipped entirely was
    # starving one side, concentrating inventory, and then forcing the hard flatten override
    # to dump that inventory at exactly the worst (trend-confirming) moment.


def compute_reservation_price(mid: float, inventory: int, sigma: float, gamma: float, time_remaining: float) -> float:
    """r(t) = s(t) - q * gamma * sigma^2 * (T - t)"""
    return mid - inventory * gamma * (sigma ** 2) * time_remaining


def compute_optimal_half_spread(gamma: float, sigma: float, time_remaining: float, kappa: float) -> float:
    """delta_total = gamma*sigma^2*(T-t) + (2/gamma)*ln(1 + gamma/kappa); returned as HALF-spread."""
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
    is_forced: bool = False  # NEW: True if this order was created by the hard flatten
                             # override (crosses the spread) rather than passive touch-joining


@dataclass
class SimState:
    inventory: int = 0
    cash: float = 0.0
    avg_cost: float = 0.0                 # NEW: average cost basis of current inventory
    realized_pnl: float = 0.0             # NEW: PnL actually locked in by round-trip trades
    pnl_history: list = field(default_factory=list)
    realized_pnl_history: list = field(default_factory=list)   # NEW
    unrealized_pnl_history: list = field(default_factory=list) # NEW
    inventory_history: list = field(default_factory=list)
    time_history: list = field(default_factory=list)
    fill_log: list = field(default_factory=list)  # (time, side, price, size, event_index, is_forced)
    n_quotes_placed: int = 0
    n_fills: int = 0
    n_requotes_same_price: int = 0
    n_requotes_new_price: int = 0
    quote_touch_distance_ticks: list = field(default_factory=list)  # NEW diagnostic
    n_forced_flatten_crosses: int = 0        # NEW diagnostic
    forced_flatten_z_values: list = field(default_factory=list)  # NEW: OFI z-score at each forced flatten


def update_avg_cost_and_realized(state: SimState, prev_inventory: int, signed_fill: int, price: float):
    """
    Average-cost inventory accounting. This is what lets us separate:
      - realized_pnl: PnL actually earned by buying and later selling (or vice versa) —
        this is the number that reflects genuine market-making skill.
      - unrealized (mark-to-market) PnL: inventory * (current_mid - avg_cost) — this can
        be large and positive purely because the stock drifted while you sat on a stuck
        position. That's what was happening in the original backtest.
    """
    if prev_inventory == 0 or np.sign(prev_inventory) == np.sign(signed_fill):
        total_size = abs(prev_inventory) + abs(signed_fill)
        state.avg_cost = (
            (state.avg_cost * abs(prev_inventory) + price * abs(signed_fill)) / total_size
            if total_size > 0 else price
        )
    else:
        closing_size = min(abs(signed_fill), abs(prev_inventory))
        direction = np.sign(prev_inventory)  # +1 if closing a long (i.e. selling), -1 if closing a short (buying)
        state.realized_pnl += closing_size * (price - state.avg_cost) * direction
        remaining = abs(signed_fill) - closing_size
        if remaining > 0:
            state.avg_cost = price  # flipped through zero -> new position opened at this fill price

    state.inventory = prev_inventory + signed_fill


def lookup_displayed_size(orderbook_row, price: float, side: str, num_levels: int = 10, tick_size: float = 0.01) -> float:
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
    order_size: int = 100,
    requote_every_n_events: int = 25,
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

            # Bid fill: seller-initiated trade (d == -1) at a price <= our bid fills our buy order
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

            # Ask fill: buyer-initiated trade (d == 1) at a price >= our ask fills our sell order
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

        # --- 1b. Enforce inventory limits ---
        if state.inventory >= inventory_limit and our_bid is not None:
            our_bid = None
        if state.inventory <= -inventory_limit and our_ask is not None:
            our_ask = None

        # --- 2. Recompute desired quotes periodically ---
        if i % requote_every_n_events == 0:
            sigma = sigma_series[i]
            z = ofi_z[i]
            best_bid, best_ask = best_bid_arr[i], best_ask_arr[i]

            # NOTE: compute_reservation_price's classical inventory term is negligible at
            # this tick/vol scale (see ASParams docstrings) -- the skew that actually does
            # anything is added explicitly below.
            r = micro_price[i]
            as_half_spread = compute_optimal_half_spread(params.gamma, sigma, t_remaining / total_T * params.T, params.kappa)

            # FIX: cap the theoretical A-S half-spread to a tick-realistic range. The raw
            # formula routinely produced half-spreads of many ticks (or dollars), while the
            # real touch spread on AAPL is ~1 tick — so uncapped quotes were parked in empty
            # space that LOBSTER trades (which print only at the touch) could never reach.
            half_spread = np.clip(
                as_half_spread,
                params.min_half_spread_ticks * tick_size,
                params.max_half_spread_ticks * tick_size,
            )

            # Explicit, gamma-scaled inventory skew (replaces the numerically negligible
            # classical term). Positive inventory (long) pushes r down -> more eager to
            # sell, less eager to buy, and vice versa. FIX: capped at max_inventory_skew_ticks
            # so a high gamma can nudge quotes but can never by itself force a price through
            # the touch into an involuntary spread-crossing trade -- only the explicit
            # flatten override below is allowed to do that, deliberately.
            raw_skew = params.gamma * params.inventory_skew_ticks_per_100_per_gamma * (state.inventory / 100.0)
            inventory_skew = np.clip(raw_skew, -params.max_inventory_skew_ticks, params.max_inventory_skew_ticks) * tick_size
            r -= inventory_skew

            # Asymmetric OFI adverse-selection protection. FIX from the previous version:
            # rather than skipping a side entirely (which starved it, concentrated inventory
            # on the other side, and then forced the hard flatten override to dump that
            # inventory at exactly the worst, trend-confirming moment), the "at-risk" side is
            # now WIDENED to protective_widen_ticks instead. It's still quoted -- if filled,
            # the extra distance compensates for the adverse-selection risk -- but it no
            # longer disappears and forces one-sided inventory buildup.
            protect_ask = params.use_ofi_signal and z > params.ofi_z_threshold
            protect_bid = params.use_ofi_signal and z < -params.ofi_z_threshold

            bid_half_spread = max(half_spread, params.protective_widen_ticks * tick_size) if protect_bid else half_spread
            ask_half_spread = max(half_spread, params.protective_widen_ticks * tick_size) if protect_ask else half_spread

            can_buy = state.inventory < inventory_limit
            can_sell = state.inventory > -inventory_limit

            new_bid_px = round((r - bid_half_spread) / tick_size) * tick_size if can_buy else None
            new_ask_px = round((r + ask_half_spread) / tick_size) * tick_size if can_sell else None

            # never let the two sides cross
            if new_bid_px is not None and new_bid_px >= best_ask:
                new_bid_px = round((best_ask - tick_size) / tick_size) * tick_size
            if new_ask_px is not None and new_ask_px <= best_bid:
                new_ask_px = round((best_bid + tick_size) / tick_size) * tick_size

            # never be MORE aggressive than the touch (don't jump the whole visible book)
            if new_bid_px is not None:
                new_bid_px = min(new_bid_px, best_bid)
            if new_ask_px is not None:
                new_ask_px = max(new_ask_px, best_ask)

            # If the quote sits meaningfully behind the touch, join the touch instead --
            # UNLESS we're deliberately protecting that side this cycle, in which case
            # standing back from the touch is the point.
            if new_bid_px is not None and not protect_bid and (best_bid - new_bid_px) > params.touch_join_ticks * tick_size:
                new_bid_px = best_bid
            if new_ask_px is not None and not protect_ask and (new_ask_px - best_ask) > params.touch_join_ticks * tick_size:
                new_ask_px = best_ask

            # Diagnostic: how far (in ticks) our quotes sit from the touch before any override
            if new_bid_px is not None:
                state.quote_touch_distance_ticks.append((best_bid - new_bid_px) / tick_size)
            if new_ask_px is not None:
                state.quote_touch_distance_ticks.append((new_ask_px - best_ask) / tick_size)

            # Inventory-driven aggressiveness override — threshold scales with
            # inventory_limit / order_size. Diagnostics recorded so we can check whether
            # this still tends to fire during a sustained OFI trend against us.
            forced_bid = False
            forced_ask = False
            if state.inventory < -flatten_threshold and can_buy:
                new_bid_px = best_ask
                new_ask_px = None
                forced_bid = True
                state.n_forced_flatten_crosses += 1
                state.forced_flatten_z_values.append(z)
            if state.inventory > flatten_threshold and can_sell:
                new_ask_px = best_bid
                new_bid_px = None
                forced_ask = True
                state.n_forced_flatten_crosses += 1
                state.forced_flatten_z_values.append(z)

            pending_quotes = (new_bid_px, new_ask_px, order_size, forced_bid, forced_ask)
            pending_quote_event = i + latency_events
            state.n_quotes_placed += 1

        # --- 3. Apply pending quotes (only reset queue position on real price change) ---
        if pending_quotes is not None and i >= pending_quote_event:
            new_bid_px, new_ask_px, sz, forced_bid, forced_ask = pending_quotes

            if new_bid_px is not None:
                if our_bid is not None and abs(our_bid.price - new_bid_px) < 1e-9:
                    state.n_requotes_same_price += 1
                else:
                    state.n_requotes_new_price += 1
                    displayed = lookup_displayed_size(data["orderbook"].iloc[i], new_bid_px, "bid")
                    our_bid = RestingOrder(price=new_bid_px, size=sz, ahead_volume=displayed, is_forced=forced_bid)

            if new_ask_px is not None:
                if our_ask is not None and abs(our_ask.price - new_ask_px) < 1e-9:
                    pass
                else:
                    displayed = lookup_displayed_size(data["orderbook"].iloc[i], new_ask_px, "ask")
                    our_ask = RestingOrder(price=new_ask_px, size=sz, ahead_volume=displayed, is_forced=forced_ask)

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
# 8. MARKOUT ANALYSIS (NEW — the standard adverse-selection diagnostic)
# ---------------------------------------------------------------------------
def compute_markouts(state: SimState, mid_price: np.ndarray, horizons=(100, 500, 1000)) -> pd.DataFrame:
    """
    For each fill, compares the fill price to the mid-price some events later.
    For a BUY fill: markout = future_mid - fill_price. Positive means price rose after
    we bought (good). Negative means we were adversely selected.
    For a SELL fill: markout = fill_price - future_mid, same interpretation mirrored.
    `is_forced` marks fills that came from the hard inventory-flatten override (crossing
    the spread) rather than passive touch-joining -- these have a different economics
    (you pay the spread rather than earn it) and should generally be looked at separately.
    """
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


def compute_crossing_cost(state: SimState, mid_price: np.ndarray) -> float:
    """
    Estimates the total cost of forced spread-crossing fills: for a forced BUY, cost =
    price - mid_at_fill (positive = paid above mid, i.e. gave away half the spread or
    more). For a forced SELL, cost = mid_at_fill - price. Summed over size. This isolates
    "cost of emergency inventory flattening" from "cost of adverse selection on passive
    fills" -- two different problems that were previously blended into one PnL number.
    """
    total_cost = 0.0
    for (t, side, price, size, idx, is_forced) in state.fill_log:
        if not is_forced:
            continue
        m = mid_price[idx]
        cost_per_share = (price - m) if side == "BUY" else (m - price)
        total_cost += cost_per_share * size
    return total_cost


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

    metrics = {
        "final_pnl_total": pnl[-1],
        "final_pnl_realized": realized[-1],
        "final_pnl_unrealized": pnl[-1] - realized[-1],
        # sharpe_total includes mark-to-market drift on open inventory -- report it, but
        # sharpe_realized is the more defensible "did this actually make trading decisions
        # that made money" number.
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
        "n_forced_flatten_crosses": state.n_forced_flatten_crosses,
        "mean_ofi_z_at_forced_flatten": (
            np.mean(state.forced_flatten_z_values) if state.forced_flatten_z_values else np.nan
        ),
        # If this is large in magnitude and same-signed as the flatten direction (positive
        # inventory forcing a sell while z is still positive/bullish, or negative inventory
        # forcing a buy while z is still negative/bearish), forced flattens are dumping
        # inventory into the trend rather than against it -- the exact failure mode we're
        # checking for.
    }

    if mid_price is not None and len(state.fill_log) > 0:
        markout_df = compute_markouts(state, mid_price, markout_horizons)
        for h in markout_horizons:
            col = f"markout_{h}"
            if col in markout_df.columns:
                metrics[f"mean_{col}"] = markout_df[col].mean()
                # Split by fill type -- forced (spread-crossing) fills have fundamentally
                # different economics from passive touch-joining fills and mixing them
                # together obscures which problem (crossing cost vs. adverse selection)
                # is actually driving PnL.
                passive = markout_df[~markout_df["is_forced"]]
                forced = markout_df[markout_df["is_forced"]]
                if len(passive) > 0:
                    metrics[f"mean_{col}_passive"] = passive[col].mean()
                if len(forced) > 0:
                    metrics[f"mean_{col}_forced"] = forced[col].mean()

        metrics["n_forced_fills"] = int(markout_df["is_forced"].sum())
        metrics["n_passive_fills"] = int((~markout_df["is_forced"]).sum())
        metrics["total_crossing_cost"] = compute_crossing_cost(state, mid_price)

    return metrics


def plot_backtest_results(state: SimState, save_path: str = "backtest_pnl.png"):
    fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True)

    axes[0].plot(state.time_history, state.pnl_history, color="darkgreen", label="Total (mark-to-market)")
    axes[0].plot(state.time_history, state.realized_pnl_history, color="black", linestyle="--", label="Realized only")
    axes[0].set_ylabel("PnL ($)")
    axes[0].set_title("Avellaneda-Stoikov Market Maker — Backtest Results")
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
# 10. GAMMA SWEEP AND OFI ON/OFF A-B HARNESSES
# ---------------------------------------------------------------------------
def run_gamma_sweep(data: dict, gammas, base_params: ASParams, **backtest_kwargs) -> pd.DataFrame:
    """Risk-return sweep: for each gamma, run the backtest and record metrics."""
    rows = []
    for g in gammas:
        p = ASParams(**{**base_params.__dict__, "gamma": g})
        state = run_backtest(data, p, **backtest_kwargs)
        m = compute_backtest_metrics(state, mid_price=data["mid_price"])
        m["gamma"] = g
        rows.append(m)
    return pd.DataFrame(rows)


def run_ofi_ab_test(data: dict, params: ASParams, **backtest_kwargs) -> pd.DataFrame:
    """A/B comparison: OFI adverse-selection overlay on vs. off, all else equal."""
    p_on = ASParams(**{**params.__dict__, "use_ofi_signal": True})
    p_off = ASParams(**{**params.__dict__, "use_ofi_signal": False})

    state_on = run_backtest(data, p_on, **backtest_kwargs)
    state_off = run_backtest(data, p_off, **backtest_kwargs)

    m_on = compute_backtest_metrics(state_on, mid_price=data["mid_price"])
    m_off = compute_backtest_metrics(state_off, mid_price=data["mid_price"])
    m_on["ofi_signal"] = "on"
    m_off["ofi_signal"] = "off"
    return pd.DataFrame([m_on, m_off])


def plot_gamma_sweep(sweep_df: pd.DataFrame, save_path: str = "gamma_sweep.png"):
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(sweep_df["gamma"], sweep_df["final_pnl_realized"], marker="o", color="darkgreen", label="Realized PnL")
    ax1.set_xlabel("Gamma (risk aversion)")
    ax1.set_ylabel("Realized PnL ($)", color="darkgreen")
    ax2 = ax1.twinx()
    ax2.plot(sweep_df["gamma"], sweep_df["inventory_std"], marker="s", color="steelblue", label="Inventory Std")
    ax2.set_ylabel("Inventory Std (shares)", color="steelblue")
    plt.title("Gamma Sweep: Risk-Return Trade-off")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    print(f"Saved gamma sweep plot to {save_path}")


# ---------------------------------------------------------------------------
# 4. MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    _validate_ofi()

    msg_file = "data/AAPL_2012-06-21_34200000_57600000_message_10.csv"
    ob_file = "data/AAPL_2012-06-21_34200000_57600000_orderbook_10.csv"

    data = load_lobster_data(msg_file, ob_file)

    print("\n--- Information Coefficient across horizons (OFI window = 50 events) ---")
    ic_table = compute_ic_table(data, ofi_window=50, horizons=(10, 50, 200, 500, 1000))
    print(ic_table.to_string(index=False))

    print("\n--- Decile Analysis (horizon = 50 events) ---")
    deciles = decile_analysis(data, ofi_window=50, horizon=50)
    print(deciles.to_string(index=False))

    plot_decile_staircase(deciles, horizon=50)
    plot_ic_decay(ic_table)

    A, kappa = calibrate_arrival_intensity(data)

    params = ASParams(gamma=0.1, kappa=3.2, max_half_spread_ticks=3.0, touch_join_ticks=1.0)

    print("\nRunning AS market-making backtest...")
    state = run_backtest(
        data, params,
        order_size=200,
        requote_every_n_events=100,
        latency_events=2,
        inventory_limit=1000,
    )

    metrics = compute_backtest_metrics(state, mid_price=data["mid_price"])
    print("\n--- Backtest Metrics ---")
    for k, v in metrics.items():
        print(f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}")

    print(f"n_requotes_same_price / n_quotes_placed: {state.n_requotes_same_price / state.n_quotes_placed:.4f}")

    plot_backtest_results(state)

    # --- Gamma sweep (risk-return deliverable) ---
    print("\nRunning gamma sweep...")
    sweep = run_gamma_sweep(
        data, gammas=[0.01, 0.05, 0.1, 0.3, 0.5, 1.0], base_params=params,
        order_size=200, requote_every_n_events=100, latency_events=2, inventory_limit=1000,
    )
    print(sweep[["gamma", "final_pnl_realized", "inventory_std", "max_abs_inventory", "fill_rate"]].to_string(index=False))
    plot_gamma_sweep(sweep)

    # --- OFI on/off A-B test ---
    print("\nRunning OFI on/off A-B test...")
    ab = run_ofi_ab_test(
        data, params,
        order_size=200, requote_every_n_events=100, latency_events=2, inventory_limit=1000,
    )
    print(ab[["ofi_signal", "final_pnl_realized", "mean_markout_500", "inventory_std"]].to_string(index=False))