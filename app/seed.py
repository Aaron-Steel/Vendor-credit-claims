"""Create tables and load reference data (products + retailers) from data/seed_*.json.

Idempotent: safe to re-run. Updates existing products/retailers by key, inserts new ones.
Run:  python -m app.seed
"""
import json
import os

from .db import Base, DATA_DIR, SessionLocal, engine, rebuild_reference_tables
from .models import Product, Retailer


def load_json(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        print(f"  (skipped {name} - not found; run scripts/extract_seed.py first)")
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def seed():
    rebuild_reference_tables()   # drop legacy (pre-country) products/retailers if present
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        retailers = load_json("seed_retailers.json")
        existing_r = {(r.name, r.country): r for r in db.query(Retailer).all()}
        for row in retailers:
            country = row.get("country", "AU")
            r = existing_r.get((row["name"], country))
            if r:
                r.default_rebate = row["rebate"]
            else:
                db.add(Retailer(name=row["name"], country=country,
                                default_rebate=row["rebate"]))

        products = load_json("seed_products.json")
        existing_p = {(p.code, p.country): p for p in db.query(Product).all()}
        for row in products:
            country = row.get("country", "AU")
            p = existing_p.get((row["code"], country))
            if p:
                p.description = row["description"]
                p.brand = row["brand"]
                p.status = row["status"]
                p.rrp_inc = row["rrp_inc"]
                p.channel_prices = row["channel_prices"]
            else:
                db.add(Product(
                    code=row["code"], country=country, description=row["description"],
                    brand=row["brand"], status=row["status"],
                    rrp_inc=row["rrp_inc"], channel_prices=row["channel_prices"]))
        db.commit()
        print(f"Seeded {db.query(Retailer).count()} retailers, "
              f"{db.query(Product).count()} products.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
