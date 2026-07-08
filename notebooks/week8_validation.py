"""
============================================================================
WEEK 8 - ANALYTICS DASHBOARD VALIDATION
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SCRIPT DOES
---------------------
  Proves the Week 8 dashboard is CORRECT and RESILIENT, not just that the files
  exist. It imports every dashboard module, exercises the pure helpers, and
  confirms the dashboard degrades gracefully when the backend is offline -
  marking each check PASS/FAIL so the output doubles as a Week 8 CHECKLIST:

    IMPORTS     the dashboard package, config, api_client and utils all import.
    CONFIG      settings load, with the expected defaults (API base URL, ...).
    API CLIENT  the client is creatable and exposes one method per endpoint;
                its error type (APIError) is a plain Exception the pages catch.
    COMPONENTS  every reusable component module imports.
    PAGES       every page module imports and exposes a render(client) entry.
    FORMATTING  the formatting helpers behave (esp. utilization shown as %).
    EXPORT      the CSV / JSON / Markdown export builders produce valid bytes.
    RESILIENCE  a client pointed at a dead backend does NOT crash: is_backend_up
                returns False and calls raise a friendly APIError.
    FILES       every required Week 8 file / folder exists (dashboard, docs,
                notes/Week8).
    LIVE (opt)  if a backend is reachable, a few endpoints are sanity-checked
                through the real api_client.

  It NEVER requires the backend or the database to be up (the LIVE section is
  optional and skipped cleanly if the backend is offline), so it is safe to run
  anywhere - matching the Week 6 / Week 7 validation style.

HOW TO RUN
----------
        pip install -r requirements.txt      # adds streamlit, plotly
        python notebooks/week8_validation.py
  (Optional: start the backend first - uvicorn api.main:app --reload - to also
   exercise the LIVE section against real data.)
============================================================================
"""

import os
import sys
import warnings

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*ScriptRunContext.*")


