"""
============================================================================
API CONFIG  (Week 4)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  It holds the SETTINGS for the API layer: the title and version shown in the
  documentation, the default/maximum page sizes for list endpoints, and which
  browser origins may call the API (CORS). Each setting can be overridden by an
  environment variable (from the local .env file) but has a safe default, so
  the API runs even with no .env at all.

WHY A SEPARATE CONFIG FILE (and why not hard-code these)?
---------------------------------------------------------
  The same reasoning as the Week 3 database config: values that might change
  between environments (your laptop vs. a cloud server) do not belong buried
  inside the code. Keeping them in one settings object means one place to look
  and one place to change - and secrets can come from the environment, never
  from source control.

HOW IT WORKS (pydantic-settings)
--------------------------------
  We use pydantic-settings' BaseSettings. It reads each field from an
  environment variable of the same name (prefixed with API_), falling back to
  the default written here. python-dotenv already loaded the .env file back in
  the Week 3 database config, so those variables are available here too.

NOTE: this file is ONLY about API behaviour. The DATABASE connection settings
still live in database/config.py (Week 3) and are reused unchanged - we do not
duplicate them here.
============================================================================
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class APISettings(BaseSettings):
    """
    All tunable API settings in one typed object.

    Pydantic reads each field from an environment variable with the API_
    prefix (e.g. API_TITLE, API_DEFAULT_PAGE_SIZE). If the variable is absent,
    the default written here is used. Because the fields are typed, a bad value
    (e.g. API_MAX_PAGE_SIZE="abc") fails loudly at startup instead of causing a
    confusing error later.
    """

    # model_config replaces the old "class Config" in Pydantic v2. env_prefix
    # means "look for API_TITLE, API_VERSION, ..." in the environment.
    model_config = SettingsConfigDict(
        env_prefix="API_",
        env_file=".env",
        extra="ignore",  # ignore unrelated variables (e.g. DATABASE_*).
    )

    # ---- Documentation identity (shown at the top of Swagger UI) ----------
    title: str = "Supply Chain & Logistics Optimizer API"
    version: str = "0.4.0"  # 0.4 = Week 4; bumped as the project grows.
    description: str = (
        "REST API over the Week 3 PostgreSQL database. It exposes the supply "
        "chain entities (customers, warehouses, inventory, vehicles, routes, "
        "orders, disruptions) with full CRUD, filtering, sorting, searching, "
        "and pagination. Built on the reused Week 3 SQLAlchemy models and CRUD "
        "layer."
    )

    # ---- Pagination guardrails (used by every list endpoint) -------------
    # Default page size when the caller does not ask for one.
    default_page_size: int = 20
    # Hard upper limit so a caller cannot request a million rows at once.
    max_page_size: int = 100

    # ---- CORS (which browser origins may call this API) ------------------
    # A single string like "*" or "http://localhost:3000,http://localhost:5173".
    # We keep it as a raw string and split it in main.py, which keeps parsing
    # simple and beginner-obvious.
    cors_origins: str = "*"

    def cors_origin_list(self) -> list[str]:
        """Turn the comma-separated cors_origins string into a clean list."""
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> APISettings:
    """
    Return the ONE shared settings object.

    @lru_cache means the settings are read from the environment once and then
    reused, instead of being re-parsed on every request. FastAPI endpoints get
    these settings through dependency injection (see dependencies.py), which is
    also what makes them trivial to override in tests later.
    """
    return APISettings()


# A module-level instance for code that just wants to read a value directly
# (e.g. main.py building the app). Endpoints should prefer the injected form.
settings = get_settings()
