"""
============================================================================
SYSTEM HEALTH PAGE
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS PAGE SHOWS
--------------------
  An enterprise-style operations board for the backend the dashboard depends on:
    * a single green/amber/red status banner (is the platform healthy?),
    * three service status cards (Backend, Optimization API, Agent API),
    * operational metrics (response time, latency, runtime, stored runs,
      scenarios, agent services),
    * the scenario catalog grouped by category, and
    * a recent-activity panel (last health check, last optimization, connection).

WHERE THE NUMBERS COME FROM (no computation here)
-------------------------------------------------
  Every value is read from the existing backend APIs (GET /health,
  /optimization/scenarios, /optimization/metrics, /optimization/history,
  /agents/status). Response-time / latency figures are the round-trip time of
  those same calls, measured client-side - the dashboard never invents a metric
  or bypasses the backend. If a service is down, the board reports it cleanly
  instead of crashing.
============================================================================
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import streamlit as st

from dashboard.api_client import APIClient, APIError
from dashboard.components.kpi_cards import kpi_row
from dashboard.config import get_settings
from dashboard.utils.formatting import format_datetime, format_int, format_ms, title_case

# Session-state keys (presentation state only - no backend involvement).
_CONNECTED_SINCE_KEY = "_health_connected_since"


def render(client: APIClient) -> None:
    """Render the System Health page."""
    settings = get_settings()
    st.header("System Health")
    st.caption(
        "Live operational status of the platform's backend services, refreshed "
        "each time this page loads."
    )

    checked_at = datetime.now(timezone.utc)

    # ---- Probe each service once and reuse the results downstream ---------
    backend = _probe(client.get_health)
    optimization = _probe(client.get_scenarios)
    agents = _probe(client.get_agent_status)
    probes = [backend, optimization, agents]
    ok_count = sum(1 for p in probes if p["ok"])

    # Remember when the backend first responded this session (for "connected
    # since"); this is presentation state, not a backend call.
    if backend["ok"] and _CONNECTED_SINCE_KEY not in st.session_state:
        st.session_state[_CONNECTED_SINCE_KEY] = checked_at

    # ---- Status banner ----------------------------------------------------
    if ok_count == len(probes):
        st.success("✅  All systems operational — the platform is healthy.")
    elif ok_count == 0:
        st.error("🔴  The backend is currently unavailable. Please try again shortly.")
    else:
        st.warning(f"🟠  Partial service — {ok_count} of {len(probes)} services are responding.")

    st.divider()

    # ---- Service status cards --------------------------------------------
    st.subheader("Service Status")
    _render_status_cards(backend, optimization, agents)

    st.divider()

    # ---- Operational metrics ---------------------------------------------
    st.subheader("Operational Metrics")
    _render_operational_metrics(client, backend, optimization, agents)

    st.divider()

    # ---- Scenario catalog -------------------------------------------------
    st.subheader("Scenario Catalog")
    _render_scenario_catalog(optimization)

    st.divider()

    # ---- Recent activity --------------------------------------------------
    st.subheader("Recent Activity")
    _render_recent_activity(client, checked_at, settings)


# ===========================================================================
# SECTIONS
# ===========================================================================
def _render_status_cards(backend: dict, optimization: dict, agents: dict) -> None:
    """Three KPI-style cards: title + icon + status + short description."""
    agent_count = len(agents["data"].get("agents", [])) if agents["ok"] and agents["data"] else 0
    mode = (agents["data"] or {}).get("orchestration_mode", "") if agents["ok"] else ""

    cards = [
        (backend, "Backend", "Healthy", "Offline", "Core API service"),
        (optimization, "Optimization API", "Online", "Unavailable", "Optimization engine endpoints"),
        (
            agents,
            "Agent API",
            "Running",
            "Unavailable",
            f"{agent_count}-agent crew · {mode} mode" if agents["ok"] else "Autonomous decision engine",
        ),
    ]

    columns = st.columns(3)
    for column, (probe, title, up_word, down_word, description) in zip(columns, cards):
        icon = "🟢" if probe["ok"] else "🔴"
        status = up_word if probe["ok"] else down_word
        with column:
            st.metric(title, f"{icon} {status}")
            st.caption(description)


def _render_operational_metrics(
    client: APIClient, backend: dict, optimization: dict, agents: dict
) -> None:
    """Two rows of KPI cards drawn from real backend values (with safe fallbacks)."""
    # Aggregate metrics (stored-run count + typical runtime).
    run_count = None
    try:
        metrics = client.get_metrics()
        run_count = metrics.get("run_count")
    except APIError:
        metrics = {}

    # The most recent stored run's solver runtime (one row, newest first).
    last_runtime_ms = None
    try:
        page = client.get_history(page=1, page_size=1, sort_by="created_at", sort_dir="desc")
        items = page.get("items", [])
        if items:
            last_runtime_ms = items[0].get("runtime_ms")
    except APIError:
        pass

    # Latencies are the measured round-trip times of the probes above.
    avg_latency = _mean_latency(backend, optimization, agents)
    scenario_count = (optimization["data"] or {}).get("count") if optimization["ok"] else None
    agent_count = len(agents["data"].get("agents", [])) if agents["ok"] and agents["data"] else None

    kpi_row(
        [
            ("Backend Response Time",
             format_ms(backend["latency_ms"] if backend["ok"] else None),
             "Round-trip time of the backend liveness check."),
            ("Average API Latency", format_ms(avg_latency),
             "Mean response time across the service checks."),
            ("Last Optimization Runtime", format_ms(last_runtime_ms),
             "Solver runtime of the most recent stored run."),
        ]
    )
    kpi_row(
        [
            ("Total Stored Runs", format_int(run_count),
             "Optimization runs recorded in the history."),
            ("Available Scenarios", format_int(scenario_count),
             "Business scenarios available in the catalog."),
            ("Agent Services Online", f"{agent_count} Agents" if agent_count else "Offline",
             "Autonomous agents ready to orchestrate a decision."),
        ]
    )


def _render_scenario_catalog(optimization: dict) -> None:
    """Show the catalog grouped by category as check-marked chips + a total."""
    if not optimization["ok"] or not optimization["data"]:
        st.info("The scenario catalog is currently unavailable.")
        return

    catalog = optimization["data"]
    scenarios = catalog.get("scenarios", [])
    count = catalog.get("count", len(scenarios))

    # Tally scenarios per category (display only - a simple count, not a KPI).
    per_category: dict[str, int] = {}
    for scenario in scenarios:
        category = scenario.get("category") or "other"
        per_category[category] = per_category.get(category, 0) + 1

    if not per_category:
        st.info("No scenarios in the catalog yet.")
        return

    ordered = sorted(per_category.items())
    columns = st.columns(len(ordered) + 1)
    columns[0].metric("Total Scenarios", format_int(count))
    for column, (category, n) in zip(columns[1:], ordered):
        column.markdown(f"**✓ {title_case(category)}**")
        column.caption(f"{n} scenario{'s' if n != 1 else ''}")


def _render_recent_activity(client: APIClient, checked_at: datetime, settings) -> None:
    """A compact panel of the latest platform activity and connection info."""
    # Last optimization request = newest stored run's created_at, if any.
    last_optimization_at = None
    try:
        page = client.get_history(page=1, page_size=1, sort_by="created_at", sort_dir="desc")
        items = page.get("items", [])
        if items:
            last_optimization_at = items[0].get("created_at")
    except APIError:
        pass

    connected_since = st.session_state.get(_CONNECTED_SINCE_KEY)

    columns = st.columns(4)
    columns[0].metric("Last Health Check", format_datetime(checked_at))
    columns[1].metric("Last Optimization Request", format_datetime(last_optimization_at))
    columns[2].metric("Backend Connected Since", format_datetime(connected_since))
    columns[3].metric("Current Environment", _environment_label(settings.api_base_url))


# ===========================================================================
# SMALL HELPERS (read-only, never raise)
# ===========================================================================
def _probe(call) -> dict:
    """
    Run one backend call, timing it, and return {ok, latency_ms, data}.

    Never raises: an APIError becomes ok=False with data=None, so the health
    board itself is immune to the very outages it reports.
    """
    start = time.perf_counter()
    try:
        data = call()
        return {"ok": True, "latency_ms": (time.perf_counter() - start) * 1000.0, "data": data}
    except APIError:
        return {"ok": False, "latency_ms": (time.perf_counter() - start) * 1000.0, "data": None}


def _mean_latency(*probes: dict) -> float | None:
    """Mean measured latency across the probes that responded (None if none did)."""
    values = [p["latency_ms"] for p in probes if p["ok"]]
    if not values:
        return None
    return sum(values) / len(values)


def _environment_label(base_url: str) -> str:
    """A human environment label derived from the backend URL (never shows the URL)."""
    low = (base_url or "").lower()
    if any(token in low for token in ("127.0.0.1", "localhost", "0.0.0.0")):
        return "Development"
    return "Production"
