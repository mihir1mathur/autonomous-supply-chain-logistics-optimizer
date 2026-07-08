"""
============================================================================
WEEK 6 - OPTIMIZATION EXECUTION DEMO  (happy paths)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SCRIPT DOES
---------------------
  Exercises the Week 6 optimization EXECUTION layer end to end through the REST
  API and prints clean, explained output. Where Week 5 could RUN a solver, Week
  6 runs it under a SCENARIO, MEASURES the run's KPIs, EVALUATES it against an
  un-optimized baseline, and STORES it - then reads the history back.

    1. GET  /optimization/scenarios   the "what if" catalog
    2. POST /optimization/run         run + measure + evaluate + STORE a run
    3. POST /optimization/simulate    the same as a throwaway what-if (not stored)
    4. GET  /optimization/history     the runs we just stored
    5. GET  /optimization/{id}        one stored run in full
    6. GET  /optimization/metrics     aggregate KPIs across the stored runs

  For each run it reports the numbers the Week 6 goals ask for: total cost,
  travel distance, vehicle + warehouse utilization, inventory holding cost,
  stockouts, late deliveries, orders fulfilled, runtime, solver status, and the
  model size (variables / constraints) - plus the before-vs-after improvement.

HOW THE REQUESTS ARE MADE (no separate server needed)
-----------------------------------------------------
  Same pattern as the Week 4/5 scripts: FastAPI's in-process TestClient by
  default (one command, no running server), or a real running server if the
  environment variable API_BASE_URL is set.

PREREQUISITES
-------------
  The Week 3 database must exist and be loaded, and the Week 6 table created:
        pip install -r requirements.txt
        python database/init_db.py                 # creates optimization_runs
        python notebooks/week3_load_database.py
  Then run:
        python notebooks/week6_execution_demo.py
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
    """Return a TestClient (default) or httpx client against API_BASE_URL."""
    base_url = os.getenv("API_BASE_URL")
    if base_url:
        import httpx

        print(f"(using a real running server at {base_url})")
        return httpx.Client(base_url=base_url, timeout=60.0)

    from fastapi.testclient import TestClient

    from api.main import app

    print("(using the in-process TestClient - no separate server needed)")
    return TestClient(app)


def banner(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def step(title):
    print("\n" + "-" * 70)
    print(title)
    print("-" * 70)


def show_metrics(m):
    """Print the twelve KPIs of a run in a compact block."""
    print(f"    total cost            : {m['total_cost']}")
    print(f"    travel distance (km)  : {m['travel_distance_km']}")
    print(f"    vehicle utilization   : {m['vehicle_utilization']*100:.1f}%")
    print(f"    warehouse utilization : {m['warehouse_utilization']*100:.1f}%")
    print(f"    inventory holding cost: {m['inventory_holding_cost']}")
    print(f"    stockouts             : {m['stockouts']}")
    print(f"    late deliveries       : {m['late_deliveries']}")
    print(f"    orders fulfilled      : {m['orders_fulfilled']}")
    print(f"    runtime (ms)          : {m['optimization_runtime_ms']}")
    print(f"    solver status         : {m['solver_status']}")
    print(f"    variables / constraints: {m['num_variables']} / {m['num_constraints']}"
          f"  ({'estimated' if m['model_size_is_estimated'] else 'decision count'})")


def main():
    banner("WEEK 6 - OPTIMIZATION EXECUTION DEMO (happy paths)")
    client = get_client()

    # ---- 1) SCENARIOS -----------------------------------------------------
    step("GET /optimization/scenarios  (the 'what if' catalog)")
    print("  Each scenario is a set of changes applied to the optimizer's inputs.")
    sc = client.get("/optimization/scenarios").json()
    print(f"  {sc['count']} scenarios available:")
    for s in sc["scenarios"]:
        print(f"    {s['key']:<20} [{s['category']}]  {s['name']}")

    # ---- 2) RUN under a scenario -----------------------------------------
    step("POST /optimization/run  (assignment under the 'high_demand' scenario)")
    print("  Runs the CP-SAT assignment solver on inputs where demand is scaled")
    print("  up 1.8x, then measures, evaluates, and STORES the run.")
    run = client.post(
        "/optimization/run",
        json={"optimizer": "assignment", "scenario": "high_demand", "max_shipments": 40},
    ).json()
    print(f"  -> run_id={run['run_id']}  persisted={run['persisted']}")
    print(f"  warehouse : {run['warehouse_id']}   scenario: {run['scenario_name']}")
    print("  scenario changes applied:")
    for change in run["scenario_changes"]:
        print(f"    - {change}")
    print("  KPIs (Week 6, Part 5):")
    show_metrics(run["metrics"])
    print("  BEFORE vs AFTER (Week 6, Part 6):")
    print(f"    {run['evaluation']['summary']}")

    stored_run_id = run["run_id"]

    # ---- Run the other three optimizers so history has variety -----------
    step("POST /optimization/run  (the other three optimizers)")
    for optimizer, body in [
        ("fleet", {"optimizer": "fleet", "scenario": "vehicle_failure", "max_shipments": 40}),
        ("routes", {"optimizer": "routes", "scenario": "normal", "max_stops": 25}),
        ("warehouse", {"optimizer": "warehouse", "scenario": "supplier_delay", "sample_size": 20}),
    ]:
        r = client.post("/optimization/run", json=body).json()
        m = r["metrics"]
        print(f"  {optimizer:<10} scenario={r['scenario']:<16} "
              f"cost={m['total_cost']:<10} dist={m['travel_distance_km']:<9} "
              f"util={m['vehicle_utilization']*100:4.1f}%  orders={m['orders_fulfilled']} "
              f"stockouts={m['stockouts']}  -> {r['evaluation']['summary'] if r['evaluation'] else ''}")

    # ---- 3) SIMULATE (what-if, not stored) -------------------------------
    step("POST /optimization/simulate  (a what-if that is NOT stored)")
    print("  Same computation as /run, but the result is thrown away - handy for")
    print("  trying a scenario without cluttering the history.")
    sim = client.post(
        "/optimization/simulate",
        json={"optimizer": "assignment", "scenario": "normal", "max_shipments": 40},
    ).json()
    print(f"  -> persisted={sim['persisted']} (no run_id: {sim['run_id']})")
    print(f"  normal-scenario consolidation: {sim['evaluation']['summary']}")
    print(f"  (vehicles used {sim['evaluation']['before']['vehicles_used']} -> "
          f"{sim['metrics']['vehicles_used']} after optimizing)")

    # ---- 4) HISTORY -------------------------------------------------------
    step("GET /optimization/history  (the runs we just stored, newest first)")
    hist = client.get("/optimization/history?page_size=5").json()
    print(f"  total stored runs: {hist['pagination']['total']}  (showing up to 5)")
    for row in hist["items"]:
        print(f"    {row['run_id']}  {row['optimizer']:<10} {row['scenario']:<16} "
              f"cost={row['total_cost']}  status={row['solver_status']}")

    # ---- 5) GET ONE BY ID -------------------------------------------------
    step(f"GET /optimization/{{run_id}}  (one stored run in full)")
    one = client.get(f"/optimization/{stored_run_id}").json()
    print(f"  {one['run_id']}: {one['optimizer']} / {one['scenario']} at {one['created_at']}")
    print(f"  stored KPIs: cost={one['total_cost']} dist={one['travel_distance_km']} "
          f"util={one['vehicle_utilization']} orders={one['orders_fulfilled']}")

    # ---- 6) METRICS AGGREGATE --------------------------------------------
    step("GET /optimization/metrics  (aggregate KPIs across the stored runs)")
    agg = client.get("/optimization/metrics").json()
    print(f"  runs stored        : {agg['run_count']}")
    print(f"  total cost          : {agg['total_cost']}")
    print(f"  average cost        : {agg['average_cost']}")
    print(f"  total distance (km) : {agg['total_distance_km']}")
    print(f"  avg vehicle util    : {agg['average_vehicle_utilization']*100:.1f}%")
    print(f"  total orders        : {agg['total_orders_fulfilled']}")
    print(f"  total stockouts     : {agg['total_stockouts']}")
    print(f"  avg runtime (ms)    : {agg['average_runtime_ms']}")
    print(f"  runs per scenario   : {agg['runs_per_scenario']}")

    banner("EXECUTION DEMO COMPLETE - run, simulate, history and metrics all work.")


if __name__ == "__main__":
    main()
