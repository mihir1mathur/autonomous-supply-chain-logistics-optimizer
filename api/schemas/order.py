"""
============================================================================
ORDER SCHEMAS  (Week 4)   entity: orders  (model: models/order.py)
Project: Supply Chain & Logistics Optimizer
============================================================================

An order is a SHIPMENT REQUEST (Week 0). It belongs to one customer and carries
the five delivery timestamps used to measure delays. order_status is kept as a
free string because the real Olist data uses many values (delivered, shipped,
canceled, invoiced, processing, unavailable, created, approved).

Four schemas: Base (validation) -> Create / Update -> Response.
============================================================================
"""

from datetime import datetime

from pydantic import BaseModel, Field

from api.schemas.base import ORMModel


class OrderBase(BaseModel):
    customer_id: str | None = Field(None, description="FK to the customer (destination).")
    order_status: str | None = Field(
        None,
        description="e.g. delivered / shipped / canceled / invoiced / processing.",
        examples=["delivered"],
    )
    order_purchase_timestamp: datetime | None = Field(None, description="When the order was placed.")
    order_approved_at: datetime | None = Field(None, description="When payment was approved.")
    order_delivered_carrier_date: datetime | None = Field(
        None, description="When the carrier picked it up."
    )
    order_delivered_customer_date: datetime | None = Field(
        None, description="When it reached the customer."
    )
    order_estimated_delivery_date: datetime | None = Field(
        None, description="The promised delivery date."
    )


class OrderCreate(OrderBase):
    order_id: str = Field(..., description="Primary key (the Olist order id).")


class OrderUpdate(OrderBase):
    pass


class OrderResponse(ORMModel):
    order_id: str
    customer_id: str | None = None
    order_status: str | None = None
    order_purchase_timestamp: datetime | None = None
    order_approved_at: datetime | None = None
    order_delivered_carrier_date: datetime | None = None
    order_delivered_customer_date: datetime | None = None
    order_estimated_delivery_date: datetime | None = None
