"""
============================================================================
DISRUPTION SCHEMAS  (Week 4)   entity: disruptions  (model: models/disruption.py)
Project: Supply Chain & Logistics Optimizer
============================================================================

A disruption is an event that delays deliveries (Week 2, simulated). It sits in
a real city/state and MAY point at a warehouse (affected_warehouse_id) or, for
future replanning, a route (affected_route_id) - both optional. disruption_type,
severity, and status are restricted via enums.

Four schemas: Base (validation) -> Create / Update -> Response.
============================================================================
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from api.schemas.base import ORMModel
from api.utils.validation import DisruptionStatus, DisruptionType, Severity


class DisruptionBase(BaseModel):
    disruption_type: DisruptionType | None = Field(
        None,
        description="heavy_traffic / severe_weather / warehouse_overload / "
        "inventory_shortage / road_closure.",
    )
    severity: Severity | None = Field(None, description="low / medium / high / critical.")
    location_city: str | None = Field(None, description="City where the event happens.")
    location_state: str | None = Field(
        None, min_length=2, max_length=2, description="State (2-letter code)."
    )
    affected_warehouse_id: str | None = Field(
        None, description="Optional FK to the affected warehouse (null for area-wide)."
    )
    affected_route_id: str | None = Field(
        None, description="Optional FK to a specific route (reserved for Week 7)."
    )
    start_time: datetime | None = Field(None, description="When the event starts.")
    end_time: datetime | None = Field(None, description="When the event ends.")
    impact_description: str | None = Field(None, description="Free-text description.")
    estimated_delay_minutes: int | None = Field(
        None, ge=0, description="Estimated delay caused, in minutes."
    )
    status: DisruptionStatus | None = Field(
        None, description="active / resolved / scheduled."
    )

    @field_validator("location_state")
    @classmethod
    def _uppercase_state(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class DisruptionCreate(DisruptionBase):
    disruption_id: str = Field(..., description="Primary key, e.g. 'DIS-0001'.")


class DisruptionUpdate(DisruptionBase):
    pass


class DisruptionResponse(ORMModel):
    disruption_id: str
    disruption_type: str | None = None
    severity: str | None = None
    location_city: str | None = None
    location_state: str | None = None
    affected_warehouse_id: str | None = None
    affected_route_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    impact_description: str | None = None
    estimated_delay_minutes: int | None = None
    status: str | None = None
