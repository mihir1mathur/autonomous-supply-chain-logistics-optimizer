"""
WAREHOUSE MODEL  (table: warehouses)  -- the fulfillment ORIGINS.

Source: simulation/warehouses.csv (Week 2).
  - REAL: location (from Olist sellers) - seller_id, city, state, zip, lat/lng.
  - SIMULATED: capacity, current_utilization, operating_status.

A warehouse is where shipments start. It is the anchor for inventory,
vehicles, delivery routes, and (optionally) disruptions.
"""

from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database.connection import Base


class Warehouse(Base):
    __tablename__ = "warehouses"

    # PRIMARY KEY (e.g. "WH-0001").
    warehouse_id = Column(String, primary_key=True)

    # FOREIGN KEY -> sellers.seller_id. The Olist seller this warehouse was
    # mapped from (REAL). Every warehouse is backed by exactly one seller.
    seller_id = Column(String, ForeignKey("sellers.seller_id"), index=True)

    # Location (REAL).
    warehouse_city = Column(String)
    warehouse_state = Column(String, index=True)
    warehouse_zip_code_prefix = Column(Integer)
    latitude = Column(Float)
    longitude = Column(Float)

    # Operational fields (SIMULATED in Week 2).
    capacity = Column(Integer)               # package-slot capacity
    current_utilization = Column(Float)      # 0..1 fraction in use
    operating_status = Column(String, index=True)  # active / overloaded / inactive

    # RELATIONSHIPS.
    # The seller this warehouse was mapped from (one-to-one, parent side).
    seller = relationship("Seller", back_populates="warehouse")
    # A warehouse has many of each of the following.
    inventory_items = relationship("Inventory", back_populates="warehouse")
    vehicles = relationship("Vehicle", back_populates="warehouse")
    delivery_routes = relationship("DeliveryRoute", back_populates="warehouse")
    disruptions = relationship("Disruption", back_populates="affected_warehouse")

    def __repr__(self):
        return f"<Warehouse {self.warehouse_id} ({self.warehouse_city}, {self.warehouse_state})>"
