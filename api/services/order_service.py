"""
============================================================================
ORDER SERVICE  (Week 4)   entity: orders
Project: Supply Chain & Logistics Optimizer
============================================================================

Business logic for orders (SHIPMENT REQUESTS). Subclasses BaseService for
generic CRUD + pagination and declares the order-specific safelists. Orders are
REAL Olist data and read-heavy, so no special write rule is needed here.
============================================================================
"""

from models import Order

from api.services.base_service import BaseService


class OrderService(BaseService):
    model = Order
    pk_name = "order_id"
    entity_name = "Order"

    filterable_fields = {"customer_id", "order_status"}
    searchable_fields = {"order_id", "customer_id", "order_status"}
    sortable_fields = {
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_estimated_delivery_date",
        "order_delivered_customer_date",
    }


order_service = OrderService()
