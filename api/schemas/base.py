"""
============================================================================
SHARED SCHEMA BASE  (Week 4)
Project: Supply Chain & Logistics Optimizer
============================================================================

This tiny file holds the ONE setting every Response schema needs, so we do not
repeat it in seven files.

WHY `from_attributes=True` MATTERS (the ORM bridge)
---------------------------------------------------
  A service returns a SQLAlchemy MODEL object (e.g. a Warehouse row). FastAPI
  needs to turn that into JSON using the RESPONSE schema. Normally Pydantic
  builds a model from a dict; `from_attributes=True` tells it "you may also
  build me from an OBJECT by reading its attributes" - i.e. read
  warehouse.warehouse_id, warehouse.capacity, ... directly off the SQLAlchemy
  row. This is the clean seam between the database objects (Week 3 models) and
  the JSON the API returns.

ORMModel is the base class every <Entity>Response inherits from.
============================================================================
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base for RESPONSE schemas: lets Pydantic read from SQLAlchemy objects."""

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# The paginated response envelope, as a Pydantic model so it appears properly
# in the auto-generated docs. It mirrors the dict built in utils/pagination.py.
# ---------------------------------------------------------------------------
class PaginationMeta(BaseModel):
    """The "which page is this" information returned alongside every list."""

    total: int          # total matching rows across ALL pages.
    page: int           # the page number returned (starts at 1).
    page_size: int      # how many rows per page.
    total_pages: int    # how many pages exist in total.
    has_next: bool      # is there a page after this one?
    has_prev: bool      # is there a page before this one?


ItemT = TypeVar("ItemT")


class PaginatedResponse(BaseModel, Generic[ItemT]):
    """
    Standard list response: a page of items plus pagination metadata.

    Used as `PaginatedResponse[CustomerResponse]` etc. Because the item schema
    has from_attributes=True, FastAPI converts the SQLAlchemy rows the service
    returns straight into the item schema - the router just returns the Page.
    """

    items: list[ItemT]
    pagination: PaginationMeta
