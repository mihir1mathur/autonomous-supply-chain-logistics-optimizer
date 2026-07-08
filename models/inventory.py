"""
INVENTORY MODEL  (table: inventory)  -- STOCK that connects a product to a
warehouse with a quantity.

Source: simulation/inventory.csv (Week 2).
  - REAL signal: which warehouse stocks which product (from real sales).
  - SIMULATED: stock_level, reorder thresholds, last_restock_date, status.

Inventory is the LINK table between products and warehouses:
  one row = "this warehouse holds this many units of this product".
"""

from sqlalchemy import Column, Date, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database.connection import Base


class Inventory(Base):
    __tablename__ = "inventory"

    # PRIMARY KEY (e.g. "INV-000001").
    inventory_id = Column(String, primary_key=True)

    # FOREIGN KEYS - this is what makes inventory the bridge.
    warehouse_id = Column(String, ForeignKey("warehouses.warehouse_id"), index=True)
    product_id = Column(String, ForeignKey("products.product_id"), index=True)

    # Denormalized category copy (handy for quick filtering without a join).
    product_category_name = Column(String)

    # Stock numbers (SIMULATED).
    stock_level = Column(Integer)         # units currently on hand
    reorder_threshold = Column(Integer)   # reorder when stock drops to/below this
    reorder_quantity = Column(Integer)    # how many units to bring in per restock
    last_restock_date = Column(Date, nullable=True)

    # healthy / low_stock / out_of_stock. Indexed: we query stockouts a lot.
    inventory_status = Column(String, index=True)

    # RELATIONSHIPS (the two parents this row links).
    warehouse = relationship("Warehouse", back_populates="inventory_items")
    product = relationship("Product", back_populates="inventory_items")

    def __repr__(self):
        return (
            f"<Inventory {self.inventory_id} wh={self.warehouse_id} "
            f"prod={self.product_id} stock={self.stock_level} ({self.inventory_status})>"
        )
