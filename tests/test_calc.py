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


def test_margin_basis_back_solves_support():
    """MOVA Z60 / JB Hi-Fi from a real April promo built the margin-driven way:
    buy 1799.40, rebate 9%, RRP ~2998.99, % off ~23.34%, target promo margin 35%,
    brand funds 100% (supplier ratio 1, MG 0). Total support should be ~278.95."""
    i = LineInputs(
        retailer_buy_ex=1799.40, rebate=0.09, pct_off=0.23341,
        ratio_supplier=1.0, ratio_mg=0.0, ratio_retailer=0.0,
        rrp_inc=2998.99, support_basis="margin", target_margin=0.35,
    )
    r = compute_line(i, weeks=2)
    assert abs(r.total_support - 278.95) < 0.1       # supplier + MG
    assert abs(r.supplier_support - 278.95) < 0.1    # brand funds 100%
    assert abs(r.mg_support - 0.0) < 1e-9
    # by construction the resulting promo margin equals the target
    assert abs(r.promo_margin - 0.35) < 1e-6


def test_margin_basis_falls_back_without_target():
    """No target margin set -> behaves like the default % off method."""
    base = dict(retailer_buy_ex=84.98, rebate=0.135, pct_off=0.20,
                ratio_supplier=0.333, ratio_mg=0.333, ratio_retailer=0.333, rrp_inc=169.95)
    pct = compute_line(LineInputs(**base), weeks=2)
    margin_no_target = compute_line(LineInputs(support_basis="margin", **base), weeks=2)
    assert abs(pct.total_support - margin_no_target.total_support) < 1e-12


def test_cogs_basis_pct_off_cost():
    """Withings %OFFCOGS sample. JB Hi-Fi: supplier support = buy ex x 17.5%, MG 0
    (H5 = G5*17.5%). Harvey Norman same SKU: supplier 12.5% + MG 8% of buy ex.
    Rebate is NOT applied to the support (it's % of gross buy ex)."""
    # JB Hi-Fi style: supplier only (ratios unused in cogs mode)
    jb = compute_line(LineInputs(
        retailer_buy_ex=100.0, rebate=0.19, pct_off=0.10, rrp_inc=200.0,
        ratio_supplier=0.0, ratio_mg=0.0,
        support_basis="cogs", cogs_supplier_pct=0.175, cogs_mg_pct=0.0), weeks=2)
    assert abs(jb.supplier_support - 17.5) < 1e-9   # 100 * 17.5%, rebate ignored
    assert abs(jb.mg_support - 0.0) < 1e-9
    assert abs(jb.total_support - 17.5) < 1e-9
    # Harvey Norman style: supplier + MG
    hn = compute_line(LineInputs(
        retailer_buy_ex=100.0, rebate=0.17, pct_off=0.10, rrp_inc=200.0,
        ratio_supplier=0.0, ratio_mg=0.0,
        support_basis="cogs", cogs_supplier_pct=0.125, cogs_mg_pct=0.08), weeks=2)
    assert abs(hn.supplier_support - 12.5) < 1e-9
    assert abs(hn.mg_support - 8.0) < 1e-9
    assert abs(hn.total_support - 20.5) < 1e-9


if __name__ == "__main__":
    test_anker_officeworks_line()
    test_expected_sales_and_claims()
    test_margin_basis_back_solves_support()
    test_margin_basis_falls_back_without_target()
    test_cogs_basis_pct_off_cost()
    print("All calc tests passed.")
