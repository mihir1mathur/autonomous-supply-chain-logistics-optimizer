"""
PRODUCT MODEL  (table: products)  -- the INVENTORY ITEMS (catalog).

Source: processed/products_clean.csv (REAL Olist data).
A product is a thing that CAN be stocked and ordered. Weight and dimensions
matter later for packing and vehicle capacity.

One product -> many inventory records (one per warehouse that stocks it).
"""

from sqlalchemy import Column, Float, Integer, String
from sqlalchemy.orm import relationship

from database.connection import Base


class Product(Base):
    __tablename__ = "products"

    # PRIMARY KEY.
    product_id = Column(String, primary_key=True)

    # Category in Portuguese (original) and English (added during Week 1).
    # Indexed because we group/filter by category a lot.
    product_category_name = Column(String, index=True)
    product_category_name_english = Column(String, index=True)

    # Catalog metadata. These can be missing for a few products, so nullable.
    product_name_length = Column(Integer, nullable=True)
    product_description_length = Column(Integer, nullable=True)
    product_photos_qty = Column(Integer, nullable=True)

    # Physical attributes (used later for freight / vehicle capacity). Nullable
    # because 2 products lack weight/dimensions (flagged back in Week 1).
    product_weight_g = Column(Float, nullable=True)
    product_length_cm = Column(Float, nullable=True)
    product_height_cm = Column(Float, nullable=True)
    product_width_cm = Column(Float, nullable=True)

    # RELATIONSHIP: one product appears in many inventory rows.
    inventory_items = relationship("Inventory", back_populates="product")

    def __repr__(self):
        return f"<Product {self.product_id} ({self.product_category_name_english})>"
