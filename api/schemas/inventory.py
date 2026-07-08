"""
============================================================================
INVENTORY SCHEMAS  (Week 4)   entity: inventory  (model: models/inventory.py)
Project: Supply Chain & Logistics Optimizer
============================================================================

Inventory is the BRIDGE linking a product to a warehouse with a quantity
(Week 3). inventory_status is DERIVED from stock_level vs. reorder_threshold by
the Week 2 rule; the service recomputes it, so a caller does not have to send it
(and it is kept consistent even if they do).

Four schemas: Base (validation) -> Create / Update -> Response.
============================================================================
"""

from datetime import date

from pydantic import BaseModel, Field

from api.schemas.base import ORMModel
from api.utils.validation import InventoryStatus


class InventoryBase(BaseModel):
    warehouse_id: str | None = Field(None, description="FK to the warehouse holding stock.")
    product_id: str | None = Field(None, description="FK to the product being stocked.")
    product_category_name: str | None = Field(
        None, description="Denormalized category copy (for quick filtering)."
    )
    stock_level: int | None = Field(None, ge=0, description="Units currently on hand.")
    reorder_threshold: int | None = Field(
        None, ge=0, description="Reorder when stock drops to/below this."
    )
    reorder_quantity: int | None = Field(
        None, ge=0, description="Units to bring in per restock."
    )
    last_restock_date: date | None = Field(None, description="Date of the last restock.")
    # Usually DERIVED by the service; accepted but recomputed for consistency.
    inventory_status: InventoryStatus | None = Field(
        None, description="healthy / low_stock / out_of_stock (derived from stock)."
    )


class InventoryCreate(InventoryBase):
    inventory_id: str = Field(..., description="Primary key, e.g. 'INV-000001'.")
    stock_level: int = Field(..., ge=0, description="Units on hand (required on create).")
    reorder_threshold: int = Field(
        ..., ge=0, description="Reorder threshold (required on create)."
    )


class InventoryUpdate(InventoryBase):
    pass


class InventoryResponse(ORMModel):
    inventory_id: str
    warehouse_id: str | None = None
    product_id: str | None = None
    product_category_name: str | None = None
    stock_level: int | None = None
    reorder_threshold: int | None = None
    reorder_quantity: int | None = None
    last_restock_date: date | None = None
    inventory_status: str | None = None
