"""One-off: extract seed data (retailers + product master) from the promo template.

Reads AU_Promo Form_TEMPLATE.xlsx and writes:
  data/seed_retailers.json  - retailer name + default rebate %
  data/seed_products.json   - product master (code, description, brand, status, rrp_inc, channel prices)

Re-run whenever the template's Master Price Level / Data Validation sheets are updated.
"""
import json
import os
import warnings

import openpyxl

warnings.simplefilter("ignore")  # silence the data-validation extension warning

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEMPLATE = os.path.join(ROOT, "AU_Promo Form_TEMPLATE.xlsx")
DATA_DIR = os.path.join(ROOT, "data")


def extract_retailers(wb):
    ws = wb["Data Validation"]
    retailers = []
    for r in range(3, ws.max_row + 1):
        name = ws.cell(r, 1).value
        if not name:
            continue
        rebate = ws.cell(r, 2).value
        retailers.append({"name": str(name).strip(),
                          "rebate": float(rebate) if isinstance(rebate, (int, float)) else 0.0})
    return retailers


def extract_products(wb):
    ws = wb["Master Price Level"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    # map header name -> column index (1-based)
    col = {h: i + 1 for i, h in enumerate(headers) if h}
    channel_headers = [h for h in headers
                       if h not in (None, "Source.Name", "Brand", "Code",
                                    "Description", "AU Status", "Base (RRP Inc)")]
    products = []
    seen = set()
    for r in range(2, ws.max_row + 1):
        code = ws.cell(r, col["Code"]).value
        if not code:
            continue
        code = str(code).strip()
        if code in seen:
            continue
        seen.add(code)
        rrp = ws.cell(r, col["Base (RRP Inc)"]).value
        prices = {}
        for h in channel_headers:
            v = ws.cell(r, col[h]).value
            if isinstance(v, (int, float)):
                prices[h] = float(v)
        products.append({
            "code": code,
            "description": (ws.cell(r, col["Description"]).value or "").strip()
                           if ws.cell(r, col["Description"]).value else "",
            "brand": (ws.cell(r, col["Brand"]).value or "").strip()
                     if ws.cell(r, col["Brand"]).value else "",
            "status": (ws.cell(r, col["AU Status"]).value or "").strip()
                      if ws.cell(r, col["AU Status"]).value else "",
            "rrp_inc": float(rrp) if isinstance(rrp, (int, float)) else None,
            "channel_prices": prices,
        })
    return products


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    wb = openpyxl.load_workbook(TEMPLATE, data_only=True)
    retailers = extract_retailers(wb)
    products = extract_products(wb)
    with open(os.path.join(DATA_DIR, "seed_retailers.json"), "w", encoding="utf-8") as f:
        json.dump(retailers, f, indent=2, ensure_ascii=False)
    with open(os.path.join(DATA_DIR, "seed_products.json"), "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(retailers)} retailers and {len(products)} products to {DATA_DIR}")


if __name__ == "__main__":
    main()
