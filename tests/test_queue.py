import pytest

from mm.data import BUY, CANCEL, DELETE, EXECUTE, EXECUTE_HIDDEN, HALT, SELL, SUBMIT
from mm.queue import ASK, BID, RestingOrder, on_event, queue_ahead, replace_order, take

P = 1_000_000


def bid(ahead=100, size=20, price=P):
    return RestingOrder(BID, price, size, ahead)


def ask(ahead=100, size=20, price=P):
    return RestingOrder(ASK, price, size, ahead)


@pytest.mark.parametrize("etype", [CANCEL, DELETE])
def test_cancels_at_our_price_and_side_move_us_up(etype):
    order, filled = on_event(bid(), etype, P, 30, BUY)
    assert (order.ahead, filled) == (70, 0)


@pytest.mark.parametrize("price, direction", [(P - 100, BUY), (P, SELL)])
def test_cancels_elsewhere_do_not_move_us(price, direction):
    assert on_event(bid(), DELETE, price, 30, direction) == (bid(), 0)


def test_cancels_never_fill_even_past_the_front():
    order, filled = on_event(bid(ahead=10), DELETE, P, 30, BUY)
    assert (order.ahead, filled) == (-20, 0)


@pytest.mark.parametrize("etype", [EXECUTE, EXECUTE_HIDDEN])
def test_trade_smaller_than_queue_only_eats_queue(etype):
    order, filled = on_event(bid(), etype, P, 100, BUY)
    assert (order.ahead, filled) == (0, 0)


def test_trade_past_queue_fills_only_the_excess():
    order, filled = on_event(bid(ahead=100, size=20), EXECUTE, P, 105, BUY)
    assert (order.size, order.ahead, filled) == (15, -5, 5)


def test_trade_bigger_than_queue_and_order_fills_order_and_removes_it():
    assert on_event(bid(ahead=100, size=20), EXECUTE, P, 500, BUY) == (None, 20)


def test_once_at_front_the_next_trade_fills_up_to_its_size():
    order, _ = on_event(bid(ahead=0, size=20), EXECUTE, P, 5, BUY)
    order, filled = on_event(order, EXECUTE, P, 8, BUY)
    assert (order.size, filled) == (7, 8)


def test_trade_direction_is_the_resting_side_hit():
    # A seller hitting the bid is recorded with direction BUY (the bid's side).
    assert on_event(bid(ahead=0), EXECUTE, P, 50, SELL) == (bid(ahead=0), 0)
    assert on_event(ask(ahead=0), EXECUTE, P, 50, BUY) == (ask(ahead=0), 0)
    assert on_event(ask(ahead=0), EXECUTE, P, 50, SELL)[1] == 20


def test_trade_through_our_price_reaches_us():
    assert on_event(bid(ahead=0), EXECUTE, P - 100, 50, BUY)[1] == 20
    assert on_event(ask(ahead=0), EXECUTE, P + 100, 50, SELL)[1] == 20


def test_trade_at_a_better_price_than_ours_does_not():
    assert on_event(bid(ahead=0), EXECUTE, P + 100, 50, BUY)[1] == 0
    assert on_event(ask(ahead=0), EXECUTE, P - 100, 50, SELL)[1] == 0


def test_hidden_trade_at_half_tick_through_us_reaches_us():
    assert on_event(bid(ahead=0), EXECUTE_HIDDEN, P - 50, 50, BUY)[1] == 20


@pytest.mark.parametrize("etype", [SUBMIT, HALT])
def test_submits_and_halts_do_nothing(etype):
    assert on_event(bid(), etype, P, 50, BUY) == (bid(), 0)


LEVELS_PX = [P, P - 100, P - 200]
LEVELS_SZ = [300, 400, 500]


def test_queue_ahead_is_displayed_size_at_our_level():
    assert queue_ahead(BID, P - 100, LEVELS_PX, LEVELS_SZ) == 400


def test_queue_ahead_inside_the_spread_is_empty():
    assert queue_ahead(BID, P + 100, LEVELS_PX, LEVELS_SZ) == 0


def test_queue_ahead_below_visible_book_uses_last_level():
    assert queue_ahead(BID, P - 900, LEVELS_PX, LEVELS_SZ) == 500


def test_queue_ahead_ignores_empty_level_sentinels():
    assert queue_ahead(BID, P - 900, [P, -9_999_999_999], [300, 0]) == 0
    assert queue_ahead(ASK, P + 900, [P, 9_999_999_999], [300, 0]) == 0


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
    assert replace_order(BID, bid(ahead=40, size=20), P, 10, False, LEVELS_PX, LEVELS_SZ) == bid(ahead=40, size=10)


def test_same_price_larger_size_goes_to_the_back():
    assert replace_order(BID, bid(ahead=40, size=20), P, 30, False, LEVELS_PX, LEVELS_SZ) == bid(ahead=300, size=30)


def test_new_price_goes_to_the_back():
    assert replace_order(BID, bid(ahead=40), P - 100, 20, False, LEVELS_PX, LEVELS_SZ) == bid(ahead=400, price=P - 100)


def test_replacing_updates_the_forced_flag():
    assert replace_order(BID, bid(ahead=40), P, 20, True, LEVELS_PX, LEVELS_SZ).forced


def test_no_resting_order_joins_the_back():
    assert replace_order(BID, None, P, 20, False, LEVELS_PX, LEVELS_SZ) == bid(ahead=300)
