"""
============================================================================
WEEK 8 - ANALYTICS DASHBOARD DEMO
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SCRIPT DOES
---------------------
  A friendly, printed walk-through of the Week 8 dashboard. It is meant to be
  READ as much as run. It:

    * prints exactly how to start the backend and the dashboard,
    * (optionally) calls the SAME api_client the dashboard uses to verify the
      key endpoints are answering, so you know the dashboard will have data,
    * explains which pages to open, in what order, and
    * gives a guided demo flow for a first-time viewer walkthrough.

  It uses the dashboard's own api_client, so it exercises the identical seam the
  UI does - if this script can read the endpoints, the dashboard can too.

HOW TO RUN
----------
        pip install -r requirements.txt            # adds streamlit, plotly
        # (optional but recommended) start the backend so the checks pass:
        uvicorn api.main:app --reload
        python notebooks/week8_dashboard_demo.py   # this walkthrough
        streamlit run dashboard/app.py             # the actual dashboard

  Point the dashboard/demo at a different backend by setting
  DASHBOARD_API_BASE_URL (default http://127.0.0.1:8000).
============================================================================
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard.api_client import APIError, get_client
from dashboard.config import get_settings


def banner(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ===========================================================================
# HOW TO START EVERYTHING
# ===========================================================================
def print_startup():
    settings = get_settings()
    banner("HOW TO START THE SYSTEM")
    print("  1. Start the backend (Weeks 4-7):")
    print("       uvicorn api.main:app --reload")
    print()
    print("  2. Start the dashboard (Week 8):")
    print("       streamlit run dashboard/app.py")
    print()
    print(f"  The dashboard reads the backend at: {settings.api_base_url}")
    print("  (override with the DASHBOARD_API_BASE_URL environment variable).")


# ===========================================================================
# VERIFY THE ENDPOINTS THE DASHBOARD USES
# ===========================================================================
def verify_endpoints():
    banner("VERIFY THE ENDPOINTS (via the dashboard's own api_client)")
    client = get_client()

    if not client.is_backend_up():
        print(f"  Backend not reachable at {client.base_url}.")
        print("  Start it with 'uvicorn api.main:app --reload', then re-run this demo.")
        print("  (The dashboard itself will still open - it just shows friendly")
        print("   'backend offline' messages until the backend is up.)")
        return False

    print(f"  Backend is UP at {client.base_url}.\n")

    # Each check mirrors a page's first call.
    try:
        metrics = client.get_metrics()
        print(f"  [Overview]      /optimization/metrics -> {metrics.get('run_count')} stored run(s)")

        scenarios = client.get_scenarios()
        print(f"  [Scenarios]     /optimization/scenarios -> {scenarios.get('count')} scenario(s)")

        history = client.get_history(page=1, page_size=5)
        total = history.get("pagination", {}).get("total", 0)
        print(f"  [History]       /optimization/history -> {total} run(s) total")

        status = client.get_agent_status()
        print(f"  [Agents]        /agents/status -> mode='{status.get('orchestration_mode')}', "
              f"{len(status.get('agents', []))} agents")
    except APIError as exc:
        print(f"  A check failed: {exc.message}")
        return False

    return True


# ===========================================================================
# A LIVE AGENT DECISION (what the Agent Decisions page does)
# ===========================================================================
def demo_agent_decision():
    banner("SAMPLE AGENT DECISION (what-if, not stored)")
    client = get_client()
    if not client.is_backend_up():
        print("  (skipped - backend offline)")
        return

    goal = "Optimize deliveries for a holiday rush and reduce late deliveries."
    print(f"  Request: {goal}\n")
    try:
        decision = client.agent_simulate({"goal": goal, "max_shipments": 30})
    except APIError as exc:
        print(f"  Decision failed: {exc.message}")
        return

    plan = decision.get("plan", {})
    scenario = decision.get("scenario", {})
    evaluation = decision.get("evaluation", {})
    trace = decision.get("trace", {})

    print(f"  mode      : {decision.get('mode')}")
    print(f"  success   : {decision.get('success')}")
    print(f"  plan      : optimizer={plan.get('optimizer')} priority={plan.get('priority')}")
    print(f"  scenario  : {scenario.get('key')} ({scenario.get('name')})")
    print(f"  verdict   : {evaluation.get('verdict')} - {evaluation.get('headline')}")
    print("  trace     :")
    for step in trace.get("steps", []):
        mark = "ok " if step.get("success") else "FAIL"
        print(f"     [{mark}] {step.get('agent'):<18} {step.get('duration_ms', 0):>8.1f} ms")
    print("\n  (In the dashboard, this same decision is shown with KPI cards, a")
    print("   drawn execution trace, and the Markdown/Text/JSON report tabs.)")


# ===========================================================================
# THE GUIDED DEMO FLOW
# ===========================================================================
def print_demo_flow():
    banner("GUIDED DEMO FLOW (open the pages in this order)")
    steps = [
        ("Overview",
         "The at-a-glance KPIs (stored runs, cost, utilization) + the "
         "architecture and the five-agent flow."),
        ("Optimization History",
         "Browse/filter stored runs; pick one to see its KPIs, its before/after "
         "evaluation, and its scenario changes; export CSV/JSON."),
        ("Scenario Analysis",
         "Compare stored runs across scenarios; optionally SIMULATE a scenario "
         "as a what-if (not stored)."),
        ("Agent Decisions",
         "Type a plain-English request and click Decide (store) or Simulate "
         "(what-if). Read the plan, verdict, trace and report."),
        ("Agent trace",
         "On that page, follow Planner -> Scenario -> Optimization -> Evaluation "
         "-> Reporting, each step timed and pass/fail (the workflow is auditable)."),
        ("Reports",
         "See the report in Markdown | Text | JSON and export it."),
        ("System Health",
         "Confirm the backend + APIs are up, and see how to run everything."),
    ]
    for i, (page, what) in enumerate(steps, start=1):
        print(f"  {i}. {page}")
        print(f"       {what}")


def main():
    print_startup()
    backend_up = verify_endpoints()
    if backend_up:
        demo_agent_decision()
    print_demo_flow()

    banner("DONE")
    print("  Now launch the dashboard and follow the flow above:")
    print("       streamlit run dashboard/app.py")
    print("  The dashboard is a presentation layer: it consumes the existing")
    print("  Week 6 /optimization and Week 7 /agents APIs and never bypasses them.")


if __name__ == "__main__":
    main()
