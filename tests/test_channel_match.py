"""Buy-price channel matching tolerates retailer-name vs price-column differences.

Real NZ price columns from customsearch1413 use labels like "NZ - Noel Leeming" and
"JB HIfi" while the retailer list says "Noel Leeming" / "JB HIFI" — these must still match.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import _channel_price

NZ_PRICES = {"Harvey Norman": 18.25, "JB HIfi": 18.30, "NZ - Noel Leeming": 15.82,
             "NZ - PB Technologies": 15.65, "Costco": 5.0, "Dealer 1": 15.65,
             "Education": 23.47}


def test_tolerant_channel_match():
    assert _channel_price(NZ_PRICES, "Harvey Norman") == 18.25   # exact
    assert _channel_price(NZ_PRICES, "JB HIFI") == 18.30         # case differs
    assert _channel_price(NZ_PRICES, "Noel Leeming") == 15.82    # "NZ - " prefix
    assert _channel_price(NZ_PRICES, "PB Tech") == 15.65         # alias -> Technologies
    assert _channel_price(NZ_PRICES, "Costco Wholesale") == 5.0  # alias -> Costco
    assert _channel_price(NZ_PRICES, "Dealer 1") == 15.65
    assert _channel_price(NZ_PRICES, "Cyclone Computer Co Ltd") is None  # no column
    assert _channel_price({}, "Harvey Norman") is None
    assert _channel_price(NZ_PRICES, "") is None


if __name__ == "__main__":
    test_tolerant_channel_match()
    print("All channel-match tests passed.")
