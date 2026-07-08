"""
SELLER MODEL  (table: sellers)  -- the original fulfillment SOURCES.

Source: processed/sellers_clean.csv (REAL Olist data).
In Olist a seller is the merchant that ships a product. In our logistics
model a seller is the raw origin of goods; in Week 2 the busiest sellers were
promoted to WAREHOUSES (fulfillment origins with capacity, stock, vehicles).

We keep sellers as their own table for two reasons:
  1. Normalization - a warehouse's location comes FROM its seller, so the
     seller is the single source of truth for that place.
  2. Coverage - there are 3,095 real sellers but only the top 150 became
     warehouses. Keeping every seller lets later weeks promote more of them
     to warehouses without changing the schema.

One seller -> zero or one warehouse (only the busiest sellers become one).
"""

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from database.connection import Base


class Seller(Base):
    __tablename__ = "sellers"

    # PRIMARY KEY - the real Olist seller id.
    seller_id = Column(String, primary_key=True)

    # Location of the seller (REAL). zip prefix + city + state.
    seller_zip_code_prefix = Column(Integer, index=True)
    seller_city = Column(String)
    seller_state = Column(String, index=True)

    # RELATIONSHIP: a seller may back one warehouse (the top 150 sellers do).
    # uselist=False makes this a one-to-one from the seller's side.
    warehouse = relationship("Warehouse", back_populates="seller", uselist=False)

    def __repr__(self):
        return f"<Seller {self.seller_id} ({self.seller_city}, {self.seller_state})>"
