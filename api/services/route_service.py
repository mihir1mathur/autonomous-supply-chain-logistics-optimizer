"""
============================================================================
ROUTE SERVICE  (Week 4)   entity: delivery_routes
Project: Supply Chain & Logistics Optimizer
============================================================================

Business logic for delivery routes (warehouse -> customer trips). Subclasses
BaseService for generic CRUD + pagination and declares route-specific safelists.

This is the entity Week 5 (OR-Tools) will write back into: the optimizer will
set vehicle_id and improve the estimated_* fields. Because all writes go through
this service, that future work plugs in here without touching routers.
============================================================================
"""

from models import DeliveryRoute

from api.services.base_service import BaseService


class RouteService(BaseService):
    model = DeliveryRoute
    pk_name = "route_id"
    entity_name = "Delivery route"

    filterable_fields = {
        "order_id",
        "warehouse_id",
        "customer_id",
        "vehicle_id",
        "route_status",
        "source_state",
        "destination_state",
    }
    searchable_fields = {
        "route_id",
        "source_city",
        "destination_city",
        "order_id",
    }
    sortable_fields = {
        "route_id",
        "warehouse_id",
        "customer_id",
        "route_status",
        "estimated_distance_km",
        "estimated_time_minutes",
        "estimated_cost",
    }


route_service = RouteService()
