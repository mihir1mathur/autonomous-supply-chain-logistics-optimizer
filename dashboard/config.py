"""
============================================================================
DASHBOARD CONFIG  (Week 8)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  Holds the SETTINGS for the dashboard: WHERE the backend lives
  (DASHBOARD_API_BASE_URL), how long to wait for it (request timeout), and the
  display guardrails (default page size, chart row limits). Each setting can be
  overridden by an environment variable but has a safe default, so the dashboard
  runs with no .env at all.

WHY A SEPARATE CONFIG FILE (and why not hard-code the API URL everywhere)?
-------------------------------------------------------------------------
  Exactly the reasoning of the Week 4 api/config.py and the Week 3 database
  config: values that change between environments (your laptop vs. a deployed
  server) do not belong scattered through the code. Keeping the API base URL in
  ONE place means the dashboard can be pointed at a different backend by setting
  a single environment variable - no code change. The Week 8 rule "do not
  hardcode API URLs across files" is enforced here: every HTTP call in
  api_client.py reads this one base URL.

HOW IT WORKS (pydantic-settings, same as Week 4)
------------------------------------------------
  We reuse pydantic-settings' BaseSettings (already a project dependency). Each
  field is read from an environment variable with the DASHBOARD_ prefix (e.g.
  DASHBOARD_API_BASE_URL), falling back to the default written here. Because the
  fields are typed, a bad value fails loudly at startup rather than mid-request.

NO SECRETS HERE
  The dashboard needs no API keys and stores none. It only needs to know the
  backend URL. (Any LLM key for the optional Week 7 crewai mode lives on the
  BACKEND, never in the dashboard.)
============================================================================
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class DashboardSettings(BaseSettings):
    """
    All tunable dashboard settings in one typed object.

    Pydantic reads each field from an environment variable with the DASHBOARD_
    prefix (e.g. DASHBOARD_API_BASE_URL, DASHBOARD_REQUEST_TIMEOUT_SECONDS). If
    the variable is absent, the default written here is used.
    """

    model_config = SettingsConfigDict(
        env_prefix="DASHBOARD_",
        env_file=".env",
        extra="ignore",  # ignore unrelated variables (DATABASE_*, API_*, ...).
    )

    # ---- WHERE the backend is -------------------------------------------
    # The base URL of the FastAPI app (Weeks 4-7). Default matches the address
    # `uvicorn api.main:app --reload` serves locally. Point this elsewhere (e.g.
    # a deployed backend) with the DASHBOARD_API_BASE_URL environment variable.
    api_base_url: str = "http://127.0.0.1:8000"

    # ---- HOW LONG to wait for the backend -------------------------------
    # A per-request timeout (seconds). An agent decision can take a few seconds
    # (it runs a real optimization), so the default is generous. A timeout means
    # the dashboard shows a friendly "backend is slow / offline" message rather
    # than hanging forever.
    request_timeout_seconds: float = 30.0

    # ---- DISPLAY guardrails ---------------------------------------------
    # How many history rows to request per page by default. The backend caps a
    # page at API_MAX_PAGE_SIZE (100), so this is a display convenience.
    default_page_size: int = 50
    # The largest page the history page will let a user request (mirrors the
    # backend's own cap so the dashboard never asks for more than it can get).
    max_page_size: int = 100
    # The most rows any single chart will plot, so a huge history never renders
    # an unreadable or slow chart. Charts VISUALISE API data; they never compute.
    chart_row_limit: int = 200

    # ---- Demo mode flag --------------------------------------------------
    # A small convenience switch. When true, the UI shows extra explanatory
    # captions aimed at a first-time viewer (a guided walkthrough). It changes
    # ONLY presentation text - never any data or any API call.
    demo_mode: bool = True

    # ---- Identity (shown in the sidebar / page title) -------------------
    app_title: str = "Supply Chain & Logistics Optimizer - Analytics Dashboard"
    app_version: str = "0.8.0"  # 0.8 = Week 8.

    def health_url(self) -> str:
        """The full /health URL (a quick convenience for the status page)."""
        return f"{self.api_base_url.rstrip('/')}/health"


@lru_cache
def get_settings() -> DashboardSettings:
    """
    Return the ONE shared settings object.

    @lru_cache means the settings are read from the environment once and then
    reused, mirroring the Week 4 api/config.get_settings pattern.
    """
    return DashboardSettings()


# A module-level instance for code that just wants to read a value directly.
settings = get_settings()
