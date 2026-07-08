"""
============================================================================
WEEK 3 - DATABASE LOADER  (CSV -> PostgreSQL)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SCRIPT DOES
---------------------
  Loads the CLEANED Week 1 data and the SIMULATED Week 2 data from CSV files
  into the PostgreSQL tables created by database/init_db.py.

WHERE THE DATA COMES FROM
-------------------------
  processed/ (Week 1, REAL):  customers_clean, products_clean, orders_clean
  simulation/ (Week 2):       warehouses, inventory, vehicles,
                              delivery_routes, disruptions

  We NEVER load raw files from data/ - only cleaned/simulated files.

LOADING ORDER (respects foreign keys: parents before children)
---------------------------------------------------------------
  customers -> sellers -> products -> orders -> warehouses -> inventory
  -> vehicles -> delivery_routes -> disruptions
  (sellers load before warehouses because warehouse.seller_id -> sellers.)

KEY SAFEGUARDS
--------------
  - Prints the CSV row count BEFORE loading and the DB row count AFTER.
  - Validates the after-count matches the number of unique primary keys.
  - Handles duplicate primary keys gracefully: uses INSERT ... ON CONFLICT
    DO NOTHING, so re-running the script does not crash or double-load.
  - Checks foreign keys before loading children and reports any "orphan"
    rows (rows pointing at a parent that is not present) instead of failing
    silently.
  - If a CSV file is missing, prints a clear message and skips it.
  - We do NOT fake success: counts and orphans are reported honestly.

HOW TO RUN (from the project root)
----------------------------------
    python database/init_db.py          # create the tables first
    python notebooks/week3_load_database.py
============================================================================
"""

import os
import sys

import numpy as np
import pandas as pd

# Make the project root importable when run as `python notebooks/week3_load_database.py`.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

import models  # registers all tables
from database.connection import Base, SessionLocal, engine, test_connection
from models import (
    Customer,
    DeliveryRoute,
    Disruption,
    Inventory,
    Order,
    Product,
    Seller,
    Vehicle,
    Warehouse,
)

PROCESSED_DIR = os.path.join(PROJECT_ROOT, "processed")
SIM_DIR = os.path.join(PROJECT_ROOT, "simulation")

# Insert in batches so large tables (customers has ~99k rows) stay memory-light.
BATCH_SIZE = 2000


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def banner(title):
    print("\n" + "=" * 74)
    print(title)
    print("=" * 74)


def prepare_dataframe(df, int_cols=(), float_cols=(), datetime_cols=(), date_cols=()):
    """
    Convert a raw CSV DataFrame into clean Python values ready for the database:
      - parse datetime / date columns (unparseable -> NaT),
      - coerce integer columns (keeping NULLs as None, not 0),
      - turn every remaining NaN/NaT into None (so they become SQL NULL).
    """
    df = df.copy()

    for col in datetime_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    for col in date_cols:
        if col in df.columns:
            # date columns (e.g. last_restock_date) are written DD-MM-YYYY by
            # the Week 2 scripts, so dayfirst=True makes that explicit.
            df[col] = pd.to_datetime(
                df[col], errors="coerce", dayfirst=True
            ).dt.date

    for col in int_cols:
        if col in df.columns:
            # 'Int64' is pandas' NULLABLE integer type (keeps missing as <NA>).
            df[col] = df[col].astype("float").round().astype("Int64")

    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].astype("float")

    # Replace every missing value (NaN, NaT, pandas <NA>) with Python None.
    df = df.astype(object).where(pd.notnull(df), None)
    return df


def to_records(df):
    """Turn a prepared DataFrame into a list of dict rows for SQLAlchemy."""
    records = df.to_dict("records")
    # pandas can leave numpy scalar types around; convert to plain Python.
    cleaned = []
    for row in records:
        clean = {}
        for k, v in row.items():
            if v is None:
                clean[k] = None
            elif isinstance(v, (np.integer,)):
                clean[k] = int(v)
            elif isinstance(v, (np.floating,)):
                clean[k] = float(v)
            elif isinstance(v, np.bool_):
                clean[k] = bool(v)
            else:
                clean[k] = v
        cleaned.append(clean)
    return cleaned


