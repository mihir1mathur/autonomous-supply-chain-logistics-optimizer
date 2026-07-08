"""
============================================================================
INVENTORY SERVICE  (Week 4)   entity: inventory
Project: Supply Chain & Logistics Optimizer
============================================================================

Business logic for inventory. This service has a REAL rule (unlike the simpler
read-heavy entities): inventory_status must always agree with stock_level and
reorder_threshold. We enforce that here - in ONE place - so it can never be
forgotten or half-applied, no matter who calls the service.

  RULE (identical to Week 2 and database/crud.py):
    out_of_stock  if stock_level <= 0
    low_stock     if stock_level <= reorder_threshold
    healthy       otherwise

We reuse recompute_inventory_status() from api/utils/validation.py (which itself
mirrors database/crud.py) and, for pure stock updates, we can delegate to the
Week 3 crud.update_inventory_stock helper.
============================================================================
"""

from sqlalchemy.orm import Session

from models import Inventory

from api.services.base_service import BaseService
from api.utils.exceptions import NotFoundError
from api.utils.validation import recompute_inventory_status


class InventoryService(BaseService):
    model = Inventory
    pk_name = "inventory_id"
    entity_name = "Inventory item"

    filterable_fields = {
        "warehouse_id",
        "product_id",
        "product_category_name",
        "inventory_status",
    }
    searchable_fields = {"inventory_id", "product_id", "product_category_name"}
    sortable_fields = {
        "inventory_id",
        "warehouse_id",
        "product_id",
        "stock_level",
        "reorder_threshold",
        "inventory_status",
    }

    # ---- CREATE: derive inventory_status so it is always consistent -------
    def create(self, db: Session, data: dict):
        stock = data.get("stock_level")
        threshold = data.get("reorder_threshold")
        if stock is not None and threshold is not None:
            data["inventory_status"] = recompute_inventory_status(stock, threshold)
        return super().create(db, data)

    # ---- UPDATE: recompute inventory_status if stock/threshold changed ----
    def update(self, db: Session, item_id: str, data: dict):
        item = self.get_or_none(db, item_id)
        if item is None:
            raise NotFoundError(f"{self.entity_name} '{item_id}' was not found.")

        # Apply the caller's changes first.
        for field, value in data.items():
            setattr(item, field, value)

        # If either input to the rule changed, recompute the status so the two
        # can never disagree - even if the caller also sent a status.
        if "stock_level" in data or "reorder_threshold" in data:
            item.inventory_status = recompute_inventory_status(
                item.stock_level or 0, item.reorder_threshold or 0
            )

        db.commit()
        db.refresh(item)
        return item


inventory_service = InventoryService()
