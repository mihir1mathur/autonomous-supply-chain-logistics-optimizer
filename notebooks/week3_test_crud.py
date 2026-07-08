"""
============================================================================
WEEK 3 - CRUD TEST / DEMO
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SCRIPT DOES
---------------------
  Opens one database session and exercises every CRUD/query function in
  database/crud.py, printing readable results. It is a quick way to confirm
  the database is loaded and queryable end-to-end.

  It is READ-MOSTLY: the two "update" demos change a row and then change it
  straight back, so running this script does not leave the data altered.
  The insert demo adds a clearly-marked test disruption (DIS-TEST-0001) and
  then deletes it again at the end.

HOW TO RUN (from the project root)
----------------------------------
    python database/init_db.py
    python notebooks/week3_load_database.py
    python notebooks/week3_test_crud.py
============================================================================
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import select

import models  # registers tables
from database import crud
from database.connection import SessionLocal, test_connection
from models import (
    Customer,
    Disruption,
    Inventory,
    Order,
    Product,
    Seller,
    Vehicle,
    Warehouse,
)


def section(title):
    print("\n" + "-" * 70)
    print(title)
    print("-" * 70)


def first_id(db, model, column):
    """Grab any one existing id from a table, so the demo uses real data."""
    return db.scalar(select(column).limit(1))


def main():
    print("=" * 70)
    print("WEEK 3 - CRUD TEST / DEMO")
    print("=" * 70)

    if not test_connection():
        print("\nAborting: start PostgreSQL, init the DB, and load data first.")
        sys.exit(1)

    db = SessionLocal()
    try:
        # Pull a few real ids to drive the demo (so it works on the loaded data).
        sample_customer_id = first_id(db, Customer, Customer.customer_id)
        sample_seller_id = first_id(db, Seller, Seller.seller_id)
        sample_product_id = first_id(db, Product, Product.product_id)
        sample_order_id = first_id(db, Order, Order.order_id)
        sample_warehouse_id = first_id(db, Warehouse, Warehouse.warehouse_id)

        if sample_warehouse_id is None:
            print("\nNo data found. Run notebooks/week3_load_database.py first.")
            sys.exit(1)

        # ---- READ: single lookups ------------------------------------
        section("get_customer_by_id()")
        print(" ", crud.get_customer_by_id(db, sample_customer_id))

        section("get_seller_by_id()")
        print(" ", crud.get_seller_by_id(db, sample_seller_id))

        section("get_product_by_id()")
        print(" ", crud.get_product_by_id(db, sample_product_id))

        section("get_order_by_id()")
        print(" ", crud.get_order_by_id(db, sample_order_id))

        section("get_warehouse_by_id()")
        wh = crud.get_warehouse_by_id(db, sample_warehouse_id)
        print(" ", wh)

        # ---- READ: lists ---------------------------------------------
        section(f"get_inventory_by_warehouse('{sample_warehouse_id}')  [first 5]")
        inv = crud.get_inventory_by_warehouse(db, sample_warehouse_id)
        print(f"  {len(inv)} inventory rows at this warehouse. First 5:")
        for row in inv[:5]:
            print("   ", row)

        section("get_low_stock_items(limit=5)")
        for row in crud.get_low_stock_items(db, limit=5):
            print("   ", row)

        section("get_available_vehicles(limit shown = 5)")
        vehicles = crud.get_available_vehicles(db)
        print(f"  {len(vehicles)} available vehicles total. First 5:")
        for row in vehicles[:5]:
            print("   ", row)

        section(f"get_routes_by_warehouse('{sample_warehouse_id}', limit=5)")
        for row in crud.get_routes_by_warehouse(db, sample_warehouse_id, limit=5):
            print("   ", row)

        section("get_active_disruptions()  [first 5]")
        active = crud.get_active_disruptions(db)
        print(f"  {len(active)} active disruptions. First 5:")
        for row in active[:5]:
            print("   ", row)

        # ---- UPDATE: change then restore (non-destructive) -----------
        section("update_inventory_stock()  (change, then restore)")
        any_inv = db.scalar(select(Inventory).limit(1))
        if any_inv is not None:
            original = any_inv.stock_level
            updated = crud.update_inventory_stock(db, any_inv.inventory_id, 0)
            print(f"  Set {updated.inventory_id} stock to 0 -> status '{updated.inventory_status}'")
            restored = crud.update_inventory_stock(db, any_inv.inventory_id, original)
            print(f"  Restored stock to {original} -> status '{restored.inventory_status}'")

        section("update_vehicle_status()  (change, then restore)")
        any_vehicle = db.scalar(select(Vehicle).limit(1))
        if any_vehicle is not None:
            original_status = any_vehicle.availability_status
            crud.update_vehicle_status(db, any_vehicle.vehicle_id, "maintenance")
            print(f"  Set {any_vehicle.vehicle_id} -> maintenance")
            crud.update_vehicle_status(db, any_vehicle.vehicle_id, original_status)
            print(f"  Restored {any_vehicle.vehicle_id} -> {original_status}")

        # ---- CREATE: insert then clean up ----------------------------
        section("insert_disruption()  (insert a test row, then delete it)")
        test_id = "DIS-TEST-0001"
        # Remove any leftover from a previous run first.
        leftover = db.get(Disruption, test_id)
        if leftover is not None:
            db.delete(leftover)
            db.commit()
        created = crud.insert_disruption(
            db,
            disruption_id=test_id,
            disruption_type="heavy_traffic",
            severity="high",
            location_city="sao paulo",
            location_state="SP",
            affected_warehouse_id=None,
            estimated_delay_minutes=120,
            status="active",
            impact_description="TEST row created by week3_test_crud.py",
        )
        print(f"  Inserted: {created}")
        db.delete(created)
        db.commit()
        print(f"  Cleaned up test row {test_id}.")

        print("\n" + "=" * 70)
        print("CRUD DEMO COMPLETE - the database can be queried successfully.")
        print("=" * 70)
    finally:
        db.close()


if __name__ == "__main__":
    main()
