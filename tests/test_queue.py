from dataclasses import replace

import pytest

from mm.data import BUY, CANCEL, DELETE, EXECUTE, EXECUTE_HIDDEN, HALT, SELL, SUBMIT
from mm.queue import ASK, BID, OPTIMISTIC, PESSIMISTIC, FillModel, RestingOrder, take

P = 1_000_000
M = FillModel()  # defaults: the simulator's original assumptions


def bid(ahead=100, size=20, price=P):
    return RestingOrder(BID, price, size, ahead)


def ask(ahead=100, size=20, price=P):
    return RestingOrder(ASK, price, size, ahead)


@pytest.mark.parametrize("etype", [CANCEL, DELETE])
def test_cancels_at_our_price_and_side_move_us_up(etype):
    order, filled = M.on_event(bid(), etype, P, 30, BUY)
    assert (order.ahead, filled) == (70, 0)


@pytest.mark.parametrize("price, direction", [(P - 100, BUY), (P, SELL)])
def test_cancels_elsewhere_do_not_move_us(price, direction):
    assert M.on_event(bid(), DELETE, price, 30, direction) == (bid(), 0)


def test_cancels_never_fill_even_past_the_front():
    order, filled = M.on_event(bid(ahead=10), DELETE, P, 30, BUY)
    assert (order.ahead, filled) == (-20, 0)


@pytest.mark.parametrize("etype", [EXECUTE, EXECUTE_HIDDEN])
def test_trade_smaller_than_queue_only_eats_queue(etype):
    order, filled = M.on_event(bid(), etype, P, 100, BUY)
    assert (order.ahead, filled) == (0, 0)


def test_trade_past_queue_fills_only_the_excess():
    order, filled = M.on_event(bid(ahead=100, size=20), EXECUTE, P, 105, BUY)
    assert (order.size, order.ahead, filled) == (15, -5, 5)


def test_trade_bigger_than_queue_and_order_fills_order_and_removes_it():
    assert M.on_event(bid(ahead=100, size=20), EXECUTE, P, 500, BUY) == (None, 20)


def test_once_at_front_the_next_trade_fills_up_to_its_size():
    order, _ = M.on_event(bid(ahead=0, size=20), EXECUTE, P, 5, BUY)
    order, filled = M.on_event(order, EXECUTE, P, 8, BUY)
    assert (order.size, filled) == (7, 8)


def test_trade_direction_is_the_resting_side_hit():
    # A seller hitting the bid is recorded with direction BUY (the bid's side).
    assert M.on_event(bid(ahead=0), EXECUTE, P, 50, SELL) == (bid(ahead=0), 0)
    assert M.on_event(ask(ahead=0), EXECUTE, P, 50, BUY) == (ask(ahead=0), 0)
    assert M.on_event(ask(ahead=0), EXECUTE, P, 50, SELL)[1] == 20


def test_trade_through_our_price_reaches_us():
    assert M.on_event(bid(ahead=0), EXECUTE, P - 100, 50, BUY)[1] == 20
    assert M.on_event(ask(ahead=0), EXECUTE, P + 100, 50, SELL)[1] == 20


def test_trade_at_a_better_price_than_ours_does_not():
    assert M.on_event(bid(ahead=0), EXECUTE, P + 100, 50, BUY)[1] == 0
    assert M.on_event(ask(ahead=0), EXECUTE, P - 100, 50, SELL)[1] == 0


def test_hidden_trade_at_half_tick_through_us_reaches_us():
    assert M.on_event(bid(ahead=0), EXECUTE_HIDDEN, P - 50, 50, BUY)[1] == 20


@pytest.mark.parametrize("etype", [SUBMIT, HALT])
def test_submits_and_halts_do_nothing(etype):
    assert M.on_event(bid(), etype, P, 50, BUY) == (bid(), 0)


LEVELS_PX = [P, P - 100, P - 200]
LEVELS_SZ = [300, 400, 500]


def test_queue_ahead_is_displayed_size_at_our_level():
    assert M.queue_ahead(BID, P - 100, LEVELS_PX, LEVELS_SZ) == 400


def test_queue_ahead_inside_the_spread_is_empty():
    assert M.queue_ahead(BID, P + 100, LEVELS_PX, LEVELS_SZ) == 0


def test_queue_ahead_below_visible_book_uses_last_level():
    assert M.queue_ahead(BID, P - 900, LEVELS_PX, LEVELS_SZ) == 500


def test_queue_ahead_ignores_empty_level_sentinels():
    assert M.queue_ahead(BID, P - 900, [P, -9_999_999_999], [300, 0]) == 0
    assert M.queue_ahead(ASK, P + 900, [P, 9_999_999_999], [300, 0]) == 0


