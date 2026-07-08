"""
============================================================================
VEHICLE SERVICE  (Week 4)   entity: vehicles
Project: Supply Chain & Logistics Optimizer
============================================================================

Business logic for vehicles (the delivery FLEET). Subclasses BaseService for
generic CRUD + pagination and declares the vehicle-specific safelists.

The Week 3 helper crud.update_vehicle_status already exists for the common
"change a vehicle's availability" action; a future endpoint can delegate to it,
while the generic update() here covers arbitrary field changes.
============================================================================
"""

from models import Vehicle

from api.services.base_service import BaseService


class VehicleService(BaseService):
    model = Vehicle
    pk_name = "vehicle_id"
    entity_name = "Vehicle"

    filterable_fields = {
        "warehouse_id",
        "vehicle_type",
        "availability_status",
        "current_location_state",
    }
    searchable_fields = {"vehicle_id", "current_location_city", "warehouse_id"}
    sortable_fields = {
        "vehicle_id",
        "vehicle_type",
        "availability_status",
        "capacity_kg",
        "capacity_packages",
        "cost_per_km",
        "average_speed_kmph",
    }


vehicle_service = VehicleService()
