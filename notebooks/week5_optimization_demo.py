"""
============================================================================
WEEK 5 - OPTIMIZATION DEMO  (happy paths)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SCRIPT DOES
---------------------
  Exercises the Week 5 optimization engine end to end through the REST API and
  prints clean, explained output for each of the four optimization problems:

    1. Shipment assignment  (pack shipments onto vehicles, respect capacity)
    2. Warehouse selection  (nearest in-stock warehouse per demand)
    3. Vehicle utilization  (balance shipments evenly across the fleet)
    4. Route optimization   (order a warehouse's stops with nearest-neighbour)

  For each it reports the numbers the Week 5 prompt asks for: success, cost,
  distance, vehicle utilization, unassigned shipments, and execution time.

  It also shows the KEY CONTRAST between problems 1 and 3: given the SAME
  shipments and fleet, assignment CONSOLIDATES onto as few vehicles as possible
  (minimize unused capacity), while fleet balancing SPREADS the load evenly
  (minimize the peak). Same data, two goals, two different plans.

HOW THE REQUESTS ARE MADE (no separate server needed)
-----------------------------------------------------
  Same pattern as the Week 4 scripts: FastAPI's in-process TestClient by
  default (one command, no running server), or a real running server if the
  environment variable API_BASE_URL is set.

PREREQUISITES
-------------
  The Week 3 database must exist and be loaded, and OR-Tools installed:
        pip install -r requirements.txt
        python database/init_db.py
        python notebooks/week3_load_database.py
  Then run:
        python notebooks/week5_optimization_demo.py
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
        return httpx.Client(base_url=base_url, timeout=30.0)

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


def main():
    banner("WEEK 5 - OPTIMIZATION DEMO (happy paths)")
    client = get_client()

    # ---- STATUS -----------------------------------------------------------
    step("GET /optimize/status  (is the engine ready? what can it do?)")
    print("  A fast capability check that does NOT touch the database.")
    s = client.get("/optimize/status").json()
    print(f"  engine           : {s['engine']}")
    print(f"  OR-Tools version : {s['ortools_version']}")
    print(f"  solvers          : {s['solvers']}")
    print(f"  route strategies : {s['route_strategies']}")
    print(f"  solver time limit: {s['settings']['solver_time_limit_seconds']}s")

    # A modest shipment cap so the fleet has spare room - this makes the
    # difference between "consolidate" and "balance" easy to see.
    demo_shipments = 40

    # ---- 1) SHIPMENT ASSIGNMENT ------------------------------------------
    step("POST /optimize/assignment  (pack shipments onto vehicles)")
    print("  Goal: respect capacity and MINIMIZE UNUSED CAPACITY by")
    print("  consolidating shipments onto as few vehicles as possible.")
    a = client.post("/optimize/assignment", json={"max_shipments": demo_shipments}).json()
    print(f"  -> success={a['success']} status={a['status']}")
    print(f"  shipments assigned : {len(a['assignments'])}")
    print(f"  unassigned         : {len(a['unassigned_shipments'])}")
    print(f"  vehicles USED      : {a['vehicles_used']}  (fewer = tighter packing)")
    print(f"  avg utilization    : {a['average_vehicle_utilization']*100:.1f}%")
    print(f"  total distance     : {a['total_distance_km']} km")
    print(f"  total cost         : {a['total_cost']}")
    print(f"  constraint breaches: {a['constraint_violations']}")
    print(f"  execution time     : {a['execution_time_ms']} ms")
    _show_loads(a["vehicle_loads"])

    # ---- 3) VEHICLE UTILIZATION (shown next for direct contrast) ---------
    step("POST /optimize/fleet  (balance the SAME shipments across the fleet)")
    print("  Goal: SPREAD the load evenly - minimize the busiest vehicle's")
    print("  utilization - so no vehicle is slammed while others sit idle.")
    f = client.post("/optimize/fleet", json={"max_shipments": demo_shipments}).json()
    print(f"  -> success={f['success']} status={f['status']}")
    print(f"  vehicles USED      : {f['vehicles_used']}  (more = load shared out)")
    print(f"  avg utilization    : {f['average_utilization']*100:.1f}%")
    print(f"  min..max util      : {f['min_utilization']*100:.1f}% .. {f['max_utilization']*100:.1f}%")
    print(f"  utilization spread : {f['utilization_spread']*100:.1f} points (lower = better balanced)")
    print(f"  overloaded / idle  : {f['overloaded_vehicles']} / {f['underutilized_vehicles']}")
    print(f"  execution time     : {f['execution_time_ms']} ms")
    _show_loads(f["vehicle_loads"])
    print("\n  CONTRAST: assignment used {aused} vehicle(s) (consolidate); "
          "fleet balancing used {fused} (spread).".format(
              aused=a["vehicles_used"], fused=f["vehicles_used"]))

    # ---- 2) WAREHOUSE SELECTION ------------------------------------------
    step("POST /optimize/warehouse  (nearest in-stock warehouse per demand)")
    print("  Goal: for each demand, pick the NEAREST operating warehouse that")
    print("  has enough stock; if none does, mark the demand PENDING.")
    w = client.post("/optimize/warehouse", json={"sample_size": 15}).json()
    print(f"  -> success={w['success']} status={w['status']}")
    print(f"  demands assigned   : {w['assigned_count']}")
    print(f"  demands pending    : {w['pending_count']}  (no warehouse had stock)")
    print(f"  avg distance       : {w['average_distance_km']} km")
    print(f"  execution time     : {w['execution_time_ms']} ms")
    print("  a few decisions:")
    for choice in w["choices"][:6]:
        if choice["status"] == "assigned":
            print(f"    {choice['demand_id']}: qty {choice['quantity']:>2} of {choice['product_id'][:12]}.."
                  f" -> {choice['selected_warehouse_id']} ({choice['distance_km']} km)")
        else:
            print(f"    {choice['demand_id']}: qty {choice['quantity']:>2} of {choice['product_id'][:12]}.."
                  f" -> PENDING ({choice['reason']})")

    # ---- 4) ROUTE OPTIMIZATION -------------------------------------------
    step("POST /optimize/routes  (order a warehouse's stops, nearest-neighbour)")
    print("  Goal: visit the delivery stops in a SHORT order instead of the")
    print("  order they arrived. We report the distance saved vs. that naive order.")
    r = client.post("/optimize/routes", json={"max_stops": 25}).json()
    print(f"  -> success={r['success']} status={r['status']} strategy={r['strategy']}")
    print(f"  warehouse          : {r['warehouse_id']}")
    print(f"  stops              : {r['stop_count']}")
    print(f"  naive distance     : {r['naive_distance_km']} km  (un-optimized order)")
    print(f"  optimized distance : {r['total_distance_km']} km")
    print(f"  distance saved     : {r['distance_reduction_km']} km ({r['distance_reduction_percent']}%)")
    print(f"  execution time     : {r['execution_time_ms']} ms")
    print("  first few stops in the optimized order:")
    for stop in r["stops"][:5]:
        label = "START (warehouse)" if stop["sequence"] == 0 else stop["node_id"]
        print(f"    #{stop['sequence']:>2} {label:<20} leg {stop['leg_distance_km']:>7} km"
              f"  cumulative {stop['cumulative_distance_km']:>8} km")

    banner("OPTIMIZATION DEMO COMPLETE - all four optimizers ran successfully.")


def _show_loads(loads, limit=6):
    """Print a compact per-vehicle load table."""
    shown = [ln for ln in loads if ln["assigned_shipments"] > 0][:limit]
    if not shown:
        print("    (no vehicles carried anything)")
        return
    print("    vehicle            packages/capacity   util    shipments")
    for ln in shown:
        print(f"    {ln['vehicle_id']:<16} {ln['assigned_packages']:>5}/{ln['capacity_packages']:<6}"
              f"    {ln['utilization']*100:>5.1f}%   {ln['assigned_shipments']}")


if __name__ == "__main__":
    main()
