"""
CUSTOMER MODEL  (table: customers)  -- the delivery DESTINATIONS.

Source: processed/customers_clean.csv (REAL Olist data).
In our logistics model a customer is the place an order must be delivered to.

One customer -> many orders, and -> many delivery routes.
"""

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from database.connection import Base


class Customer(Base):
    __tablename__ = "customers"

    # PRIMARY KEY: customer_id is one record PER ORDER in Olist (not per person).
    customer_id = Column(String, primary_key=True)

    # customer_unique_id identifies the same real PERSON across many orders.
    # Indexed because we often look people up by it.
    customer_unique_id = Column(String, index=True)

    # Location of the destination. zip prefix + city + state.
    customer_zip_code_prefix = Column(Integer, index=True)
    customer_city = Column(String)
    customer_state = Column(String, index=True)

    # RELATIONSHIPS (how this row connects to other tables).
    # One customer has many orders and many delivery routes.
    orders = relationship("Order", back_populates="customer")
    delivery_routes = relationship("DeliveryRoute", back_populates="customer")

    def __repr__(self):
        return f"<Customer {self.customer_id} ({self.customer_city}, {self.customer_state})>"
