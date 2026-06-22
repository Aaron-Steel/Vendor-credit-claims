"""Database engine + session setup (SQLite, file-based)."""
import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "app.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)


class Base(DeclarativeBase):
    pass


# Lightweight additive migrations: column name -> SQL type, added if missing.
# (Avoids a full migration framework for this small single-file SQLite app.)
_ADDED_COLUMNS = {
    "line_items": {"actual_sales": "FLOAT",
                   "support_basis": "VARCHAR",
                   "target_margin": "FLOAT"},
}


def ensure_schema():
    """Add any newly-introduced columns to existing tables (idempotent)."""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, cols in _ADDED_COLUMNS.items():
            if table not in tables:
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for col, coltype in cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))


# One-time remap of legacy status values to the new workflow taxonomy.
_STATUS_REMAP = {
    "promotions": {"Sent": "Sent to Customer", "Live": "Running"},
    "customer_claims": {"Not Received": "Awaiting Claim", "Received": "Received by Sales",
                        "Verified": "Verified by Accounts"},
    "vendor_requests": {"Sent": "Sent to Vendor", "Approved": "Vendor Approved",
                        "Credited": "Credit Received"},
}


def migrate_statuses():
    """Map any old status strings to the current ones (idempotent)."""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, mapping in _STATUS_REMAP.items():
            if table not in tables:
                continue
            for old, new in mapping.items():
                conn.execute(text(f"UPDATE {table} SET status = :new WHERE status = :old"),
                             {"new": new, "old": old})


def get_db():
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
