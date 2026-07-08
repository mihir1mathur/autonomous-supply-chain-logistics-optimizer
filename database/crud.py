"""
============================================================================
CRUD / QUERY FUNCTIONS  (Week 3)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT IS CRUD?
-------------
  CRUD = Create, Read, Update, Delete - the four basic things you do to data
  in a database. This file holds small, readable helper functions for the
  CRUD operations this project needs. They are deliberately simple.

WHY KEEP THEM IN ONE PLACE?
---------------------------
  The FastAPI backend (Week 4) will call these SAME functions instead of
  writing SQL inside the web layer. Centralizing them means one place to read,
  test, and reuse - the web app just exposes them over HTTP later.

HOW TO USE
----------
  Every function takes a `db` session as its first argument:

      from database.connection import get_session
      from database import crud

      with get_session() as db:
          c = crud.get_customer_by_id(db, "abc123")

INVENTORY STATUS RULE (reused from Week 2)
------------------------------------------
  out_of_stock  if stock_level == 0
  low_stock     if stock_level <= reorder_threshold
  healthy       otherwise
============================================================================
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import (
    Customer,
    Disruption,
    DeliveryRoute,
    Inventory,
    Order,
    Product,
    Seller,
    Vehicle,
    Warehouse,
)


def _recompute_inventory_status(stock_level: int, reorder_threshold: int) -> str:
    """Apply the Week 2 stock rule. Used after we change a stock level."""
    if stock_level <= 0:
        return "out_of_stock"
    if stock_level <= reorder_threshold:
        return "low_stock"
    return "healthy"


# ===========================================================================
# READ - single-row lookups by primary key
# ===========================================================================
def get_customer_by_id(db: Session, customer_id: str):
    """Return one customer (or None if not found)."""
    return db.get(Customer, customer_id)


def get_seller_by_id(db: Session, seller_id: str):
    """Return one seller (or None if not found)."""
    return db.get(Seller, seller_id)


def get_product_by_id(db: Session, product_id: str):
    """Return one product (or None if not found)."""
    return db.get(Product, product_id)


def get_order_by_id(db: Session, order_id: str):
    """Return one order (or None)."""
    return db.get(Order, order_id)


def get_warehouse_by_id(db: Session, warehouse_id: str):
    """Return one warehouse (or None)."""
    return db.get(Warehouse, warehouse_id)


# ===========================================================================
# READ - list queries
# ===========================================================================
def get_inventory_by_warehouse(db: Session, warehouse_id: str):
    """All inventory rows stored at a given warehouse."""
    stmt = select(Inventory).where(Inventory.warehouse_id == warehouse_id)
    return db.scalars(stmt).all()


def get_low_stock_items(db: Session, limit: int | None = None):
    """
    Items that need attention: low_stock or out_of_stock.
    Useful later for triggering replenishment / agent decisions.
    """
    stmt = (
        select(Inventory)
        .where(Inventory.inventory_status.in_(["low_stock", "out_of_stock"]))
        .order_by(Inventory.stock_level.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return db.scalars(stmt).all()


def get_available_vehicles(db: Session, warehouse_id: str | None = None):
    """
    Vehicles that can be scheduled right now (availability_status == available).
    Optionally restrict to one warehouse's fleet.
    """
    stmt = select(Vehicle).where(Vehicle.availability_status == "available")
    if warehouse_id is not None:
        stmt = stmt.where(Vehicle.warehouse_id == warehouse_id)
    return db.scalars(stmt).all()


def get_routes_by_warehouse(db: Session, warehouse_id: str, limit: int | None = None):
    """All delivery routes that start from a given warehouse."""
    stmt = select(DeliveryRoute).where(DeliveryRoute.warehouse_id == warehouse_id)
    if limit is not None:
        stmt = stmt.limit(limit)
    return db.scalars(stmt).all()


def get_active_disruptions(db: Session):
    """All disruptions currently active (status == active)."""
    stmt = select(Disruption).where(Disruption.status == "active")
    return db.scalars(stmt).all()


# ===========================================================================
# UPDATE
# ===========================================================================
def update_inventory_stock(db: Session, inventory_id: str, new_stock_level: int):
    """
    Set a new stock level for one inventory row and RECOMPUTE its status so
    the two never disagree. Returns the updated row (or None if not found).
    """
    item = db.get(Inventory, inventory_id)
    if item is None:
        return None
    item.stock_level = new_stock_level
    item.inventory_status = _recompute_inventory_status(
        new_stock_level, item.reorder_threshold
    )
    db.commit()
    db.refresh(item)
    return item


def update_vehicle_status(db: Session, vehicle_id: str, new_status: str):
    """
    Change a vehicle's availability (available / on_delivery / maintenance).
    Returns the updated vehicle (or None if not found).
    """
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        return None
    vehicle.availability_status = new_status
    db.commit()
    db.refresh(vehicle)
    return vehicle


# ===========================================================================
# CREATE
# ===========================================================================
def insert_disruption(db: Session, **fields):
    """
    Insert a new disruption row. Pass column values as keyword arguments, e.g.

        insert_disruption(
            db,
            disruption_id="DIS-9001",
            disruption_type="heavy_traffic",
            severity="high",
            location_city="sao paulo",
            location_state="SP",
            status="active",
            estimated_delay_minutes=120,
        )

    Returns the created Disruption.
    """
    disruption = Disruption(**fields)
    db.add(disruption)
    db.commit()
    db.refresh(disruption)
    return disruption
