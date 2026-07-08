"""
============================================================================
SHARED DEPENDENCIES (DEPENDENCY INJECTION)  (Week 4)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT IS "DEPENDENCY INJECTION"? (zero-knowledge version)
--------------------------------------------------------
  Some things almost every endpoint needs - a database session, the pagination
  settings from the query string. Instead of each endpoint building those
  itself (repetitive and easy to get wrong), it just DECLARES what it needs and
  FastAPI provides ("injects") it. That is dependency injection: the endpoint
  asks for a session; FastAPI creates one, hands it over, and cleans it up.

  Analogy: a chef (the endpoint) does not go shopping for ingredients. They ask
  for "two eggs" and the kitchen (FastAPI) hands them over already prepared. If
  the kitchen changes where eggs come from, the chef's recipe does not change.

WHY THIS MATTERS FOR THE PROJECT (future-ready)
-----------------------------------------------
  Because endpoints only DECLARE their needs, we can change how a need is met
  in ONE place and every endpoint follows. Later weeks lean on this heavily:
    - Week 6 Redis: wrap get_db-backed reads with a cache dependency.
    - Auth (future): add a `current_user` dependency to protect endpoints.
  None of the endpoints have to be rewritten - we just swap what gets injected.

WHAT THIS FILE PROVIDES
-----------------------
  get_db            - one database session per request (re-exported from
                      api/database.py so endpoints import it from one place).
  pagination_params - reads ?page, ?page_size, ?sort_by, ?sort_dir from the URL
                      and returns a validated PageParams object.
  search_query      - reads an optional ?search=... free-text term.
============================================================================
"""

from fastapi import Depends, Query

from api.config import APISettings, get_settings
from api.database import get_db  # re-exported so routers import it from here.
from api.utils.pagination import PageParams

__all__ = ["get_db", "pagination_params", "search_query", "get_settings"]


def pagination_params(
    page: int = Query(
        1,
        ge=1,
        description="Which page of results to return (starts at 1).",
    ),
    page_size: int = Query(
        None,
        ge=1,
        description="How many rows per page. Defaults to API_DEFAULT_PAGE_SIZE; "
        "capped at API_MAX_PAGE_SIZE.",
    ),
    sort_by: str | None = Query(
        None,
        description="Column to sort by. Each endpoint documents which columns "
        "are allowed.",
    ),
    sort_dir: str = Query(
        "asc",
        pattern="^(asc|desc)$",
        description="Sort direction: 'asc' (A->Z, low->high) or 'desc'.",
    ),
    settings: APISettings = Depends(get_settings),
) -> PageParams:
    """
    Turn the pagination-related query-string parameters into one validated
    PageParams object that every list endpoint accepts.

    - page defaults to 1 (ge=1 rejects 0 or negatives with a clean 422).
    - page_size defaults to the configured default, and is clamped to the
      configured maximum so a caller can never request an unbounded page.
    - sort_dir is restricted to asc/desc by the regex pattern.
    """
    effective_size = page_size if page_size is not None else settings.default_page_size
    if effective_size > settings.max_page_size:
        effective_size = settings.max_page_size

    return PageParams(
        page=page,
        page_size=effective_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


def search_query(
    search: str | None = Query(
        None,
        min_length=1,
        max_length=200,
        description="Optional free-text search. Each endpoint documents which "
        "text columns it searches (case-insensitive, partial match).",
    ),
) -> str | None:
    """Return the trimmed ?search=... term, or None if not provided."""
    if search is None:
        return None
    cleaned = search.strip()
    return cleaned or None