def check_orphans(records, fk_field, valid_keys):
    """
    Return how many rows reference a parent key that is NOT present.
    NULL foreign keys (e.g. area-wide disruptions) are allowed and ignored.
    """
    orphans = 0
    for r in records:
        key = r.get(fk_field)
        if key is not None and key not in valid_keys:
            orphans += 1
    return orphans


def db_count(db, model):
    """Count rows currently in a table."""
    return db.scalar(select(func.count()).select_from(model))


def load_table(db, label, file_path, model, pk_col, prepare_kwargs=None,
               fk_checks=None):
    """
    Generic loader for one CSV -> one table.
      label        : human name for printing.
      file_path    : the CSV to read.
      model        : the SQLAlchemy model class.
      pk_col       : primary-key column name (for de-dup + validation).
      prepare_kwargs: dict passed to prepare_dataframe (int/float/date cols).
      fk_checks    : list of (fk_field, set_of_valid_parent_keys) to report orphans.
    """
    banner(f"LOADING: {label}  ->  table '{model.__tablename__}'")

    if not os.path.exists(file_path):
        print(f"  MISSING FILE: {file_path}")
        print("  Skipping this table. Re-run the Week 1/Week 2 scripts to create it.")
        return

    df = pd.read_csv(file_path)
    csv_rows = len(df)
    unique_pks = df[pk_col].nunique()
    print(f"  CSV rows (before loading): {csv_rows:,}")
    if unique_pks != csv_rows:
        print(f"  Note: {csv_rows - unique_pks} duplicate '{pk_col}' values in the CSV "
              f"(will be de-duplicated on load).")

    df = prepare_dataframe(df, **(prepare_kwargs or {}))
    records = to_records(df)

    # Foreign-key sanity check (report, do not silently drop).
    if fk_checks:
        for fk_field, valid_keys in fk_checks:
            orphans = check_orphans(records, fk_field, valid_keys)
            if orphans:
                print(f"  WARNING: {orphans} rows have a '{fk_field}' with no matching "
                      f"parent. PostgreSQL will reject those (foreign key).")
            else:
                print(f"  FK check '{fk_field}': OK (no orphan rows).")

    # Insert in batches with ON CONFLICT DO NOTHING (idempotent, dup-safe).
    inserted_attempt = 0
    for start in range(0, len(records), BATCH_SIZE):
        chunk = records[start:start + BATCH_SIZE]
        stmt = pg_insert(model.__table__).values(chunk)
        stmt = stmt.on_conflict_do_nothing(index_elements=[pk_col])
        db.execute(stmt)
        inserted_attempt += len(chunk)
    db.commit()

    after = db_count(db, model)
    print(f"  DB rows (after loading):  {after:,}")
    status = "OK" if after == unique_pks else "CHECK"
    print(f"  Validation: unique CSV keys = {unique_pks:,}, table rows = {after:,} -> {status}")


