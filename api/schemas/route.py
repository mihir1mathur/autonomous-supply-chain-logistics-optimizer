"""
============================================================================
DELIVERY ROUTE SCHEMAS  (Week 4)   entity: delivery_routes  (model: models/route.py)
Project: Supply Chain & Logistics Optimizer
============================================================================

A delivery route ties an order to the warehouse it ships from and the customer
it goes to (Week 2). vehicle_id is reserved for the OR-Tools optimizer (Week 5)
and may be null. route_status is restricted via the RouteStatus enum.

Four schemas: Base (validation) -> Create / Update -> Response.
============================================================================
"""

from pydantic import BaseModel, Field, field_validator

from api.schemas.base import ORMModel
from api.utils.validation import RouteStatus


class RouteBase(BaseModel):
    order_id: str | None = Field(None, description="FK to the order being delivered.")
    warehouse_id: str | None = Field(None, description="FK to the origin warehouse.")
    customer_id: str | None = Field(None, description="FK to the destination customer.")
    vehicle_id: str | None = Field(
        None, description="FK to the assigned vehicle (set by OR-Tools later; may be null)."
    )
    source_city: str | None = Field(None, description="Origin city.")
    source_state: str | None = Field(None, min_length=2, max_length=2, description="Origin state.")
    destination_city: str | None = Field(None, description="Destination city.")
    destination_state: str | None = Field(
        None, min_length=2, max_length=2, description="Destination state."
    )
    source_latitude: float | None = Field(None, ge=-90, le=90, description="Origin latitude.")
    source_longitude: float | None = Field(None, ge=-180, le=180, description="Origin longitude.")
    destination_latitude: float | None = Field(
        None, ge=-90, le=90, description="Destination latitude."
    )
    destination_longitude: float | None = Field(
        None, ge=-180, le=180, description="Destination longitude."
    )
    estimated_distance_km: float | None = Field(None, ge=0, description="Estimated distance (km).")
    estimated_time_minutes: float | None = Field(
        None, ge=0, description="Estimated travel time (minutes)."
    )
    estimated_cost: float | None = Field(None, ge=0, description="Estimated cost.")
    route_status: RouteStatus | None = Field(
        None, description="planned / in_transit / completed."
    )

    @field_validator("source_state", "destination_state")
    @classmethod
    def _uppercase_state(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class RouteCreate(RouteBase):
    route_id: str = Field(..., description="Primary key, e.g. 'RT-000001'.")


class RouteUpdate(RouteBase):
    pass


class RouteResponse(ORMModel):
    route_id: str
    order_id: str | None = None
    warehouse_id: str | None = None
    customer_id: str | None = None
    vehicle_id: str | None = None
    source_city: str | None = None
    source_state: str | None = None
    destination_city: str | None = None
    destination_state: str | None = None
    source_latitude: float | None = None
    source_longitude: float | None = None
    destination_latitude: float | None = None
    destination_longitude: float | None = None
    estimated_distance_km: float | None = None
    estimated_time_minutes: float | None = None
    estimated_cost: float | None = None
    route_status: str | None = None
