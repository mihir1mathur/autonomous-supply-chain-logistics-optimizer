"""
============================================================================
WAREHOUSE SERVICE  (Week 4)   entity: warehouses
Project: Supply Chain & Logistics Optimizer
============================================================================

Business logic for warehouses (fulfillment ORIGINS). Subclasses BaseService for
the generic CRUD + pagination and declares the warehouse-specific safelists.
============================================================================
"""

from models import Warehouse

from api.services.base_service import BaseService


class WarehouseService(BaseService):
    model = Warehouse
    pk_name = "warehouse_id"
    entity_name = "Warehouse"

    filterable_fields = {
        "warehouse_state",
        "warehouse_city",
        "operating_status",
        "seller_id",
    }
    searchable_fields = {"warehouse_city", "warehouse_id", "seller_id"}
    sortable_fields = {
        "warehouse_id",
        "warehouse_city",
        "warehouse_state",
        "capacity",
        "current_utilization",
        "operating_status",
    }


warehouse_service = WarehouseService()
