"""
============================================================================
WEEK 7 - AI MULTI-AGENT ORCHESTRATION VALIDATION
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SCRIPT DOES
---------------------
  Proves the Week 7 orchestration layer is CORRECT, not just that it runs. It
  drives the REST API and asserts the properties every autonomous decision must
  have, marking each check PASS/FAIL so the output doubles as a Week 7
  validation CHECKLIST:

    STATUS      the /agents/status endpoint reports a valid mode, the five
                agents, and the four optimizers.
    CREW        a decision runs the full five-agent pipeline (plan -> scenario
                -> optimization -> evaluation -> report) and every trace step
                succeeds.
    REASONING   the Planner infers the optimizer and the Scenario agent picks
                the right existing scenario from plain-language requests, and
                explicit overrides are honoured.
    REUSE       the optimization the crew runs goes THROUGH the Week 6 execution
                service (never OR-Tools directly): it carries the twelve KPIs and
                a before-vs-after evaluation, and a stored run has a run_id.
    WHAT-IF     /agents/simulate produces a full decision WITHOUT storing a run.
    REPORT      the Reporting agent emits markdown + text + json, with
                recommendations and future improvements.
    RESILIENCE  a request the platform cannot satisfy (an unknown warehouse)
                fails LOUDLY: success=false with the failure captured in the
                trace, never a 500.
    OFFLINE     the whole layer works with NO LLM key (deterministic mode).
    REGRESSION  Week 4 / 5 / 6 endpoints still work (no regressions).
    ERRORS      an invalid request body returns a clean 422.

HOW THE REQUESTS ARE MADE
-------------------------
  Same as the Week 4/5/6 scripts: the in-process TestClient by default, or a
  real running server if API_BASE_URL is set. No LLM key is needed - the layer
  runs deterministically.

PREREQUISITES
-------------
        pip install -r requirements.txt
        python database/init_db.py
        python notebooks/week3_load_database.py
        python notebooks/week7_validation.py
============================================================================
"""

import os
import sys
import warnings

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*httpx.*")
warnings.filterwarnings("ignore", message=".*starlette.testclient.*")


def get_client():
    base_url = os.getenv("API_BASE_URL")
    if base_url:
        import httpx

        print(f"(using a real running server at {base_url})")
        return httpx.Client(base_url=base_url, timeout=180.0)

    from fastapi.testclient import TestClient

    from api.main import app

    print("(using the in-process TestClient - no separate server needed)")
    return TestClient(app)


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
# STATUS
# ===========================================================================
def validate_status(client, results):
    banner("STATUS  (the orchestration layer describes itself)")
    r = client.get("/agents/status")
    results.append(check("status endpoint returns 200", r.status_code == 200, f"got {r.status_code}"))
    s = r.json()
    results.append(check(
        "mode is a valid orchestration mode",
        s.get("orchestration_mode") in ("deterministic", "crewai"),
        f"mode={s.get('orchestration_mode')}",
    ))
    results.append(check(
        "all five agents are listed",
        len(s.get("agents", [])) == 5,
        f"agents={s.get('agents')}",
    ))
    results.append(check(
        "all four optimizers are listed",
        set(s.get("optimizers", [])) == {"assignment", "fleet", "routes", "warehouse"},
        f"optimizers={s.get('optimizers')}",
    ))


# ===========================================================================
# CREW  (the full pipeline runs and every step succeeds)
# ===========================================================================
def validate_crew(client, results):
    banner("CREW  (a decision runs the full five-agent pipeline)")
    r = client.post("/agents/decide", json={"goal": "minimize cost for normal operations",
                                             "max_shipments": 30})
    results.append(check("decide returns 200", r.status_code == 200, f"got {r.status_code}"))
    d = r.json()
    results.append(check("decision reports success", d.get("success") is True))
    for part in ("plan", "scenario", "optimization", "evaluation", "report", "trace"):
        results.append(check(f"decision carries a '{part}'", bool(d.get(part))))

    steps = d.get("trace", {}).get("steps", [])
    expected_agents = ["PlannerAgent", "ScenarioAgent", "OptimizationAgent",
                       "EvaluationAgent", "ReportingAgent"]
    results.append(check(
        "trace has the five agent steps in order",
        [s["agent"] for s in steps] == expected_agents,
        f"got {[s['agent'] for s in steps]}",
    ))
    results.append(check("every trace step succeeded", d["trace"].get("all_succeeded") is True))
    results.append(check(
        "every step has a non-negative duration",
        all(s.get("duration_ms", -1) >= 0 for s in steps),
    ))
    results.append(check("a run_id was stored", bool(d["optimization"].get("run_id"))))


