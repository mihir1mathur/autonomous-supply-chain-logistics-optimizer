"""
============================================================================
API ERRORS & EXCEPTION HANDLERS  (Week 4)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE IS FOR
---------------------
  When something goes wrong in an API, the caller should get a CLEAR, PREDICTABLE
  answer - not a stack trace, and definitely not raw SQL. This file defines:

    1. Our own error types (NotFoundError, DuplicateError, ...). Services
       `raise` these in plain English when a rule is broken.
    2. ONE consistent JSON shape every error is returned in, so any caller can
       always read `error.code` and `error.message`.
    3. Exception HANDLERS that catch those errors (and unexpected ones) and turn
       them into that JSON shape with the right HTTP status code.

WHAT ARE HTTP STATUS CODES? (zero-knowledge version)
----------------------------------------------------
  Every HTTP response carries a 3-digit code describing the outcome:
    2xx = success        (200 OK, 201 Created, 204 No Content)
    4xx = the CALLER did something wrong (their request was bad)
    5xx = the SERVER hit a problem (our fault)
  The codes this project uses:
    400 Bad Request        - the request itself is malformed / makes no sense.
    401 Unauthorized       - not logged in.       (future-ready: auth is Week 5+)
    403 Forbidden          - logged in but not allowed. (future-ready)
    404 Not Found          - the thing you asked for does not exist.
    409 Conflict           - clashes with current state (e.g. duplicate id).
    422 Unprocessable      - the data failed validation (wrong type/range).
    500 Internal Error     - an unexpected server-side failure.

WHY PRODUCTION APIs NEVER EXPOSE RAW SQL ERRORS
-----------------------------------------------
  A raw database error (table names, column names, the failing query) is two
  bad things at once: (1) it is useless to the caller, and (2) it leaks the
  internal structure of the system to anyone - a gift to an attacker. So we
  CATCH database errors, log the technical detail server-side (for us), and
  return a generic, safe message (for them). Callers get "an internal error
  occurred"; we keep the real detail in our logs.
============================================================================
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("api.errors")


# ===========================================================================
# 1) OUR OWN ERROR TYPES
#    Services raise these. Each carries the HTTP status code it should become,
#    a short machine-readable `code`, and a human-readable `message`.
# ===========================================================================
class AppError(Exception):
    """
    Base class for every error the application raises on purpose.

    status_code - the HTTP code this becomes (e.g. 404).
    code        - a short stable string a caller can branch on ("not_found").
    message     - a friendly, safe sentence describing what happened.
    """

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, details: object | None = None):
        super().__init__(message)
        self.message = message
        # Optional extra structured info (e.g. which field), safe to expose.
        self.details = details


class BadRequestError(AppError):
    """400 - the request is malformed or asks for something impossible."""

    status_code = 400
    code = "bad_request"


class NotFoundError(AppError):
    """404 - the requested resource does not exist."""

    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    """409 - the request conflicts with the current state of the data."""

    status_code = 409
    code = "conflict"


class DuplicateError(ConflictError):
    """
    409 - a more specific conflict: trying to create something whose id
    (or other unique field) already exists.
    """

    code = "duplicate"


class UnprocessableError(AppError):
    """422 - the data is well-formed but fails a business validation rule."""

    status_code = 422
    code = "unprocessable"


# ===========================================================================
# 2) THE ONE JSON SHAPE FOR EVERY ERROR
#    Everything the caller receives on failure looks like:
#      { "error": { "code": "...", "message": "...", "details": ... } }
# ===========================================================================
def _error_body(code: str, message: str, details: object | None = None) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


# ===========================================================================
# 3) THE HANDLERS - registered on the app in main.py via
#    register_exception_handlers(app).
# ===========================================================================
def register_exception_handlers(app: FastAPI) -> None:
    """Attach every exception handler to the FastAPI app in one call."""

    # --- Our own AppError family -> the JSON shape + its status code --------
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        # These are EXPECTED errors (we raised them on purpose), so log at INFO.
        logger.info("AppError %s on %s: %s", exc.code, request.url.path, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.details),
        )

    # --- Pydantic request validation failures (bad body/query) -> 422 ------
    # FastAPI raises RequestValidationError before our code even runs when the
    # incoming JSON has the wrong types/shape. We reshape it into OUR envelope.
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # exc.errors() lists each bad field; we pass a trimmed, safe version.
        details = [
            {
                "field": ".".join(str(p) for p in err.get("loc", []) if p != "body"),
                "problem": err.get("msg", ""),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_body(
                "validation_error",
                "One or more fields failed validation.",
                details,
            ),
        )

    # --- Duplicate / integrity problems from the database -> 409 -----------
    # e.g. inserting a row whose primary key already exists, or a foreign key
    # that points at a missing parent. We give a safe message, not the raw SQL.
    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
        logger.warning("IntegrityError on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=409,
            content=_error_body(
                "conflict",
                "The request conflicts with existing data (for example a "
                "duplicate id, or a reference to something that does not exist).",
            ),
        )

    # --- Any OTHER database error -> 500, with the raw detail HIDDEN --------
    @app.exception_handler(SQLAlchemyError)
    async def handle_db_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        # Log the REAL detail for us; return a generic message to the caller.
        logger.error("Database error on %s: %s", request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content=_error_body(
                "database_error",
                "An internal database error occurred. Please try again later.",
            ),
        )

    # --- Plain FastAPI/Starlette HTTPExceptions (e.g. raised by 3rd party) --
    # Reshape them into our envelope too, so the caller sees ONE format only.
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body("http_error", str(exc.detail)),
        )

    # --- The final safety net: anything we did not anticipate -> 500 -------
    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled error on %s: %s", request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content=_error_body(
                "internal_error",
                "An unexpected internal error occurred.",
            ),
        )