ASKS_PX = [P, P + 100, P + 200]
ASKS_SZ = [30, 40, 9_999]


def test_marketable_bid_sweeps_asks_up_to_its_limit_at_their_prices():
    assert take(BID, P + 100, 50, ASKS_PX, ASKS_SZ) == [(P, 30), (P + 100, 20)]


def test_marketable_order_stops_at_its_limit_price():
    assert take(BID, P, 50, ASKS_PX, ASKS_SZ) == [(P, 30)]


def test_marketable_ask_sweeps_bids():
    assert take(ASK, P - 100, 350, LEVELS_PX, LEVELS_SZ) == [(P, 300), (P - 100, 50)]


def test_order_that_does_not_cross_takes_nothing():
    assert take(BID, P - 100, 50, ASKS_PX, ASKS_SZ) == []
    assert take(ASK, P + 100, 50, LEVELS_PX, LEVELS_SZ) == []


def test_same_price_smaller_size_keeps_queue_place():
    assert M.replace_order(BID, bid(ahead=40, size=20), P, 10, False, LEVELS_PX, LEVELS_SZ) == bid(ahead=40, size=10)


def test_same_price_larger_size_goes_to_the_back():
    assert M.replace_order(BID, bid(ahead=40, size=20), P, 30, False, LEVELS_PX, LEVELS_SZ) == bid(ahead=300, size=30)


def test_new_price_goes_to_the_back():
    assert M.replace_order(BID, bid(ahead=40), P - 100, 20, False, LEVELS_PX, LEVELS_SZ) == bid(ahead=400, price=P - 100)


def test_replacing_updates_the_forced_flag():
    assert M.replace_order(BID, bid(ahead=40), P, 20, True, LEVELS_PX, LEVELS_SZ).forced


def test_no_resting_order_joins_the_back():
    assert M.replace_order(BID, None, P, 20, False, LEVELS_PX, LEVELS_SZ) == bid(ahead=300)


# FillModel switches: each assumption the data can't settle, tested at every setting.

def test_cancels_behind_us_never_move_us_up():
    assert FillModel(cancels="behind").on_event(bid(), DELETE, P, 30, BUY) == (bid(), 0)


@pytest.mark.parametrize("submitted_at, ahead", [(-1, 70), (4, 70), (6, 100)])
def test_exact_cancels_skip_orders_that_joined_after_us(submitted_at, ahead):
    # We joined at event 5. Orders from before the open (-1) or before event 5 are ahead; later ones behind.
    order = replace(bid(), placed_at=5)
    moved, _ = FillModel(cancels="exact").on_event(order, CANCEL, P, 30, BUY, submitted_at)
    assert moved.ahead == ahead


def test_hidden_trade_at_our_price_can_leave_the_visible_queue_alone():
    model = FillModel(hidden_trades_eat_queue=False)
    assert model.on_event(bid(), EXECUTE_HIDDEN, P, 100, BUY) == (bid(), 0)
    assert model.on_event(bid(ahead=0), EXECUTE_HIDDEN, P - 50, 50, BUY)[1] == 20  # through us still counts


def test_trade_through_our_price_can_fill_us_whatever_is_left_ahead():
    assert FillModel(trade_through_fills=True).on_event(bid(ahead=500), EXECUTE, P - 100, 5, BUY) == (None, 20)
    assert FillModel(trade_through_fills=False).on_event(bid(ahead=500), EXECUTE, P - 100, 5, BUY)[1] == 0
    assert FillModel(trade_through_fills=True).on_event(bid(ahead=500), EXECUTE, P, 5, BUY)[1] == 0


def test_unseen_queue_below_the_visible_book_can_be_empty():
    assert FillModel(unseen_queue="empty").queue_ahead(BID, P - 900, LEVELS_PX, LEVELS_SZ) == 0


def test_a_new_order_records_when_it_joined_and_a_kept_one_keeps_it():
    new = M.replace_order(BID, None, P, 20, False, LEVELS_PX, LEVELS_SZ, now=7)
    assert new.placed_at == 7
    assert M.replace_order(BID, new, P, 10, False, LEVELS_PX, LEVELS_SZ, now=9).placed_at == 7


def test_presets_bracket_the_defaults():
    assert (PESSIMISTIC.cancels, PESSIMISTIC.hidden_trades_eat_queue, PESSIMISTIC.trade_through_fills) ==         ("behind", False, False)
    assert (OPTIMISTIC.cancels, OPTIMISTIC.hidden_trades_eat_queue, OPTIMISTIC.trade_through_fills) ==         ("ahead", True, True)
