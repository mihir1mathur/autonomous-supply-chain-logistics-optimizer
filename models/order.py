"""
ORDER MODEL  (table: orders)  -- the SHIPMENT REQUESTS.

Source: processed/orders_clean.csv (REAL Olist data).
An order is one customer's purchase = a request to deliver goods. The five
timestamp columns let us measure delivery delays (promised vs actual).

One order -> belongs to one customer, and -> can have many delivery routes.
"""

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from database.connection import Base


class Order(Base):
    __tablename__ = "orders"

    # PRIMARY KEY.
    order_id = Column(String, primary_key=True)

    # FOREIGN KEY -> customers.customer_id. Every order belongs to a customer.
    # Indexed so "all orders for a customer" is fast.
    customer_id = Column(String, ForeignKey("customers.customer_id"), index=True)

    # delivered / shipped / canceled / etc. Indexed because we filter by it.
    order_status = Column(String, index=True)

    # The delivery timeline. Some are NULL for orders never delivered - that
    # is expected and meaningful (non-delivery is itself a signal).
    order_purchase_timestamp = Column(DateTime, nullable=True)
    order_approved_at = Column(DateTime, nullable=True)
    order_delivered_carrier_date = Column(DateTime, nullable=True)
    order_delivered_customer_date = Column(DateTime, nullable=True)
    order_estimated_delivery_date = Column(DateTime, nullable=True)

    # RELATIONSHIPS.
    customer = relationship("Customer", back_populates="orders")
    delivery_routes = relationship("DeliveryRoute", back_populates="order")

    def __repr__(self):
        return f"<Order {self.order_id} ({self.order_status})>"
