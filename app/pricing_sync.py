"""Sync product/customer pricing from NetSuite saved searches into the app DB.

The NetSuite saved searches "Master Price Levels_AU" (customsearch1084) and
"Master Price Levels_NZ" (customsearch1413) return one row per SKU, with columns:
  Code, Description, Brand, AU Status / NZ Status, Base (RRP Inc),
  then one column per retailer/channel (its price level).
This is the same shape as the Excel master sheets, so rows map straight to products.

Flow:  n8n (daily) -> NetSuite RESTlet runs the search -> POST rows to
        /admin/sync-pricing -> sync_pricing() maps + upserts here.
"""
from sqlalchemy import select

from .models import Product
from .seed import upsert_products

# Columns that are NOT a retailer channel price (mirrors scripts/extract_seed.py).
NON_CHANNEL = {"Source.Name", "Brand", "Code", "Description",
               "AU Status", "NZ Status", "Base (RRP Inc)", "RRP ex GST"}

# Safety guard: never prune discontinued products from a feed this small (protects the
# catalog against a broken/empty NetSuite response). Real masters are 1700+ rows.
MIN_ROWS_TO_PRUNE = 50


def _to_float(v):
    """Parse a saved-search cell to float; blanks/non-numeric -> None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def rows_to_products(rows, country):
    """Map NetSuite saved-search rows (list of dicts keyed by column label) to
    product dicts for the given country. De-dupes by code (keeps the first)."""
    country = (country or "AU").upper()
    status_key = "NZ Status" if country == "NZ" else "AU Status"
    products, seen = [], set()
    for row in rows:
        code = (row.get("Code") or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        prices = {}
        for key, val in row.items():
            if key in NON_CHANNEL:
                continue
            fv = _to_float(val)
            if fv is not None:
                prices[key] = fv
        products.append({
            "code": code,
            "country": country,
            "description": (row.get("Description") or "").strip(),
            "brand": (row.get("Brand") or "").strip(),
            "status": str(row.get(status_key) or "").strip(),
            "rrp_inc": _to_float(row.get("Base (RRP Inc)")),
            "channel_prices": prices,
        })
    return products


def sync_pricing(db, country, rows, prune=True):
    """Make the country's catalog match the NetSuite feed: upsert every row, then
    (optionally) prune discontinued products — those in the DB for this country but no
    longer in the feed. Pruning is skipped if the feed is suspiciously small. Commits.
    Returns a summary dict."""
    country = (country or "AU").upper()
    products = rows_to_products(rows, country)
    inserted, updated = upsert_products(db, products)

    pruned = 0
    prune_skipped = prune and len(products) < MIN_ROWS_TO_PRUNE
    if prune and not prune_skipped:
        feed_codes = {p["code"] for p in products}
        existing = db.scalars(select(Product).where(Product.country == country)).all()
        for p in existing:
            if p.code not in feed_codes:
                db.delete(p)
                pruned += 1
    db.commit()
    return {"country": country, "received": len(rows), "products": len(products),
            "inserted": inserted, "updated": updated, "pruned": pruned,
            "prune_skipped": prune_skipped}
