"""
============================================================================
DASHBOARD API CLIENT   -- the ONLY seam between the UI and FastAPI
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE IS
-----------------
  The single place in the dashboard that talks to the backend over HTTP. Every
  page and component goes THROUGH this client; none of them build URLs or call
  httpx themselves. This mirrors the agent layer's "one tool seam" idea: there is
  exactly one door to the platform, so the rule "the dashboard never bypasses
  the backend services" is easy to see and impossible to break by accident.

WHY A DEDICATED CLIENT (and not scattered requests)
---------------------------------------------------
  * ONE base URL (from dashboard/config.py) - point at a different backend by
    changing one environment variable.
  * ONE error style - if the backend is down, slow, or returns an error, the
    client raises a small, friendly APIError with a human message instead of a
    raw stack trace. Pages catch APIError and show that message, so the
    dashboard degrades gracefully rather than crashing.
  * NO backend logic - this client only makes requests and returns the parsed
    JSON. It never computes a KPI, never runs an optimizer, never touches the
    database. All of that already lives behind the backend services.

THE METHODS MAP 1:1 TO THE EXISTING ENDPOINTS
---------------------------------------------
    GET  /health                    -> get_health()
    GET  /optimization/scenarios    -> get_scenarios()
    GET  /optimization/history      -> get_history(...)
    GET  /optimization/metrics      -> get_metrics(...)
    GET  /optimization/{run_id}     -> get_run(run_id)
    POST /optimization/run          -> run_optimization(payload)
    POST /optimization/simulate     -> simulate_optimization(payload)
    POST /agents/decide             -> agent_decide(payload)
    POST /agents/simulate           -> agent_simulate(payload)
    GET  /agents/status             -> get_agent_status()

  Nothing here is Streamlit-specific, so this module imports cleanly even if
  Streamlit is not installed (the validation suite relies on that).
============================================================================
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import httpx

from dashboard.config import DashboardSettings, get_settings


class APIError(Exception):
    """
    A friendly error the pages can show to the user.

    It always carries a short, human-readable `message` (safe to print in the
    UI) and, when available, the HTTP `status_code` and the endpoint `path` that
    failed - handy for the System Health page.
    """

    def __init__(self, message: str, *, status_code: int | None = None, path: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.path = path


class APIClient:
    """
    A thin, reusable HTTP client for the Supply Chain Optimizer backend.

    Construct it once and reuse it (see the module-level get_client()); it keeps
    a persistent httpx.Client (connection pooling) and remembers the time of the
    last successful request, which the System Health page displays.
    """

    def __init__(self, settings: DashboardSettings | None = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.api_base_url.rstrip("/")
        self.timeout = self.settings.request_timeout_seconds
        # A reusable client (keeps TCP connections warm across requests).
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
        # Updated on every successful call; None until the first one succeeds.
        self.last_success_at: datetime | None = None

    # -----------------------------------------------------------------------
    # THE ONE PLACE requests are made and errors are turned into APIError
    # -----------------------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """
        Make one HTTP request and return the parsed JSON body.

        Any transport problem (backend offline, DNS failure, timeout) or an HTTP
        error status is converted into a friendly APIError. This is the single
        choke point that keeps the whole dashboard resilient: a page only has to
        catch APIError, never a zoo of httpx exceptions.
        """
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.ConnectError:
            raise APIError(
                f"Cannot reach the backend at {self.base_url}. Is it running? "
                f"Start it with:  uvicorn api.main:app --reload",
                path=path,
            )
        except httpx.TimeoutException:
            raise APIError(
                f"The backend at {self.base_url} did not respond within "
                f"{self.timeout:.0f}s. It may be busy or offline.",
                path=path,
            )
        except httpx.HTTPError as exc:  # any other transport-level problem
            raise APIError(f"Network error talking to the backend: {exc}", path=path)

        # A non-2xx status: surface the backend's own error message if it sent
        # one (the API error envelope), otherwise a generic line.
        if response.status_code >= 400:
            detail = _extract_error_detail(response)
            raise APIError(
                f"The backend returned {response.status_code} for {path}: {detail}",
                status_code=response.status_code,
                path=path,
            )

        # Success: record the time and return the JSON body.
        self.last_success_at = datetime.now(timezone.utc)
        try:
            return response.json()
        except ValueError:
            raise APIError(f"The backend returned a non-JSON response for {path}.", path=path)

    # -----------------------------------------------------------------------
    # META
    # -----------------------------------------------------------------------
    def get_health(self) -> dict:
        """GET /health - a quick liveness check ({'status': 'ok'})."""
        return self._request("GET", "/health")

    def is_backend_up(self) -> bool:
        """
        Return True if /health responds, False otherwise (never raises).

        Handy for the sidebar connection badge, which must not crash the page
        just because the backend happens to be down.
        """
        try:
            self.get_health()
            return True
        except APIError:
            return False

    # -----------------------------------------------------------------------
    # OPTIMIZATION EXECUTION  (the execution layer, /optimization/*)
    # -----------------------------------------------------------------------
    def get_scenarios(self) -> dict:
        """GET /optimization/scenarios - the scenario catalog."""
        return self._request("GET", "/optimization/scenarios")

    def get_metrics(self, *, scenario: str | None = None, optimizer: str | None = None) -> dict:
        """GET /optimization/metrics - aggregate KPIs across the stored runs."""
        params = _clean_params({"scenario": scenario, "optimizer": optimizer})
        return self._request("GET", "/optimization/metrics", params=params)

    def get_history(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        sort_by: str | None = None,
        sort_dir: str = "desc",
        search: str | None = None,
        scenario: str | None = None,
        optimizer: str | None = None,
        warehouse_id: str | None = None,
        solver_status: str | None = None,
    ) -> dict:
        """
        GET /optimization/history - a page of stored runs (filter/sort/paginate).

        Returns the backend's paginated envelope: {"items": [...],
        "pagination": {...}}. All filtering, sorting and paging is done by the
        backend; the dashboard only passes the query parameters through.
        """
        params = _clean_params(
            {
                "page": page,
                "page_size": page_size,
                "sort_by": sort_by,
                "sort_dir": sort_dir,
                "search": search,
                "scenario": scenario,
                "optimizer": optimizer,
                "warehouse_id": warehouse_id,
                "solver_status": solver_status,
            }
        )
        return self._request("GET", "/optimization/history", params=params)

    def get_run(self, run_id: str) -> dict:
        """GET /optimization/{run_id} - one stored run by id."""
        return self._request("GET", f"/optimization/{run_id}")

    def run_optimization(self, payload: dict | None = None) -> dict:
        """POST /optimization/run - run + measure + evaluate + STORE one run."""
        return self._request("POST", "/optimization/run", json=payload or {})

    def simulate_optimization(self, payload: dict | None = None) -> dict:
        """POST /optimization/simulate - a what-if run that is NOT stored."""
        return self._request("POST", "/optimization/simulate", json=payload or {})

    # -----------------------------------------------------------------------
    # AI ORCHESTRATION  (the agent layer, /agents/*)
    # -----------------------------------------------------------------------
    def get_agent_status(self) -> dict:
        """GET /agents/status - the orchestration mode, agents, and LLM info."""
        return self._request("GET", "/agents/status")

    def agent_decide(self, payload: dict | None = None) -> dict:
        """POST /agents/decide - one autonomous decision, storing the run."""
        return self._request("POST", "/agents/decide", json=payload or {})

    def agent_simulate(self, payload: dict | None = None) -> dict:
        """POST /agents/simulate - one autonomous what-if, NOT stored."""
        return self._request("POST", "/agents/simulate", json=payload or {})


# ===========================================================================
# SMALL HELPERS
# ===========================================================================
def _clean_params(params: dict) -> dict:
    """Drop keys whose value is None so we never send empty query parameters."""
    return {k: v for k, v in params.items() if v is not None}


def _extract_error_detail(response: httpx.Response) -> str:
    """
    Pull a human-readable message out of an error response.

    The API error envelope uses a top-level "detail" (a string or a list of
    validation errors). We format whatever is there into one short line.
    """
    try:
        body = response.json()
    except ValueError:
        return response.text[:200] or "(no error body)"

    detail = body.get("detail") if isinstance(body, dict) else None
    if detail is None:
        return str(body)[:200]
    if isinstance(detail, str):
        return detail
    # A 422 validation error is a list of {loc, msg, ...} dicts.
    if isinstance(detail, list):
        msgs = []
        for item in detail:
            if isinstance(item, dict):
                loc = ".".join(str(p) for p in item.get("loc", []) if p != "body")
                msgs.append(f"{loc}: {item.get('msg', '')}".strip(": "))
            else:
                msgs.append(str(item))
        return "; ".join(msgs) or "validation error"
    return str(detail)[:200]


@lru_cache
def get_client() -> APIClient:
    """
    Return the ONE shared API client.

    @lru_cache gives a single reused client (and a single `last_success_at`
    clock) for the whole dashboard process, mirroring the backend service
    singletons. Streamlit pages call this on every rerun and get the same
    client back cheaply.
    """
    return APIClient()