# ===========================================================================
# SMALL TEST HELPERS  (same look as the Week 6 / 7 validation scripts)
# ===========================================================================
def banner(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def check(description, passed, detail=""):
    mark = "PASS" if passed else "FAIL"
    print(f"  [{mark}] {description}")
    if detail:
        print(f"         {detail}")
    return bool(passed)


# ===========================================================================
# IMPORTS
# ===========================================================================
def validate_imports(results):
    banner("IMPORTS  (the dashboard package imports cleanly)")
    try:
        import dashboard  # noqa: F401
        import dashboard.config  # noqa: F401
        import dashboard.api_client  # noqa: F401
        from dashboard.utils import export, formatting  # noqa: F401

        results.append(check("dashboard package + config + api_client import", True))
        results.append(check("dashboard.utils (formatting, export) import", True))
    except Exception as exc:  # pragma: no cover - a failed import is the failure
        results.append(check("dashboard core modules import", False, repr(exc)))


# ===========================================================================
# CONFIG
# ===========================================================================
def validate_config(results):
    banner("CONFIG  (settings load with sensible defaults)")
    from dashboard.config import DashboardSettings, get_settings

    settings = get_settings()
    results.append(check("get_settings() returns a DashboardSettings",
                         isinstance(settings, DashboardSettings)))
    results.append(check("api_base_url has a value",
                         bool(settings.api_base_url), f"api_base_url={settings.api_base_url}"))
    results.append(check("request timeout is positive",
                         settings.request_timeout_seconds > 0,
                         f"timeout={settings.request_timeout_seconds}"))
    results.append(check("health_url() is built from the base url",
                         settings.health_url().endswith("/health"),
                         settings.health_url()))


# ===========================================================================
# API CLIENT
# ===========================================================================
def validate_api_client(results):
    banner("API CLIENT  (creatable; one method per endpoint; friendly errors)")
    from dashboard.api_client import APIClient, APIError, get_client

    client = get_client()
    results.append(check("get_client() returns an APIClient", isinstance(client, APIClient)))
    results.append(check("APIError is an Exception subclass", issubclass(APIError, Exception)))

    required_methods = [
        "get_health", "get_scenarios", "get_history", "get_metrics", "get_run",
        "run_optimization", "simulate_optimization",
        "agent_decide", "agent_simulate", "get_agent_status",
    ]
    missing = [m for m in required_methods if not callable(getattr(client, m, None))]
    results.append(check("client exposes a method for every endpoint",
                         not missing, f"missing={missing}"))


# ===========================================================================
# COMPONENTS
# ===========================================================================
def validate_components(results):
    banner("COMPONENTS  (every reusable UI module imports)")
    modules = [
        "dashboard.components.kpi_cards",
        "dashboard.components.charts",
        "dashboard.components.tables",
        "dashboard.components.filters",
        "dashboard.components.agent_trace",
        "dashboard.components.report_viewer",
    ]
    for name in modules:
        try:
            __import__(name)
            results.append(check(f"import {name}", True))
        except Exception as exc:
            results.append(check(f"import {name}", False, repr(exc)))


# ===========================================================================
# PAGES
# ===========================================================================
def validate_pages(results):
    banner("PAGES  (every page imports and exposes render(client))")
    import importlib

    pages = [
        "dashboard.pages.overview",
        "dashboard.pages.optimization_history",
        "dashboard.pages.scenario_analysis",
        "dashboard.pages.agent_decisions",
        "dashboard.pages.reports",
        "dashboard.pages.system_health",
    ]
    for name in pages:
        try:
            module = importlib.import_module(name)
            has_render = callable(getattr(module, "render", None))
            results.append(check(f"{name} imports and has render()", has_render))
        except Exception as exc:
            results.append(check(f"{name} imports", False, repr(exc)))

    # Importing app.py must NOT run the app or require the backend.
    try:
        import dashboard.app  # noqa: F401
        results.append(check("dashboard.app imports without launching / needing a backend", True))
    except Exception as exc:
        results.append(check("dashboard.app imports", False, repr(exc)))


# ===========================================================================
# FORMATTING
# ===========================================================================
def validate_formatting(results):
    banner("FORMATTING  (helpers behave; utilization shown as a percentage)")
    from dashboard.utils import formatting as f

    results.append(check("fraction_to_percent(0.767) == '76.7%'",
                         f.fraction_to_percent(0.767) == "76.7%",
                         f.fraction_to_percent(0.767)))
    results.append(check("format_percent_value(27.5, signed=True) == '+27.5%'",
                         f.format_percent_value(27.5, signed=True) == "+27.5%",
                         f.format_percent_value(27.5, signed=True)))
    results.append(check("format_currency(1234.5) == '$1,234.50'",
                         f.format_currency(1234.5) == "$1,234.50",
                         f.format_currency(1234.5)))
    results.append(check("format_ms(2500) switches to seconds",
                         f.format_ms(2500) == "2.50 s", f.format_ms(2500)))
    results.append(check("format_int(None) is the missing dash",
                         f.format_int(None) == f.MISSING))
    results.append(check("safe_get reads a nested value",
                         f.safe_get({"a": {"b": 5}}, "a", "b") == 5))


# ===========================================================================
# EXPORT
# ===========================================================================
def validate_export(results):
    banner("EXPORT  (CSV / JSON / Markdown builders produce valid bytes)")
    import json

    from dashboard.utils import export as e

    rows = [
        {"run_id": "r1", "scenario": "normal", "total_cost": 10.0, "metrics": {"x": 1}},
        {"run_id": "r2", "scenario": "holiday", "total_cost": 20.0},
    ]
    csv_bytes = e.history_to_csv_bytes(rows)
    csv_text = csv_bytes.decode("utf-8")
    results.append(check("history CSV has a header + one line per row",
                         csv_text.splitlines()[0].startswith("run_id") and len(csv_text.splitlines()) == 3,
                         f"lines={len(csv_text.splitlines())}"))

    run_json = e.run_to_json_bytes({"run_id": "r1", "metrics": {"total_cost": 10}})
    results.append(check("run JSON export is valid JSON",
                         json.loads(run_json).get("run_id") == "r1"))

    report = {"markdown": "# Title\n\nbody", "json": {"a": 1}, "recommendations": ["x"]}
    md = e.report_to_markdown_bytes(report)
    results.append(check("report Markdown export carries the markdown text",
                         md.decode("utf-8").startswith("# Title")))
    rep_json = e.report_to_json_bytes(report)
    results.append(check("report JSON export is valid JSON",
                         json.loads(rep_json).get("json", {}).get("a") == 1))


# ===========================================================================
# RESILIENCE  (a dead backend never crashes the dashboard)
# ===========================================================================
def validate_resilience(results):
    banner("RESILIENCE  (a dead backend is handled gracefully, never a crash)")
    from dashboard.api_client import APIClient, APIError
    from dashboard.config import DashboardSettings

    # A client pointed at a port nothing is listening on.
    dead = APIClient(DashboardSettings(api_base_url="http://127.0.0.1:59999",
                                       request_timeout_seconds=2.0))

    results.append(check("is_backend_up() returns False (does not raise)",
                         dead.is_backend_up() is False))

    raised_friendly = False
    try:
        dead.get_metrics()
    except APIError as exc:
        raised_friendly = bool(exc.message)
    except Exception:
        raised_friendly = False
    results.append(check("a call to a dead backend raises a friendly APIError",
                         raised_friendly))


# ===========================================================================
# FILES  (every required Week 8 artifact exists)
# ===========================================================================
def validate_files(results):
    banner("FILES  (required dashboard files, docs, and notes exist)")

    required = [
        # dashboard package
        "dashboard/__init__.py", "dashboard/app.py", "dashboard/config.py",
        "dashboard/api_client.py",
        "dashboard/components/__init__.py", "dashboard/components/kpi_cards.py",
        "dashboard/components/charts.py", "dashboard/components/tables.py",
        "dashboard/components/filters.py", "dashboard/components/agent_trace.py",
        "dashboard/components/report_viewer.py",
        "dashboard/pages/__init__.py", "dashboard/pages/overview.py",
        "dashboard/pages/optimization_history.py", "dashboard/pages/scenario_analysis.py",
        "dashboard/pages/agent_decisions.py", "dashboard/pages/reports.py",
        "dashboard/pages/system_health.py",
        "dashboard/utils/__init__.py", "dashboard/utils/formatting.py",
        "dashboard/utils/export.py",
        # docs
        "docs/dashboard_architecture.md", "docs/dashboard_user_guide.md",
        "docs/week8_dashboard_summary.md",
        # scripts
        "notebooks/week8_dashboard_demo.py", "notebooks/week8_validation.py",
    ]
    for rel in required:
        results.append(check(f"exists: {rel}", os.path.exists(os.path.join(PROJECT_ROOT, rel))))

    # notes/Week8 folder + the thirteen note files.
    notes_dir = os.path.join(PROJECT_ROOT, "notes", "Week8")
    results.append(check("notes/Week8 folder exists", os.path.isdir(notes_dir)))
    note_files = [
        "00_INDEX.txt", "01_Dashboard_Overview.txt", "02_Streamlit_Basics.txt",
        "03_API_Client_Reuse.txt", "04_KPI_Cards.txt", "05_Charts_And_Trends.txt",
        "06_Optimization_History.txt", "07_Scenario_Comparison.txt",
        "08_Agent_Trace_Viewer.txt", "09_Report_Viewer.txt",
        "10_Interview_Explanation.txt", "11_Recruiter_Explanation.txt",
        "12_Revision_Sheet.txt",
    ]
    for name in note_files:
        results.append(check(f"notes/Week8/{name} exists",
                             os.path.exists(os.path.join(notes_dir, name))))


# ===========================================================================
# LIVE  (optional - only if a backend is reachable)
# ===========================================================================
def validate_live(results):
    banner("LIVE  (optional: sanity-check a few endpoints if the backend is up)")
    from dashboard.api_client import get_client

    client = get_client()
    if not client.is_backend_up():
        print(f"  (skipped - no backend reachable at {client.base_url}; "
              f"start it with 'uvicorn api.main:app --reload' to run this section)")
        return

    metrics = client.get_metrics()
    results.append(check("GET /optimization/metrics returns a run_count",
                         "run_count" in metrics, f"run_count={metrics.get('run_count')}"))
    scenarios = client.get_scenarios()
    results.append(check("GET /optimization/scenarios returns a catalog",
                         scenarios.get("count", 0) >= 1, f"count={scenarios.get('count')}"))
    status = client.get_agent_status()
    results.append(check("GET /agents/status lists the five agents",
                         len(status.get("agents", [])) == 5, f"agents={status.get('agents')}"))


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    results = []

    validate_imports(results)
    validate_config(results)
    validate_api_client(results)
    validate_components(results)
    validate_pages(results)
    validate_formatting(results)
    validate_export(results)
    validate_resilience(results)
    validate_files(results)
    validate_live(results)

    banner("SUMMARY")
    passed = sum(1 for ok in results if ok)
    total = len(results)
    print(f"  {passed}/{total} checks passed.")
    if passed == total:
        print("  ALL WEEK 8 CHECKS PASSED - the dashboard imports, formats, exports,")
        print("  and degrades gracefully; it is additive and consumes the backend APIs.")
    else:
        print("  SOME CHECKS FAILED - see the [FAIL] lines above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