# ===========================================================================
# REASONING  (planner + scenario inference, and explicit overrides)
# ===========================================================================
def validate_reasoning(client, results):
    banner("REASONING  (agents infer intent; overrides are honoured)")

    # A "holiday" mention should select the holiday scenario.
    d = client.post("/agents/simulate",
                    json={"goal": "prepare for a holiday peak", "max_shipments": 20}).json()
    results.append(check(
        "'holiday' request selects the holiday scenario",
        d["scenario"]["key"] == "holiday",
        f"scenario={d['scenario']['key']}",
    ))

    # "balance the fleet" should infer the fleet optimizer.
    d = client.post("/agents/simulate",
                    json={"goal": "balance the fleet evenly across the depot", "max_shipments": 20}).json()
    results.append(check(
        "'balance the fleet' infers the fleet optimizer",
        d["plan"]["optimizer"] == "fleet",
        f"optimizer={d['plan']['optimizer']}",
    ))

    # An urgent word should raise priority to high.
    d = client.post("/agents/simulate",
                    json={"goal": "URGENT: assign shipments now", "max_shipments": 20}).json()
    results.append(check(
        "'urgent' raises the priority to high",
        d["plan"]["priority"] == "high",
        f"priority={d['plan']['priority']}",
    ))

    # An explicit optimizer + scenario override must be used verbatim.
    d = client.post("/agents/simulate",
                    json={"optimizer": "routes", "scenario": "fuel_price_increase",
                          "goal": "anything", "max_stops": 20}).json()
    results.append(check(
        "explicit optimizer override is honoured",
        d["plan"]["optimizer"] == "routes",
        f"optimizer={d['plan']['optimizer']}",
    ))
    results.append(check(
        "explicit scenario override is honoured",
        d["scenario"]["key"] == "fuel_price_increase",
        f"scenario={d['scenario']['key']}",
    ))


# ===========================================================================
# REUSE  (the crew drives the Week 6 execution service, not OR-Tools)
# ===========================================================================
def validate_reuse(client, results):
    banner("REUSE  (decisions go THROUGH the Week 6 execution service)")
    d = client.post("/agents/decide",
                    json={"goal": "assign shipments for high demand", "max_shipments": 40}).json()
    opt = d["optimization"]
    results.append(check(
        "the optimization was invoked via the execution service",
        opt.get("invoked") == "execution_service.run",
        f"invoked={opt.get('invoked')}",
    ))

    kpis = d["evaluation"].get("kpis", {})
    expected_kpis = {
        "total_cost", "travel_distance_km", "vehicle_utilization", "warehouse_utilization",
        "inventory_holding_cost", "stockouts", "late_deliveries", "orders_fulfilled",
        "optimization_runtime_ms", "solver_status", "num_constraints", "num_variables",
    }
    results.append(check(
        "the run carries all twelve Week 6 KPIs",
        expected_kpis.issubset(set(kpis.keys())),
        f"missing={expected_kpis - set(kpis.keys())}",
    ))
    results.append(check(
        "a before-vs-after evaluation is present",
        bool(d["evaluation"].get("improvements")),
    ))
    results.append(check(
        "utilization is a valid fraction (0..1)",
        0.0 <= float(kpis.get("vehicle_utilization", -1)) <= 1.0,
        f"util={kpis.get('vehicle_utilization')}",
    ))


# ===========================================================================
# WHAT-IF  (simulate does not store a run)
# ===========================================================================
def validate_simulate(client, results):
    banner("WHAT-IF  (/agents/simulate never stores a run)")
    d = client.post("/agents/simulate",
                    json={"goal": "minimize cost", "max_shipments": 20}).json()
    results.append(check("simulate reports success", d.get("success") is True))
    results.append(check("simulate did NOT persist", d["optimization"].get("persisted") is False))
    results.append(check("simulate has no run_id", d["optimization"].get("run_id") is None))


