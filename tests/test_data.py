import numpy as np

from mm import data


def test_load_keeps_integer_prices_and_splits_book_levels(tmp_path):
    stem = tmp_path / "TEST_2012-06-21_34200000_57600000"
    (tmp_path / f"{stem.name}_message_2.csv").write_text(
        "34200.1,1,11,100,5850100,1\n"
        "34200.2,5,12,50,5850050,-1\n")
    (tmp_path / f"{stem.name}_orderbook_2.csv").write_text(
        "5850100,200,5850000,100,5850200,300,5849900,400\n"
        "5850100,200,5850000,300,9999999999,0,-9999999999,0\n")

    m = data.load("TEST", tmp_path, levels=2)

    assert m.price.dtype.kind == "i" and m.price[1] == 5850050  # hidden trade at a half tick
    assert m.best_bid.tolist() == [5850000, 5850000]
    assert m.ask_px[0].tolist() == [5850100, 5850200]
    assert m.bid_sz[1].tolist() == [300, 0]
    # micro leans to the thinner side: 100 on the bid, 200 on the ask -> closer to the bid
    assert np.isclose(m.micro[0], (100 * 5850100 + 200 * 5850000) / 300)
    assert data.dollars(m.mid[0]) == 585.005
