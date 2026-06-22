"""Promo credit-claim calculation engine.

Ported from AU_Promo Form_TEMPLATE.xlsx (the "Promo Form" sheet). Pure functions, no I/O.
Verified against the ANKER A1902T11 / Officeworks example in the template — see tests.

Per-line model (all amounts ex-GST in AUD unless noted):

    net_buy          = retailer_buy_ex * (1 - rebate)
    rec_sale_inc     = rrp_inc * (1 - pct_off)
    std_margin       = (rrp_inc/1.1 - net_buy) / (rrp_inc/1.1)

Support can be driven two ways (support_basis):

  "pct_off" (default) — discount-driven, as in the standard template:
    total_support/u  = net_buy * pct_off
    supplier_support = total_support/u * ratio_supplier
    mg_support       = total_support/u * ratio_mg
    total_support    = supplier_support + mg_support          # retailer's own share excluded

  "margin" — margin-driven (back-solve support to hit a target promo margin):
    total_support    = net_buy - (1 - target_margin) * rec_sale_inc/1.1
    supplier_support = total_support * ratio_supplier / (ratio_supplier + ratio_mg)
    mg_support       = total_support * ratio_mg       / (ratio_supplier + ratio_mg)
    (% off still sets the promo sale price; promo_margin then equals target_margin)

Both modes then:
    promo_margin     = (rec_sale_inc/1.1 + total_support - net_buy) / (rec_sale_inc/1.1)
    expected_sales   = ceil(avg_6wk * (1 + growth)) * weeks
    supplier_claim   = expected_sales * supplier_support
    mg_claim         = expected_sales * mg_support
"""
import math
from dataclasses import dataclass
from datetime import date

GST = 1.1  # AU GST gross-up divisor


def weeks_between(start: date, end: date) -> float:
    """Promo length in weeks, matching the template's (end - start + 1) / 7."""
    return ((end - start).days + 1) / 7


@dataclass
class LineInputs:
    retailer_buy_ex: float          # what the retailer pays MacGear, ex GST  (col G)
    rebate: float                   # retailer rebate fraction                 (F$2)
    pct_off: float                  # recommended % off / promo depth          (CU)
    ratio_supplier: float           # brand's funding share                    (F$61)
    ratio_mg: float                 # MacGear's funding share                  (F$60)
    rrp_inc: float | None = None    # base RRP inc GST                         (CS)
    ratio_retailer: float = 0.0     # retailer's funding share (informational) (F$59)
    avg_6wk: float | None = None    # customer 6-week avg unit sales           (N)
    growth: float = 0.0             # growth expectation fraction              (O$2)
    actual_sales: float | None = None  # qty actually sold / being claimed
    support_basis: str = "pct_off"  # "pct_off" (discount-driven) or "margin"
    target_margin: float | None = None  # target promo margin fraction (margin mode)


@dataclass
class LineResult:
    net_buy: float
    rec_sale_inc: float | None
    total_support_unit: float
    supplier_support: float
    mg_support: float
    total_support: float
    std_margin: float | None
    promo_margin: float | None
    expected_sales: float | None
    supplier_claim: float | None
    mg_claim: float | None
    # actuals (based on actual_sales qty rather than expected_sales)
    actual_supplier_claim: float | None
    actual_mg_claim: float | None


def compute_line(i: LineInputs, weeks: float) -> LineResult:
    net_buy = i.retailer_buy_ex * (1 - i.rebate)
    rec_sale_inc = i.rrp_inc * (1 - i.pct_off) if i.rrp_inc else None

    if i.support_basis == "margin" and rec_sale_inc and i.target_margin is not None:
        # margin-driven: back-solve total support to hit the target promo margin,
        # then split it across supplier/MG by their ratios. (% off still sets the
        # promo sale price above; the retailer share isn't part of this total.)
        total_support = net_buy - (1 - i.target_margin) * rec_sale_inc / GST
        denom = i.ratio_supplier + i.ratio_mg
        supplier_support = total_support * i.ratio_supplier / denom if denom else 0.0
        mg_support = total_support * i.ratio_mg / denom if denom else 0.0
        total_support = supplier_support + mg_support
        total_support_unit = total_support
    else:
        # discount-driven (standard template): support = net buy x % off x ratio
        total_support_unit = net_buy * i.pct_off
        supplier_support = total_support_unit * i.ratio_supplier
        mg_support = total_support_unit * i.ratio_mg
        total_support = supplier_support + mg_support

    std_margin = None
    if i.rrp_inc:
        base = i.rrp_inc / GST
        std_margin = (base - net_buy) / base if base else None

    promo_margin = None
    if rec_sale_inc:
        base = rec_sale_inc / GST
        promo_margin = (base + total_support - net_buy) / base if base else None

    expected_sales = None
    if i.avg_6wk:
        units = math.ceil(i.avg_6wk * (1 + i.growth))
        expected_sales = units * weeks if units else None

    supplier_claim = expected_sales * supplier_support if expected_sales else None
    mg_claim = expected_sales * mg_support if expected_sales else None

    actual_supplier_claim = i.actual_sales * supplier_support if i.actual_sales else None
    actual_mg_claim = i.actual_sales * mg_support if i.actual_sales else None

    return LineResult(
        net_buy=net_buy,
        rec_sale_inc=rec_sale_inc,
        total_support_unit=total_support_unit,
        supplier_support=supplier_support,
        mg_support=mg_support,
        total_support=total_support,
        std_margin=std_margin,
        promo_margin=promo_margin,
        expected_sales=expected_sales,
        supplier_claim=supplier_claim,
        mg_claim=mg_claim,
        actual_supplier_claim=actual_supplier_claim,
        actual_mg_claim=actual_mg_claim,
    )