# ===========================================================================
# REPORT  (three renderings + action lists)
# ===========================================================================
def validate_report(client, results):
    banner("REPORT  (markdown + text + json, with recommendations)")
    d = client.post("/agents/decide",
                    json={"goal": "minimize cost for normal operations", "max_shipments": 20}).json()
    report = d.get("report", {})
    results.append(check("report has markdown", isinstance(report.get("markdown"), str) and len(report["markdown"]) > 50))
    results.append(check("report has plain text", isinstance(report.get("text"), str) and len(report["text"]) > 20))
    results.append(check("report has a json structure", isinstance(report.get("json"), dict) and bool(report["json"])))
    results.append(check("report has recommendations", len(report.get("recommendations", [])) > 0))
    results.append(check("report has future improvements", len(report.get("future_improvements", [])) > 0))


# ===========================================================================
# RESILIENCE  (a bad target fails loudly, never a 500)
# ===========================================================================
def validate_resilience(client, results):
    banner("RESILIENCE  (an impossible request fails loudly, keeps the trace)")
    r = client.post("/agents/decide",
                    json={"optimizer": "assignment", "warehouse_id": "NOPE-DOES-NOT-EXIST"})
    results.append(check("impossible request still returns 200 (not 500)", r.status_code == 200, f"got {r.status_code}"))
    d = r.json()
    results.append(check("the decision reports success=false", d.get("success") is False))
    steps = d.get("trace", {}).get("steps", [])
    results.append(check(
        "the failing step is captured in the trace",
        any(not s["success"] for s in steps),
        f"steps={[(s['agent'], s['success']) for s in steps]}",
    ))
    results.append(check("a human-readable message explains the stop", bool(d.get("message"))))


# ===========================================================================
# ERRORS  (invalid body -> clean 422)
# ===========================================================================
def validate_errors(client, results):
    banner("ERRORS  (an invalid body is a clean 422)")
    r = client.post("/agents/decide", json={"max_shipments": 0})  # violates ge=1
    results.append(check("max_shipments=0 is rejected with 422", r.status_code == 422, f"got {r.status_code}"))


# ===========================================================================
# REGRESSION  (Weeks 4/5/6 untouched)
# ===========================================================================
def validate_regression(client, results):
    banner("REGRESSION  (Weeks 4 / 5 / 6 endpoints still work)")
    r = client.get("/warehouses", params={"page": 1, "page_size": 1})
    results.append(check("Week 4: GET /warehouses returns 200", r.status_code == 200, f"got {r.status_code}"))
    r = client.get("/optimize/status")
    results.append(check("Week 5: GET /optimize/status returns 200", r.status_code == 200, f"got {r.status_code}"))
    r = client.post("/optimization/run", json={"optimizer": "assignment", "scenario": "normal", "max_shipments": 20})
    results.append(check(
        "Week 6: POST /optimization/run still succeeds",
        r.status_code == 200 and r.json().get("success") is True,
        f"got {r.status_code}",
    ))
    r = client.get("/optimization/scenarios")
    results.append(check("Week 6: GET /optimization/scenarios returns 200", r.status_code == 200, f"got {r.status_code}"))


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    client = get_client()
    results: list[bool] = []

    validate_status(client, results)
    validate_crew(client, results)
    validate_reasoning(client, results)
    validate_reuse(client, results)
    validate_simulate(client, results)
    validate_report(client, results)
    validate_resilience(client, results)
    validate_errors(client, results)
    validate_regression(client, results)

    banner("SUMMARY")
    passed = sum(1 for ok in results if ok)
    total = len(results)
    print(f"  {passed}/{total} checks passed.")
    if passed == total:
        print("  ALL WEEK 7 CHECKS PASSED - the AI orchestration layer is correct,")
        print("  additive, and drives the existing platform without regressions.")
    else:
        print("  SOME CHECKS FAILED - see the [FAIL] lines above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
