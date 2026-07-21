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


def validate_reproducibility(client, results):
    """
    Prove the Week 6 benchmark is REPRODUCIBLE: deterministic warehouse choice
    and loading, one pinned warehouse reused across a whole sweep, a stable input
    fingerprint, and identical stable business fields across two runs (with
    runtime explicitly excluded from the comparison).
    """
    banner("REPRODUCIBILITY  (deterministic warehouse + solver; stable metrics)")

    # Reproducibility requires deterministic solver mode; turn it on here so the
    # earlier checks are unaffected. The solvers read this fresh on every solve.
    os.environ["BENCHMARK_DETERMINISTIC"] = "true"

    from sqlalchemy import func, select

    from api.services.execution_service import execution_service
    from database.connection import get_session
    from models import DeliveryRoute, Vehicle
    from notebooks.week6_benchmark_runner import (
        IGNORED_FIELDS,
        MAX_SHIPMENTS,
        BENCHMARK_SCENARIOS,
        compute_input_fingerprint,
        extract_stable_fields,
        resolve_benchmark_warehouse,
        run_benchmark,
    )

    # --- 1) deterministic warehouse tie-breaking -------------------------
    with get_session() as db:
        w1 = execution_service.resolve_dispatch_warehouse(db, None)
        w2 = execution_service.resolve_dispatch_warehouse(db, None)
        rows = db.execute(
            select(Vehicle.warehouse_id, func.count())
            .where(Vehicle.availability_status == "available")
            .group_by(Vehicle.warehouse_id)
        ).all()
        counts = {wid: c for wid, c in rows if wid is not None}
        max_count = max(counts.values()) if counts else 0
        tied_top = sorted(w for w, c in counts.items() if c == max_count)
        expected = None
        for w in tied_top:
            has_route = db.execute(
                select(DeliveryRoute.route_id).where(DeliveryRoute.warehouse_id == w).limit(1)
            ).first()
            if has_route is not None:
                expected = w
                break
        # --- 2) ordered warehouse loading -------------------------------
        wh_inputs = execution_service._load_all_warehouses(db)
        loaded_ids = [w.warehouse_id for w in wh_inputs]

    results.append(
        check(
            "default dispatch warehouse resolves deterministically (smallest id wins ties)",
            w1 == w2 == expected,
            f"resolved={w1}/{w2} expected={expected} tied_top={tied_top}",
        )
    )
    results.append(
        check(
            "warehouses are loaded in a deterministic (sorted) order",
            loaded_ids == sorted(loaded_ids),
            f"{loaded_ids[:3]}... (n={len(loaded_ids)})",
        )
    )

    # --- 3) one warehouse reused across every scenario -------------------
    runs1 = run_benchmark(client, w1)
    runs2 = run_benchmark(client, w1)
    reused = (
        len(runs1) == len(BENCHMARK_SCENARIOS)
        and all(r["warehouse_id"] == w1 for r in runs1)
    )
    results.append(
        check(
            "the pinned benchmark warehouse is reused across all scenarios",
            reused,
            f"warehouses seen={sorted({r['warehouse_id'] for r in runs1})} count={len(runs1)}",
        )
    )

    # --- 4) stable input fingerprint present -----------------------------
    fp1 = compute_input_fingerprint(w1, MAX_SHIPMENTS)["sha256"]
    fp2 = compute_input_fingerprint(w1, MAX_SHIPMENTS)["sha256"]
    results.append(
        check(
            "input fingerprint is present and stable (64-char SHA-256)",
            fp1 == fp2 and len(fp1) == 64,
            f"{fp1}",
        )
    )

    # --- 5) two-run stable-field equality --------------------------------
    stable1 = [extract_stable_fields(r) for r in runs1]
    stable2 = [extract_stable_fields(r) for r in runs2]
    results.append(
        check(
            "stable business fields are identical across two benchmark runs",
            stable1 == stable2,
            "" if stable1 == stable2 else "stable fields differed between runs",
        )
    )

    # --- 6) runtime is excluded from the equality comparison -------------
    stable_keys = set(stable1[0]["metrics"]) | set(stable1[0]["evaluation"]) | set(stable1[0])
    runtime_excluded = all(f not in stable_keys for f in IGNORED_FIELDS)
    # And the ignored fields really can differ while the stable comparison holds.
    runtimes_seen = {r["metrics"]["optimization_runtime_ms"] for r in runs1 + runs2}
    results.append(
        check(
            "runtime / run_id / created_at are excluded from the reproducibility comparison",
            runtime_excluded and stable1 == stable2,
            f"ignored={IGNORED_FIELDS}; distinct runtimes observed={len(runtimes_seen)}",
        )
    )


