"""
============================================================================
CUSTOMER SCHEMAS  (Week 4)   entity: customers   (Week 3 model: models/customer.py)
Project: Supply Chain & Logistics Optimizer
============================================================================

A customer is a delivery DESTINATION (Week 0 mapping). These schemas describe
the JSON the API accepts and returns for customers.

FOUR SCHEMAS (the pattern used for every entity):
  CustomerBase     - shared fields + validation rules (the "validation schema").
  CustomerCreate   - POST body to create a customer (customer_id required).
  CustomerUpdate   - PUT/PATCH body; every field optional (change some fields).
  CustomerResponse - what the API returns (reads from the SQLAlchemy model).

Field names match the Week 3 model EXACTLY, so nothing has to be translated
between the API and the database.
============================================================================
"""

from pydantic import BaseModel, Field, field_validator

from api.schemas.base import ORMModel


# ---------------------------------------------------------------------------
# BASE / VALIDATION SCHEMA - the shared fields and the rules that validate them.
# Create and Update both build on this so the rules live in exactly one place.
# ---------------------------------------------------------------------------
class CustomerBase(BaseModel):
    # A real Olist person-identifier (same person across many orders).
    customer_unique_id: str | None = Field(
        None,
        description="Identifier for the same real person across many orders.",
        examples=["7c396fd4830fd04220f754e42b4e5bff"],
    )
    # Destination location: zip prefix + city + state.
    customer_zip_code_prefix: int | None = Field(
        None,
        ge=0,
        description="Brazilian zip-code prefix of the delivery address.",
        examples=[14409],
    )
    customer_city: str | None = Field(
        None, description="Destination city.", examples=["franca"]
    )
    customer_state: str | None = Field(
        None,
        min_length=2,
        max_length=2,
        description="Two-letter Brazilian state code.",
        examples=["SP"],
    )

    @field_validator("customer_state")
    @classmethod
    def _uppercase_state(cls, value: str | None) -> str | None:
        """State codes are always stored uppercase (e.g. 'sp' -> 'SP')."""
        return value.upper() if value else value


# ---------------------------------------------------------------------------
# CREATE (request body for POST). The id is required here because the caller
# chooses it (our ids are natural string keys from the data, e.g. Olist ids).
# ---------------------------------------------------------------------------
class CustomerCreate(CustomerBase):
    customer_id: str = Field(
        ...,  # ... means REQUIRED.
        description="Primary key. The Olist customer id (one per order).",
        examples=["06b8999e2fba1a1fbc88172c00ba8bc7"],
    )


# ---------------------------------------------------------------------------
# UPDATE (request body for PUT/PATCH). EVERY field optional, so a caller can
# send just the fields they want to change. The id is never updated (it is in
# the URL), so it is not here.
# ---------------------------------------------------------------------------
class CustomerUpdate(CustomerBase):
    pass  # all inherited fields are already optional.


# ---------------------------------------------------------------------------
# RESPONSE (what the API returns). Inherits from_attributes so FastAPI can
# build it straight from a SQLAlchemy Customer row.
# ---------------------------------------------------------------------------
class CustomerResponse(ORMModel):
    customer_id: str
    customer_unique_id: str | None = None
    customer_zip_code_prefix: int | None = None
    customer_city: str | None = None
    customer_state: str | None = None
