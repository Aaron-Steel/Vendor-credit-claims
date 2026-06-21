# Vendor Credit Claims

A web app to manage promotional credit claims end-to-end — create promos, track inbound
**customer claims**, and raise outbound **vendor credit requests** — replacing the
Monday.com + per-promo Excel workflow. See [SPEC.md](SPEC.md) for the full domain model.

## What it does (Phase 1)

- **Create a promotion** — brand, dates, AUD→USD rate, a default 3-way funding split
  (Retailer / MacGear / Brand), and the retailers running it (rebate pre-filled per retailer).
- **Add line items** per retailer by SKU code — description, RRP and channel buy-price
  auto-fill from the imported product master. The calc engine (ported 1:1 from the Excel
  template and unit-tested against it) computes supplier/MG support, margins, expected
  sales, and both claim amounts.
- **Three views** of every promo — *Internal* (everything), *Sales/Customer* (hides the
  funding split), *Vendor* (supplier support + claim only) — each exportable to Excel.
- **Lifecycle tracking** — per-customer claim status (Not Received → Received → Verified →
  Credited) with variance vs the expected claim, and a vendor request (Not Sent → Sent →
  Approved → Credited) with AUD/USD amounts. Dashboard shows all promos at a glance.

## Run it

```powershell
# from the project folder:
./run.ps1
```

That creates the virtualenv + seeds the database on first run, then serves the app at
**http://127.0.0.1:8000**. Stop with Ctrl+C.

Manual equivalent:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\extract_seed.py   # template -> data/seed_*.json
.\.venv\Scripts\python.exe -m app.seed               # create + seed data/app.db
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Refreshing reference data

Product master and retailer rebates are seeded from `AU_Promo Form_TEMPLATE.xlsx`
(Master Price Level + Data Validation sheets). When that file changes, re-run:

```powershell
.\.venv\Scripts\python.exe scripts\extract_seed.py
.\.venv\Scripts\python.exe -m app.seed   # idempotent: updates existing, adds new
```

## Layout

```
app/
  calc.py        calculation engine (pure, unit-tested vs the template)
  service.py     resolves overrides + rolls totals up to retailer/promo level
  models.py      SQLAlchemy models
  db.py          SQLite engine/session
  seed.py        create tables + load reference data
  export.py      Excel export (internal / sales / vendor)
  main.py        FastAPI routes
  templates/     Jinja pages
  static/        CSS
scripts/extract_seed.py   one-off template -> JSON extractor
tests/test_calc.py        verifies calc matches the template numbers
data/                     seed JSON + app.db (db is gitignored)
```

## Conventions

- Rebates, funding ratios and growth are stored as **fractions** (0.20 = 20%).
- Per-line "% off" is entered as a **percentage** in the UI and stored as a fraction.
- All money is **AUD ex-GST** unless labelled USD. GST factor is 1.1.

## Not yet built (future phases)

- Auth + multi-user hosting (currently single-user, local).
- Email vendor/sales copies via the Microsoft Graph app registration.
- Live product-master sync from NetSuite (currently imported from the template).
- Editing existing line items in place (currently add/delete).
```
