"""
api/utils/ package  (Week 4)
Project: Supply Chain & Logistics Optimizer

Small, shared building blocks used across the whole API so the same behaviour
is written ONCE and reused everywhere:

  exceptions.py - our own error types (NotFoundError, DuplicateError, ...) and
                  the single JSON shape every error is returned in. This is how
                  the API returns clean 404/409/422/500 responses instead of
                  leaking raw database errors.
  pagination.py - the reusable "page of results" logic (limit/offset, sorting,
                  and the standard paginated response envelope).
  validation.py - reusable field validators and the allowed value lists (enums)
                  that mirror the Week 2 / Week 3 rules (e.g. inventory_status
                  can only be healthy / low_stock / out_of_stock).

Keeping these here means routers and services stay short and consistent.
"""

from api.utils.exceptions import (
    AppError,
    BadRequestError,
    ConflictError,
    DuplicateError,
    NotFoundError,
    UnprocessableError,
    register_exception_handlers,
)
from api.utils.pagination import PageParams, Page, paginate

__all__ = [
    "AppError",
    "BadRequestError",
    "ConflictError",
    "DuplicateError",
    "NotFoundError",
    "UnprocessableError",
    "register_exception_handlers",
    "PageParams",
    "Page",
    "paginate",
]
