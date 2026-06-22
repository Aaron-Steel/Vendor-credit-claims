"""Aggregation layer: turn stored inputs into computed line/retailer/promo results.

Resolves per-line funding/growth overrides against the promotion defaults, runs the
calc engine, and rolls totals up to retailer and promotion level. Computed values are
never stored — always derived here so they stay correct when inputs change.
"""
from dataclasses import dataclass

from .calc import LineInputs, LineResult, compute_line, weeks_between
from .models import LineItem, PromoRetailer, Promotion


@dataclass
class LineView:
    line: LineItem
    result: LineResult


@dataclass
class RetailerView:
    pr: PromoRetailer
    lines: list[LineView]
    supplier_total: float
    mg_total: float
    total_support_total: float       # expected customer claim (supplier + mg)
    claim_variance: float | None     # amount claimed - expected, if claimed
    # actuals (based on actual sales qty entered per line)
    actual_supplier_total: float
    actual_mg_total: float
    actual_support_total: float      # actual customer claim (supplier + mg)
    has_actuals: bool                # any line has an actual_sales value
    actual_variance: float | None    # amount claimed - actual, if claimed


@dataclass
class PromoView:
    promo: Promotion
    weeks: float
    retailers: list[RetailerView]
    supplier_total_aud: float         # -> vendor request (expected)
    mg_total_aud: float               # MacGear absorbs (expected)
    customer_expected_aud: float      # total expected back from customers
    supplier_total_usd: float
    # actuals (based on actual sales qty)
    actual_supplier_aud: float
    actual_mg_aud: float
    actual_customer_aud: float
    actual_supplier_usd: float
    has_actuals: bool


def _line_inputs(line: LineItem, pr: PromoRetailer, promo: Promotion) -> LineInputs:
    return LineInputs(
        retailer_buy_ex=line.retailer_buy_ex or 0.0,
        rebate=pr.rebate or 0.0,
        pct_off=line.pct_off or 0.0,
        ratio_supplier=line.ratio_supplier if line.ratio_supplier is not None else promo.ratio_supplier,
        ratio_mg=line.ratio_mg if line.ratio_mg is not None else promo.ratio_mg,
        ratio_retailer=line.ratio_retailer if line.ratio_retailer is not None else promo.ratio_retailer,
        rrp_inc=line.rrp_inc,
        avg_6wk=line.avg_6wk,
        growth=line.growth if line.growth is not None else promo.growth_default,
        actual_sales=line.actual_sales,
        support_basis=line.support_basis or "pct_off",
        target_margin=line.target_margin,
        cogs_supplier_pct=line.cogs_supplier_pct,
        cogs_mg_pct=line.cogs_mg_pct,
    )


def build_promo_view(promo: Promotion) -> PromoView:
    weeks = weeks_between(promo.start_date, promo.end_date)
    retailer_views: list[RetailerView] = []
    supplier_aud = mg_aud = cust_expected = 0.0
    a_supplier_aud = a_mg_aud = a_cust_aud = 0.0
    promo_has_actuals = False

    for pr in promo.retailers:
        line_views: list[LineView] = []
        r_supplier = r_mg = r_support = 0.0
        a_supplier = a_mg = a_support = 0.0
        has_actuals = False
        for line in pr.lines:
            res = compute_line(_line_inputs(line, pr, promo), weeks)
            line_views.append(LineView(line=line, result=res))
            r_supplier += res.supplier_claim or 0.0
            r_mg += res.mg_claim or 0.0
            r_support += (res.supplier_claim or 0.0) + (res.mg_claim or 0.0)
            if line.actual_sales is not None:
                has_actuals = True
            a_supplier += res.actual_supplier_claim or 0.0
            a_mg += res.actual_mg_claim or 0.0
            a_support += (res.actual_supplier_claim or 0.0) + (res.actual_mg_claim or 0.0)

        expected = r_supplier + r_mg
        claimed = pr.customer_claim.amount_claimed if pr.customer_claim else None
        variance = (claimed - expected) if claimed is not None else None
        actual_variance = (claimed - a_support) if (claimed is not None and has_actuals) else None

        retailer_views.append(RetailerView(
            pr=pr, lines=line_views,
            supplier_total=r_supplier, mg_total=r_mg,
            total_support_total=r_support, claim_variance=variance,
            actual_supplier_total=a_supplier, actual_mg_total=a_mg,
            actual_support_total=a_support, has_actuals=has_actuals,
            actual_variance=actual_variance))

        supplier_aud += r_supplier
        mg_aud += r_mg
        cust_expected += expected
        a_supplier_aud += a_supplier
        a_mg_aud += a_mg
        a_cust_aud += a_support
        promo_has_actuals = promo_has_actuals or has_actuals

    rate = promo.aud_usd_rate or 0.0
    return PromoView(
        promo=promo, weeks=weeks, retailers=retailer_views,
        supplier_total_aud=supplier_aud, mg_total_aud=mg_aud,
        customer_expected_aud=cust_expected,
        supplier_total_usd=supplier_aud * rate,
        actual_supplier_aud=a_supplier_aud, actual_mg_aud=a_mg_aud,
        actual_customer_aud=a_cust_aud, actual_supplier_usd=a_supplier_aud * rate,
        has_actuals=promo_has_actuals,
    )