def main():
    banner("WEEK 3 - LOAD CLEANED + SIMULATED CSVs INTO POSTGRESQL")

    # 1) Must be able to connect before doing anything.
    if not test_connection():
        print("\nAborting: start PostgreSQL and create the database, then re-run.")
        print("  createdb supply_chain_optimizer")
        print("  python database/init_db.py")
        sys.exit(1)

    # 2) Make sure tables exist (safe: create_all never drops anything).
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # --- Parents first -------------------------------------------------
        load_table(
            db, "customers (Week 1)", os.path.join(PROCESSED_DIR, "customers_clean.csv"),
            Customer, "customer_id",
            prepare_kwargs={"int_cols": ["customer_zip_code_prefix"]},
        )
        load_table(
            db, "sellers (Week 1)", os.path.join(PROCESSED_DIR, "sellers_clean.csv"),
            Seller, "seller_id",
            prepare_kwargs={"int_cols": ["seller_zip_code_prefix"]},
        )
        load_table(
            db, "products (Week 1)", os.path.join(PROCESSED_DIR, "products_clean.csv"),
            Product, "product_id",
            prepare_kwargs={
                "int_cols": ["product_name_length", "product_description_length",
                             "product_photos_qty"],
                "float_cols": ["product_weight_g", "product_length_cm",
                               "product_height_cm", "product_width_cm"],
            },
        )

        # Gather valid parent keys for FK checks on children.
        customer_keys = set(db.scalars(select(Customer.customer_id)).all())
        seller_keys = set(db.scalars(select(Seller.seller_id)).all())

        load_table(
            db, "orders (Week 1)", os.path.join(PROCESSED_DIR, "orders_clean.csv"),
            Order, "order_id",
            prepare_kwargs={"datetime_cols": [
                "order_purchase_timestamp", "order_approved_at",
                "order_delivered_carrier_date", "order_delivered_customer_date",
                "order_estimated_delivery_date"]},
            fk_checks=[("customer_id", customer_keys)],
        )
        load_table(
            db, "warehouses (Week 2)", os.path.join(SIM_DIR, "warehouses.csv"),
            Warehouse, "warehouse_id",
            prepare_kwargs={
                "int_cols": ["warehouse_zip_code_prefix", "capacity"],
                "float_cols": ["latitude", "longitude", "current_utilization"],
            },
            fk_checks=[("seller_id", seller_keys)],
        )

        # Refresh parent key sets now that warehouses/products exist.
        warehouse_keys = set(db.scalars(select(Warehouse.warehouse_id)).all())
        product_keys = set(db.scalars(select(Product.product_id)).all())
        order_keys = set(db.scalars(select(Order.order_id)).all())

        load_table(
            db, "inventory (Week 2)", os.path.join(SIM_DIR, "inventory.csv"),
            Inventory, "inventory_id",
            prepare_kwargs={
                "int_cols": ["stock_level", "reorder_threshold", "reorder_quantity"],
                "date_cols": ["last_restock_date"],
            },
            fk_checks=[("warehouse_id", warehouse_keys), ("product_id", product_keys)],
        )
        load_table(
            db, "vehicles (Week 2)", os.path.join(SIM_DIR, "vehicles.csv"),
            Vehicle, "vehicle_id",
            prepare_kwargs={
                "int_cols": ["capacity_kg", "capacity_packages", "average_speed_kmph"],
                "float_cols": ["cost_per_km"],
            },
            fk_checks=[("warehouse_id", warehouse_keys)],
        )

        vehicle_keys = set(db.scalars(select(Vehicle.vehicle_id)).all())

        load_table(
            db, "delivery_routes (Week 2)", os.path.join(SIM_DIR, "delivery_routes.csv"),
            DeliveryRoute, "route_id",
            prepare_kwargs={
                "float_cols": ["source_latitude", "source_longitude",
                               "destination_latitude", "destination_longitude",
                               "estimated_distance_km", "estimated_time_minutes",
                               "estimated_cost"],
            },
            fk_checks=[("order_id", order_keys), ("warehouse_id", warehouse_keys),
                       ("customer_id", customer_keys), ("vehicle_id", vehicle_keys)],
        )
        load_table(
            db, "disruptions (Week 2)", os.path.join(SIM_DIR, "disruptions.csv"),
            Disruption, "disruption_id",
            prepare_kwargs={
                "int_cols": ["estimated_delay_minutes"],
                "datetime_cols": ["start_time", "end_time"],
            },
            fk_checks=[("affected_warehouse_id", warehouse_keys)],
        )

        banner("LOAD COMPLETE - row counts per table")
        for model in (Customer, Seller, Product, Order, Warehouse, Inventory,
                      Vehicle, DeliveryRoute, Disruption):
            print(f"  {model.__tablename__:16}: {db_count(db, model):,} rows")
        print("\nDone. Next: python notebooks/week3_test_crud.py")
    finally:
        db.close()


if __name__ == "__main__":
    main()