def validate_report_semantics(client, results):
    """
    Unit-check the benchmark REPORTING helpers so the report's wording can never
    misrepresent the (unchanged) numbers: zero/tie observation handling, an
    honest OPTIMAL/FEASIBLE summary, cost-increase phrasing for a negative
    reduction, no false distance-reduction claim, and dependency-qualified
    reproducibility wording.
    """
    banner("REPORT SEMANTICS  (honest wording over the unchanged numbers)")

    from notebooks.week6_benchmark_runner import (
        OBJECTIVE_NOTE,
        UTILIZATION_FORMULA_NOTE,
        _signed_pct,
        cost_change_label,
        cost_change_percent,
        describe_max_observation,
        distance_note,
        normal_scenario_observation,
        reproducibility_note,
        status_summary_text,
    )

    def _run(scenario, **metrics):
        base = {
            "stockouts": 0,
            "late_deliveries": 0,
            "total_cost": 0.0,
            "vehicle_utilization": 0.0,
            "solver_status": "OPTIMAL",
        }
        base.update(metrics)
        return {"scenario": scenario, "metrics": base, "evaluation": {}}

    # --- 1) all-zero observation handling --------------------------------
    all_zero = [_run("normal"), _run("holiday"), _run("demand_spike")]
    zero_obs = describe_max_observation(
        all_zero, "stockouts", "stockout count",
        "No stockouts occurred in any tested scenario.",
    )
    results.append(
        check(
            "all-zero observation reports that none occurred",
            zero_obs == "No stockouts occurred in any tested scenario.",
            zero_obs,
        )
    )

    # --- 2) ties in the maximum observation ------------------------------
    tied = [
        _run("normal", late_deliveries=0),
        _run("holiday", late_deliveries=50),
        _run("demand_spike", late_deliveries=50),
        _run("supplier_delay", late_deliveries=30),
    ]
    tie_obs = describe_max_observation(
        tied, "late_deliveries", "late-delivery count",
        "No late deliveries occurred in any tested scenario.",
    )
    results.append(
        check(
            "tied maximum observation lists all tied scenarios",
            tie_obs == "Highest late-delivery count: holiday and demand_spike, tied at 50.",
            tie_obs,
        )
    )

    # --- 3) correct OPTIMAL/FEASIBLE summary -----------------------------
    status_runs = [
        _run("normal", solver_status="OPTIMAL"),
        _run("holiday", solver_status="OPTIMAL"),
        _run("demand_spike", solver_status="OPTIMAL"),
        _run("vehicle_failure", solver_status="FEASIBLE"),
        _run("supplier_delay", solver_status="OPTIMAL"),
    ]
    summary = status_summary_text(status_runs)
    expected_summary = (
        "4/5 scenarios returned OPTIMAL. The constrained vehicle_failure scenario "
        "returned a reproducible FEASIBLE solution within the configured solver time limit."
    )
    results.append(
        check(
            "solver-status summary is truthful (4/5 OPTIMAL, names the FEASIBLE case)",
            summary == expected_summary and "5/5" not in summary,
            summary,
        )
    )

    # --- 4) negative cost reduction -> explicit cost increase ------------
    inc = cost_change_label(-46.8)
    dec = cost_change_label(3.2)
    none = cost_change_label(0.0)
    results.append(
        check(
            "negative cost reduction is reported as an explicit cost increase",
            cost_change_percent(-46.8) == 46.8
            and inc == "+46.8% (cost increase)"
            and dec == "-3.2% (cost decrease)"
            and none == "0.0% (no change)",
            f"{inc} | {dec} | {none}",
        )
    )

    # --- 5) no false distance-improvement claim when change is zero ------
    zero_dist = [
        {"scenario": "normal", "metrics": {}, "evaluation": {"distance_reduction_percent": 0.0}},
        {"scenario": "holiday", "metrics": {}, "evaluation": {"distance_reduction_percent": 0.0}},
    ]
    dnote = distance_note(zero_dist)
    results.append(
        check(
            "distance note claims no route-distance reduction when change is zero",
            "does not demonstrate route-distance reduction" in dnote
            and "no distance savings are claimed" in dnote,
            dnote,
        )
    )

    # --- 6) dependency-version-qualified reproducibility wording ---------
    rnote = reproducibility_note()
    results.append(
        check(
            "reproducibility wording is dependency-version-qualified (not 'every machine')",
            "Python version" in rnote
            and "OR-Tools version" in rnote
            and "every machine" not in rnote
            and "run_id" in rnote,
            "",
        )
    )

    # --- 7) optimized 'normal' is NOT called the unoptimized baseline ----
    norm_obs = normal_scenario_observation(
        [_run("normal", total_cost=109551.39, vehicle_utilization=0.598)]
    )
    results.append(
        check(
            "optimized normal scenario is not labelled the unoptimized baseline",
            norm_obs.startswith("Normal optimized scenario:")
            and "vehicle utilization is" in norm_obs
            and "109551.39" in norm_obs
            and "59.8%" in norm_obs
            and "baseline" not in norm_obs.lower(),
            norm_obs,
        )
    )

    # --- 8) utilization change uses relative percent, not percentage points
    #       The field is (after-before)/before*100 (a relative % increase), so it
    #       is documented and displayed in percent - never mislabelled as "pp".
    util_display = _signed_pct(34.7)
    results.append(
        check(
            "utilization change is documented as a relative percent (not percentage points)",
            "relative percentage increase" in UTILIZATION_FORMULA_NOTE
            and "/ baseline_utilization" in UTILIZATION_FORMULA_NOTE
            and "not in percentage points" in UTILIZATION_FORMULA_NOTE
            and util_display == "+34.7%"
            and "pp" not in util_display,
            f"{util_display}; note={UTILIZATION_FORMULA_NOTE[:60]}...",
        )
    )

    # --- 9) revised cost trade-off wording is present -------------------
    results.append(
        check(
            "cost note uses the explicit trade-off wording (no 'not a regression')",
            "explicit trade-off in favor of capacity-feasible consolidation and "
            "fulfillment rather than direct monetary-cost minimization" in OBJECTIVE_NOTE
            and "not a regression" not in OBJECTIVE_NOTE,
            "",
        )
    )


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
    validate_reproducibility(client, results)
    validate_report_semantics(client, results)

    banner("SUMMARY")
    passed = sum(results)
    total = len(results)
    print(f"  {passed}/{total} checks passed.")
    if passed == total:
        print("  Week 6 execution layer is correct: runs, scenarios, metrics,")
        print("  evaluation, storage, APIs, error handling and reproducibility all hold.")
    else:
        print("  Some checks failed - review the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
