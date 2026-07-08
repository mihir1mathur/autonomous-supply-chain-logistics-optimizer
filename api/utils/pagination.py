"""
============================================================================
PAGINATION, SORTING & THE PAGE ENVELOPE  (Week 4)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHY PAGINATION EXISTS (zero-knowledge version)
----------------------------------------------
  Some tables are huge - `orders` has ~99,000 rows and `delivery_routes` even
  more. If a "list orders" endpoint returned ALL of them at once, it would be
  slow, use a lot of memory, and overwhelm the caller. PAGINATION means handing
  back the data in small PAGES, like a book: "give me page 1 (rows 1-20), then
  page 2 (rows 21-40)". The caller asks for a page number and a page size; we
  return just that slice plus some totals so they know how many pages exist.

THE TWO KNOBS
-------------
  page      - which page to return, starting at 1.
  page_size - how many rows per page (capped by API_MAX_PAGE_SIZE so nobody can
              ask for a million rows at once).
  From these we compute the SQL LIMIT (page_size) and OFFSET ((page-1)*size).

SORTING
-------
  Callers can also choose the order: sort_by=<column> and sort_dir=asc|desc.
  We only allow sorting by columns the service explicitly permits (a safelist),
  so a caller can never sort by a random or non-existent column.

THE RESPONSE ENVELOPE
---------------------
  Every list endpoint returns the SAME shape, so callers learn it once:
      {
        "items": [ ...the rows for this page... ],
        "pagination": {
          "total": 99441, "page": 1, "page_size": 20,
          "total_pages": 4973, "has_next": true, "has_prev": false
        }
      }
============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from api.config import get_settings
from api.utils.exceptions import BadRequestError

T = TypeVar("T")


@dataclass
class PageParams:
    """
    The pagination + sorting choices for one list request.

    Built by the shared FastAPI dependency in api/dependencies.py from the
    query string (?page=2&page_size=50&sort_by=stock_level&sort_dir=asc), so
    every list endpoint accepts the same parameters automatically.
    """

    page: int = 1
    page_size: int = 20
    sort_by: str | None = None
    sort_dir: str = "asc"

    @property
    def offset(self) -> int:
        """How many rows to SKIP to reach the requested page."""
        return (self.page - 1) * self.page_size


class Page(dict, Generic[T]):
    """
    The response envelope. It is a plain dict (so FastAPI serialises it to JSON
    directly) with two keys: "items" and "pagination". Generic[T] is only a
    type hint for editors; at runtime it behaves as an ordinary dict.
    """


def _apply_sorting(stmt: Select, model, params: PageParams, sortable: set[str]) -> Select:
    """
    Add an ORDER BY clause if the caller asked to sort, after checking the
    column is allowed. Raises BadRequestError (400) for an unknown column or a
    bad direction, so the caller gets a clear message instead of a 500.
    """
    if params.sort_by is None:
        return stmt

    if params.sort_by not in sortable:
        allowed = ", ".join(sorted(sortable)) or "(none)"
        raise BadRequestError(
            f"Cannot sort by '{params.sort_by}'. Allowed columns: {allowed}."
        )
    if params.sort_dir not in ("asc", "desc"):
        raise BadRequestError("sort_dir must be either 'asc' or 'desc'.")

    column = getattr(model, params.sort_by)
    direction = asc if params.sort_dir == "asc" else desc
    return stmt.order_by(direction(column))


def paginate(
    db: Session,
    stmt: Select,
    model,
    params: PageParams,
    *,
    sortable: set[str] | None = None,
) -> Page:
    """
    Run a SELECT as a single page of results and return the standard envelope.

    Steps:
      1. Count the TOTAL matching rows (before slicing) - so we can report how
         many pages exist. We count with a subquery so any filters already on
         `stmt` are respected.
      2. Apply sorting (safelisted) and the LIMIT/OFFSET slice.
      3. Return {"items": [...], "pagination": {...}}.

    `sortable` is the set of column names the caller is allowed to sort by; the
    service passes it in so each entity controls its own safelist.
    """
    settings = get_settings()

    # Defensive clamp (the dependency also validates, but services may call this
    # directly). page >= 1, and 1 <= page_size <= API_MAX_PAGE_SIZE.
    if params.page < 1:
        raise BadRequestError("page must be 1 or greater.")
    if params.page_size < 1:
        raise BadRequestError("page_size must be 1 or greater.")
    if params.page_size > settings.max_page_size:
        raise BadRequestError(
            f"page_size cannot exceed {settings.max_page_size}."
        )

    # 1) total count of matching rows (respecting any WHERE already on stmt).
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # 2) sorting + slice.
    stmt = _apply_sorting(stmt, model, params, sortable or set())
    stmt = stmt.limit(params.page_size).offset(params.offset)
    items = list(db.scalars(stmt).all())

    # 3) build the pagination metadata.
    total_pages = (total + params.page_size - 1) // params.page_size if total else 0
    pagination = {
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": total_pages,
        "has_next": params.page < total_pages,
        "has_prev": params.page > 1 and total_pages > 0,
    }
    return Page(items=items, pagination=pagination)
