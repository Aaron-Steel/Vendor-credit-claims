"""Validate the NetSuite pricing-sync mapping against real saved-search row shapes.

Rows below mirror the actual output of customsearch1084 / customsearch1413
(column labels keyed exactly as NetSuite returns them).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Product
from app.pricing_sync import rows_to_products, sync_pricing, _to_float, MIN_ROWS_TO_PRUNE

# real-shaped AU rows (channel columns abbreviated but representative)
AU_ROWS = [
    {"Brand": "ADONIT", "Code": "ADM4DG", "Description": "ADONIT Mini 4 (Grey)",
     "AU Status": "1", "Base (RRP Inc)": "39.99",
     "JB HIFI": "22.50", "Harvey Norman": "23.10", "AU - Officeworks": "",
     "NZ AU - RRP - Home Of Brands": "39.99"},
    {"Brand": "", "Code": "KNAAPBCN_SAMPLE", "Description": "KNAAP BCN Fatbike (Black)",
     "AU Status": "3", "Base (RRP Inc)": "169.99", "JB HIFI": "", "Harvey Norman": ""},
    # duplicate code should be ignored
    {"Brand": "ADONIT", "Code": "ADM4DG", "Description": "dupe", "Base (RRP Inc)": "1.00"},
]


def test_to_float():
    assert _to_float("39.99") == 39.99
    assert _to_float("1,234.50") == 1234.50
    assert _to_float("") is None
    assert _to_float(None) is None
    assert _to_float("n/a") is None
    assert _to_float(12) == 12.0


def test_au_mapping():
    prods = rows_to_products(AU_ROWS, "AU")
    assert len(prods) == 2                       # dupe ADM4DG dropped
    p = prods[0]
    assert p["code"] == "ADM4DG" and p["country"] == "AU"
    assert p["brand"] == "ADONIT"
    assert p["status"] == "1"                    # from "AU Status"
    assert p["rrp_inc"] == 39.99
    # blank channels skipped; numeric channels kept; non-channel cols excluded
    assert p["channel_prices"] == {"JB HIFI": 22.50, "Harvey Norman": 23.10,
                                   "NZ AU - RRP - Home Of Brands": 39.99}
    assert "Base (RRP Inc)" not in p["channel_prices"]
    assert "Description" not in p["channel_prices"]


def test_nz_uses_nz_status_key():
    rows = [{"Code": "X1", "Description": "d", "Brand": "B",
             "NZ Status": "2", "Base (RRP Inc)": "10", "Noel Leeming": "6.50"}]
    p = rows_to_products(rows, "NZ")[0]
    assert p["country"] == "NZ"
    assert p["status"] == "2"                    # from "NZ Status"
    assert p["channel_prices"] == {"Noel Leeming": 6.50}


def test_blank_code_skipped():
    rows = [{"Code": "", "Base (RRP Inc)": "5"}, {"Code": "  ", "Base (RRP Inc)": "6"}]
    assert rows_to_products(rows, "AU") == []


def _fresh_db():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def test_sync_prunes_discontinued_with_guard():
    db = _fresh_db()
    # seed AU: A,B,C  and an NZ product that must never be touched
    for c in ("A", "B", "C"):
        db.add(Product(code=c, country="AU", description="d", brand="", status="",
                       rrp_inc=1.0, channel_prices={}))
    db.add(Product(code="NZ1", country="NZ", description="d", brand="", status="",
                   rrp_inc=1.0, channel_prices={}))
    db.commit()

    # small feed (A updated, B, new D; C discontinued) -> below guard, so NO pruning
    small = [{"Code": "A", "Base (RRP Inc)": "2"}, {"Code": "B", "Base (RRP Inc)": "2"},
             {"Code": "D", "Base (RRP Inc)": "2"}]
    res = sync_pricing(db, "AU", small)
    assert res["prune_skipped"] is True and res["pruned"] == 0
    au_codes = set(db.scalars(select(Product.code).where(Product.country == "AU")).all())
    assert au_codes == {"A", "B", "C", "D"}        # C kept (guard), D added

    # full feed (>= guard) omitting C -> C pruned; NZ untouched
    big = [{"Code": "A", "Base (RRP Inc)": "3"}, {"Code": "B", "Base (RRP Inc)": "3"},
           {"Code": "D", "Base (RRP Inc)": "3"}]
    big += [{"Code": f"BULK{i}", "Base (RRP Inc)": "1"} for i in range(MIN_ROWS_TO_PRUNE)]
    res = sync_pricing(db, "AU", big)
    assert res["prune_skipped"] is False
    assert res["pruned"] == 1                       # only C removed
    au_codes = set(db.scalars(select(Product.code).where(Product.country == "AU")).all())
    assert "C" not in au_codes and {"A", "B", "D"} <= au_codes
    assert db.scalar(select(Product).where(Product.country == "NZ")) is not None  # NZ safe
    db.close()


if __name__ == "__main__":
    test_to_float()
    test_au_mapping()
    test_nz_uses_nz_status_key()
    test_blank_code_skipped()
    test_sync_prunes_discontinued_with_guard()
    print("All pricing-sync tests passed.")
