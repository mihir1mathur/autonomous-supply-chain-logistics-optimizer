"""
============================================================================
VEHICLE SCHEMAS  (Week 4)   entity: vehicles  (model: models/vehicle.py)
Project: Supply Chain & Logistics Optimizer
============================================================================

A vehicle is part of the delivery FLEET (Week 2, fully simulated). vehicle_type
and availability_status are restricted to their allowed values via enums.

Four schemas: Base (validation) -> Create / Update -> Response.
============================================================================
"""

from pydantic import BaseModel, Field, field_validator

from api.schemas.base import ORMModel
from api.utils.validation import AvailabilityStatus, VehicleType


class VehicleBase(BaseModel):
    warehouse_id: str | None = Field(None, description="FK to the home warehouse.")
    vehicle_type: VehicleType | None = Field(
        None, description="van / small_truck / medium_truck / large_truck."
    )
    capacity_kg: int | None = Field(None, ge=0, description="Weight capacity (kg).")
    capacity_packages: int | None = Field(
        None, ge=0, description="Package-count capacity."
    )
    current_location_city: str | None = Field(None, description="Current city.")
    current_location_state: str | None = Field(
        None, min_length=2, max_length=2, description="Current state (2-letter code)."
    )
    availability_status: AvailabilityStatus | None = Field(
        None, description="available / on_delivery / maintenance."
    )
    cost_per_km: float | None = Field(None, ge=0, description="Cost per kilometre.")
    average_speed_kmph: int | None = Field(
        None, gt=0, description="Average speed in km/h (used for time estimates)."
    )

    @field_validator("current_location_state")
    @classmethod
    def _uppercase_state(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class VehicleCreate(VehicleBase):
    vehicle_id: str = Field(..., description="Primary key, e.g. 'VEH-00001'.")


class VehicleUpdate(VehicleBase):
    pass


class VehicleResponse(ORMModel):
    vehicle_id: str
    warehouse_id: str | None = None
    vehicle_type: str | None = None
    capacity_kg: int | None = None
    capacity_packages: int | None = None
    current_location_city: str | None = None
    current_location_state: str | None = None
    availability_status: str | None = None
    cost_per_km: float | None = None
    average_speed_kmph: int | None = None
