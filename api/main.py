"""
============================================================================
FASTAPI APPLICATION ENTRY POINT  (Week 4)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE IS
-----------------
  This is the "front door" of the backend. It creates the FastAPI application,
  configures it, plugs in every router, and installs the error handlers. When
  you run the server, THIS is the object it runs.

HOW TO RUN THE API (from the project root)
------------------------------------------
    # 1. make sure the Week 3 database exists and is loaded:
    python database/init_db.py
    python notebooks/week3_load_database.py
    # 2. start the API server:
    uvicorn api.main:app --reload
    # 3. open the automatic, interactive documentation in a browser:
    #      http://127.0.0.1:8000/docs        (Swagger UI)
    #      http://127.0.0.1:8000/redoc       (ReDoc)
    #      http://127.0.0.1:8000/openapi.json (the raw OpenAPI spec)

WHAT IS "uvicorn api.main:app"?
  uvicorn is the SERVER that runs the app. "api.main:app" means "in the module
  api/main.py, use the variable named `app`". `--reload` restarts the server
  automatically whenever you edit a file (handy while developing).

WHAT GETS WIRED UP HERE (in order)
  1. Create the FastAPI app with the title/version/description from config.
  2. Add CORS middleware (which browser origins may call the API).
  3. Register the exception handlers (clean JSON errors, no raw SQL leaks).
  4. Add a root "/" and a "/health" endpoint (quick liveness checks).
  5. Include all seven entity routers.

DATABASE NOTE
  This file does NOT create tables or connect at import time. The database is
  the Week 3 one; the API only opens a session per request (see get_db). If
  PostgreSQL is down, importing/starting the app still works - only the
  endpoints that touch the database will error (cleanly) until it is back.
============================================================================
"""

import os
import sys

# Make the PROJECT ROOT importable so `import models` / `import database` (the
# Week 3 packages) resolve when the app is started as `uvicorn api.main:app`
# from the project root. This mirrors the pattern used by the Week 3 scripts.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.routers import all_routers
from api.utils.exceptions import register_exception_handlers


def create_app() -> FastAPI:
    """
    Build and return the configured FastAPI application.

    Using a factory function (instead of building the app at module top level)
    keeps setup in one clear place and makes it easy for tests later to build a
    fresh app. main.py still exposes a module-level `app` for uvicorn to find.
    """
    app = FastAPI(
        title=settings.title,
        version=settings.version,
        description=settings.description,
        # These are the default doc URLs; listed explicitly for clarity.
        docs_url="/docs",       # Swagger UI (interactive "try it out").
        redoc_url="/redoc",     # ReDoc (clean reading view).
        openapi_url="/openapi.json",  # the machine-readable OpenAPI spec.
    )

    # ---- CORS: which browsers may call this API --------------------------
    # A browser blocks a web page from calling an API on a different origin
    # unless the API says it is allowed. This middleware sends that permission.
    # "*" (any origin) is fine for local development; tighten before deploy.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- Clean error responses (see utils/exceptions.py) -----------------
    register_exception_handlers(app)

    # ---- Small non-database endpoints for quick checks -------------------
    @app.get("/", tags=["Meta"], summary="API welcome / pointer to the docs")
    def root() -> dict:
        """A friendly landing response pointing at the interactive docs."""
        return {
            "name": settings.title,
            "version": settings.version,
            "docs": "/docs",
            "openapi": "/openapi.json",
            "message": "Welcome to the Supply Chain & Logistics Optimizer API.",
        }

    @app.get("/health", tags=["Meta"], summary="Liveness check")
    def health() -> dict:
        """
        Returns 200 with a tiny payload if the app is running. Deliberately does
        NOT touch the database, so it stays fast and is a pure liveness signal.
        (A deeper 'readiness' check that pings PostgreSQL can be added later.)
        """
        return {"status": "ok"}

    # ---- Include every entity router -------------------------------------
    for entity_router in all_routers:
        app.include_router(entity_router)

    return app


# The application object uvicorn runs: `uvicorn api.main:app --reload`.
app = create_app()
