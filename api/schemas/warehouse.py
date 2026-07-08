"""
============================================================================
WAREHOUSE SCHEMAS  (Week 4)   entity: warehouses  (model: models/warehouse.py)
Project: Supply Chain & Logistics Optimizer
============================================================================

A warehouse is a fulfillment ORIGIN (Week 2). Location is REAL (from the seller
it was mapped from); capacity / utilization / operating_status are SIMULATED.

Four schemas: Base (validation) -> Create / Update (requests) -> Response.
operating_status is restricted to the allowed values via the OperatingStatus
enum, so an invalid status is rejected with a clean 422.
============================================================================
"""

from pydantic import BaseModel, Field, field_validator

from api.schemas.base import ORMModel
from api.utils.validation import OperatingStatus


class WarehouseBase(BaseModel):
    seller_id: str | None = Field(
        None, description="FK to the seller this warehouse was mapped from."
    )
    warehouse_city: str | None = Field(None, description="Warehouse city (real).")
    warehouse_state: str | None = Field(
        None, min_length=2, max_length=2, description="Two-letter state code."
    )
    warehouse_zip_code_prefix: int | None = Field(
        None, ge=0, description="Zip-code prefix of the warehouse."
    )
    latitude: float | None = Field(None, ge=-90, le=90, description="Latitude.")
    longitude: float | None = Field(None, ge=-180, le=180, description="Longitude.")
    capacity: int | None = Field(
        None, ge=0, description="Package-slot capacity (simulated)."
    )
    current_utilization: float | None = Field(
        None, ge=0, le=1, description="Fraction of capacity in use, 0..1 (simulated)."
    )
    operating_status: OperatingStatus | None = Field(
        None, description="active / overloaded / inactive (simulated)."
    )

    @field_validator("warehouse_state")
    @classmethod
    def _uppercase_state(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class WarehouseCreate(WarehouseBase):
    warehouse_id: str = Field(..., description="Primary key, e.g. 'WH-0001'.")


class WarehouseUpdate(WarehouseBase):
    pass


class WarehouseResponse(ORMModel):
    warehouse_id: str
    seller_id: str | None = None
    warehouse_city: str | None = None
    warehouse_state: str | None = None
    warehouse_zip_code_prefix: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    capacity: int | None = None
    current_utilization: float | None = None
    operating_status: str | None = None
