"""
============================================================================
WEEK 6 - OPTIMIZATION EXECUTION VALIDATION
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SCRIPT DOES
---------------------
  Proves the Week 6 execution layer is CORRECT, not just that it runs. It drives
  the REST API and asserts the properties every run must have, marking each
  check PASS/FAIL so the output doubles as a Week 6 validation CHECKLIST:

    ENGINE        an optimization run completes and reports success.
    SCENARIOS     every scenario in the catalog executes without crashing.
    METRICS       all twelve KPIs are produced and are internally consistent
                  (utilization in 0..100%, orders + stockouts add up, runtime
                  and model size are non-negative).
    EVALUATION    a before-vs-after evaluation is produced, and optimizing the
                  'normal' scenario really does raise vehicle utilization.
    DATABASE      a run is STORED, is retrievable by id, appears in the history,
                  and is counted in the metrics aggregate; a /simulate is NOT.
    APIS          the scenarios / history / metrics endpoints return the right
                  shapes; Week 4 and Week 5 endpoints still work (no regressions).
    ERRORS        bad optimizer / scenario / warehouse / id / body all return a
                  clean 4xx, never a 500.

HOW THE REQUESTS ARE MADE
-------------------------
  Same as the Week 4/5 scripts: the in-process TestClient by default, or a real
  running server if API_BASE_URL is set.

PREREQUISITES
-------------
        pip install -r requirements.txt
        python database/init_db.py                 # creates optimization_runs
        python notebooks/week3_load_database.py
        python notebooks/week6_validation.py
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

from optimization.scenarios import SCENARIOS  # noqa: E402


def get_client():
    base_url = os.getenv("API_BASE_URL")
    if base_url:
        import httpx

        print(f"(using a real running server at {base_url})")
        return httpx.Client(base_url=base_url, timeout=120.0)

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


def validate_engine(client, results):
    banner("ENGINE  (a run completes and succeeds)")
    r = client.post("/optimization/run", json={"optimizer": "assignment", "scenario": "normal", "max_shipments": 40})
    results.append(check("assignment run returns 200", r.status_code == 200, f"got {r.status_code}"))
    d = r.json()
    results.append(check("run reports success", d.get("success") is True))
    results.append(check("run was persisted with a run_id", bool(d.get("run_id"))))


def validate_scenarios(client, results):
    banner("SCENARIOS  (every catalog scenario executes)")
    catalog = client.get("/optimization/scenarios").json()
    results.append(
        check(
            "scenarios endpoint lists the whole catalog",
            catalog["count"] == len(SCENARIOS),
            f"endpoint={catalog['count']} catalog={len(SCENARIOS)}",
        )
    )
    failures = []
    for key in SCENARIOS:
        r = client.post(
            "/optimization/simulate",
            json={"optimizer": "assignment", "scenario": key, "max_shipments": 30},
        )
        if r.status_code != 200 or not r.json().get("success"):
            failures.append(f"{key}({r.status_code})")
    results.append(
        check(
            f"all {len(SCENARIOS)} scenarios run without error",
            len(failures) == 0,
            f"failed: {failures}" if failures else "",
        )
    )


def validate_metrics(client, results):
    banner("METRICS  (all twelve KPIs, internally consistent)")
    d = client.post(
        "/optimization/simulate",
        json={"optimizer": "assignment", "scenario": "high_demand", "max_shipments": 50},
    ).json()
    m = d["metrics"]
    required = [
        "total_cost", "travel_distance_km", "vehicle_utilization",
        "warehouse_utilization", "inventory_holding_cost", "stockouts",
        "late_deliveries", "orders_fulfilled", "optimization_runtime_ms",
        "solver_status", "num_constraints", "num_variables",
    ]
    results.append(
        check(
            "all twelve KPI fields are present",
            all(k in m for k in required),
            f"missing: {[k for k in required if k not in m]}",
        )
    )
    results.append(
        check(
            "vehicle utilization is within 0..100%",
            0.0 <= m["vehicle_utilization"] <= 1.0,
            f"util={m['vehicle_utilization']}",
        )
    )
    results.append(
        check(
            "orders fulfilled + stockouts do not exceed shipments considered",
            m["orders_fulfilled"] + m["stockouts"] <= 50,
            f"orders={m['orders_fulfilled']} stockouts={m['stockouts']}",
        )
    )
    results.append(
        check("runtime is non-negative", m["optimization_runtime_ms"] >= 0.0)
    )
    results.append(
        check(
            "model size (variables/constraints) is positive",
            m["num_variables"] > 0 and m["num_constraints"] > 0,
            f"vars={m['num_variables']} constraints={m['num_constraints']}",
        )
    )
    results.append(
        check(
            "late deliveries never exceed orders fulfilled",
            m["late_deliveries"] <= m["orders_fulfilled"],
            f"late={m['late_deliveries']} orders={m['orders_fulfilled']}",
        )
    )


def validate_evaluation(client, results):
    banner("EVALUATION  (before vs after; optimizing raises utilization)")
    d = client.post(
        "/optimization/simulate",
        json={"optimizer": "assignment", "scenario": "normal", "max_shipments": 40},
    ).json()
    e = d.get("evaluation")
    results.append(check("an evaluation is produced", e is not None))
    if e:
        results.append(
            check(
                "optimizing improves (or holds) vehicle utilization vs baseline",
                e["utilization_improvement_percent"] >= 0.0,
                f"utilization change {e['utilization_improvement_percent']}%",
            )
        )
        results.append(
            check(
                "the optimizer uses no more vehicles than the naive baseline",
                d["metrics"]["vehicles_used"] <= e["before"]["vehicles_used"],
                f"after={d['metrics']['vehicles_used']} before={e['before']['vehicles_used']}",
            )
        )


def validate_database(client, results):
    banner("DATABASE  (runs are stored, retrievable, counted; simulate is not)")
    before_total = client.get("/optimization/history?page_size=1").json()["pagination"]["total"]
    before_agg = client.get("/optimization/metrics").json()["run_count"]

    run = client.post(
        "/optimization/run", json={"optimizer": "fleet", "scenario": "normal", "max_shipments": 30}
    ).json()
    run_id = run["run_id"]

    after_total = client.get("/optimization/history?page_size=1").json()["pagination"]["total"]
    after_agg = client.get("/optimization/metrics").json()["run_count"]

    results.append(check("storing a run increases the history total by 1", after_total == before_total + 1, f"{before_total}->{after_total}"))
    results.append(check("storing a run increases the metrics count by 1", after_agg == before_agg + 1, f"{before_agg}->{after_agg}"))

    one = client.get(f"/optimization/{run_id}")
    results.append(check("the stored run is retrievable by id", one.status_code == 200))
    if one.status_code == 200:
        body = one.json()
        results.append(
            check(
                "the stored KPIs match what the run returned",
                abs((body["total_cost"] or 0) - run["metrics"]["total_cost"]) < 1e-6,
                f"stored={body['total_cost']} returned={run['metrics']['total_cost']}",
            )
        )

    sim_before = client.get("/optimization/history?page_size=1").json()["pagination"]["total"]
    sim = client.post("/optimization/simulate", json={"optimizer": "assignment", "scenario": "normal"}).json()
    sim_after = client.get("/optimization/history?page_size=1").json()["pagination"]["total"]
    results.append(check("a /simulate run is NOT persisted", sim["run_id"] is None and sim_after == sim_before, f"run_id={sim['run_id']} {sim_before}->{sim_after}"))


def validate_apis_and_regressions(client, results):
    banner("APIS + REGRESSIONS  (shapes right; Weeks 4 & 5 still work)")
    hist = client.get("/optimization/history?page_size=3").json()
    results.append(check("history returns the standard {items, pagination} envelope", "items" in hist and "pagination" in hist))
    agg = client.get("/optimization/metrics").json()
    results.append(check("metrics aggregate has a run_count", "run_count" in agg))

    results.append(check("Week 5 /optimize/status still works", client.get("/optimize/status").status_code == 200))
    results.append(check("Week 5 /optimize/assignment still works", client.post("/optimize/assignment", json={"max_shipments": 20}).status_code == 200))
    results.append(check("Week 4 /vehicles still works", client.get("/vehicles?page_size=2").status_code == 200))
    results.append(check("Week 4 /health still works", client.get("/health").status_code == 200))


def validate_errors(client, results):
    banner("ERROR HANDLING  (clean 4xx, never a 500)")
    cases = [
        ("unknown optimizer -> 400", client.post("/optimization/run", json={"optimizer": "teleport"}), 400),
        ("unknown scenario -> 400", client.post("/optimization/run", json={"scenario": "apocalypse"}), 400),
        ("unknown warehouse -> 404", client.post("/optimization/run", json={"warehouse_id": "WH-NOPE-9999"}), 404),
        ("unknown run id -> 404", client.get("/optimization/RUN-does-not-exist"), 404),
        ("invalid sample_size (0) -> 422", client.post("/optimization/run", json={"optimizer": "warehouse", "sample_size": 0}), 422),
        ("reserved 'vrp' strategy -> 400", client.post("/optimization/run", json={"optimizer": "routes", "strategy": "vrp"}), 400),
    ]
    for description, resp, expected in cases:
        results.append(check(description, resp.status_code == expected, f"got {resp.status_code}"))


def main():
    banner("WEEK 6 - OPTIMIZATION EXECUTION VALIDATION")
    client = get_client()
    results = []

    validate_engine(client, results)
    validate_scenarios(client, results)
    validate_metrics(client, results)
    validate_evaluation(client, results)
    validate_database(client, results)
    validate_apis_and_regressions(client, results)
    validate_errors(client, results)

    banner("SUMMARY")
    passed = sum(results)
    total = len(results)
    print(f"  {passed}/{total} checks passed.")
    if passed == total:
        print("  Week 6 execution layer is correct: runs, scenarios, metrics,")
        print("  evaluation, storage, APIs and error handling all hold.")
    else:
        print("  Some checks failed - review the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
