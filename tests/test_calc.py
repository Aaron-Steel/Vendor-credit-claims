"""Verify the calc engine reproduces the template's numbers.

Reference: ANKER A1902T11 / Officeworks line in AU_Promo Form_TEMPLATE.xlsx
  G5 retailer_buy_ex = 84.98, F2 rebate = 0.135, CU5 pct_off = 0.20,
  CS5 rrp_inc = 169.95, funding ratios 0.333 / 0.333 / 0.333.
Expected (from the workbook's evaluated cells):
  H5 supplier_support = 4.895612820000001
  I5 mg_support       = 4.895612820000001
  K5 std_margin       = 0.5242220064724918
  L5 promo_margin     = 0.4844945440129448
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.calc import LineInputs, compute_line, weeks_between


def test_anker_officeworks_line():
    i = LineInputs(
        retailer_buy_ex=84.98, rebate=0.135, pct_off=0.20,
        ratio_supplier=0.333, ratio_mg=0.333, ratio_retailer=0.333,
        rrp_inc=169.95,
    )
    weeks = weeks_between(date(2025, 6, 1), date(2025, 6, 14))
    r = compute_line(i, weeks)
    assert weeks == 2
    assert abs(r.supplier_support - 4.895612820000001) < 1e-9
    assert abs(r.mg_support - 4.895612820000001) < 1e-9
    assert abs(r.total_support - 9.791225640000002) < 1e-9
    assert abs(r.std_margin - 0.5242220064724918) < 1e-9
    assert abs(r.promo_margin - 0.4844945440129448) < 1e-9
    assert abs(r.rec_sale_inc - 135.96) < 1e-9


def test_expected_sales_and_claims():
    i = LineInputs(
        retailer_buy_ex=84.98, rebate=0.135, pct_off=0.20,
        ratio_supplier=0.333, ratio_mg=0.333, ratio_retailer=0.333,
        rrp_inc=169.95, avg_6wk=10, growth=0.2,
    )
    r = compute_line(i, weeks=2)
    # ceil(10 * 1.2) = 12 units/wk * 2 wks = 24
    assert r.expected_sales == 24
    assert abs(r.supplier_claim - 24 * 4.895612820000001) < 1e-9
    assert abs(r.mg_claim - 24 * 4.895612820000001) < 1e-9


if __name__ == "__main__":
    test_anker_officeworks_line()
    test_expected_sales_and_claims()
    print("All calc tests passed.")
