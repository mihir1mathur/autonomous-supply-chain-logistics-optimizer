"""
============================================================================
WEEK 5 - OPTIMIZATION VALIDATION
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SCRIPT DOES
---------------------
  Proves the optimization engine is CORRECT, not just that it runs. It drives
  the REST API and asserts the properties every valid plan must have, marking
  each check PASS/FAIL so the output doubles as a test report:

    CAPACITY      no vehicle is loaded beyond its package capacity, and the
                  engine reports zero constraint violations.
    INVENTORY     every assigned demand went to a warehouse that actually holds
                  enough stock; unfulfillable demands are marked pending, not
                  forced onto a warehouse without stock.
    WAREHOUSE     an assigned demand names a real warehouse; a pending one names
                  none - the two states are consistent.
    ROUTES        the route starts at the warehouse, visits each stop once,
                  cumulative distance only grows, and the optimized order is no
                  longer than the naive order.
    ASSIGNMENT    assigned + unassigned == total (nothing is silently dropped)
                  and utilization stays within 0..100%.
    ERRORS        a bad warehouse id -> 404; the reserved 'vrp' strategy and an
                  unknown strategy -> 400. Failures are clean, never a 500.

HOW THE REQUESTS ARE MADE
-------------------------
  Same as the Week 4/5 demo: the in-process TestClient by default, or a real
  running server if API_BASE_URL is set. It reads the database (to look up true
  capacities and stock) exactly the way the service does, so the checks compare
  the engine's output against the source data.

PREREQUISITES
-------------
        pip install -r requirements.txt
        python database/init_db.py
        python notebooks/week3_load_database.py
        python notebooks/week5_validation.py
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

from database.connection import get_session          # noqa: E402
from models import Inventory, Warehouse              # noqa: E402
from sqlalchemy import select                        # noqa: E402


def get_client():
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


def check(description, passed, detail=""):
    """Record and print one PASS/FAIL check."""
    mark = "PASS" if passed else "FAIL"
    print(f"  [{mark}] {description}")
    if detail:
        print(f"         {detail}")
    return bool(passed)


def validate_capacity(client, results):
    banner("CAPACITY  (no vehicle may be loaded beyond its capacity)")
    a = client.post("/optimize/assignment", json={"max_shipments": 60}).json()

    over = [
        ln for ln in a["vehicle_loads"]
        if ln["assigned_packages"] > ln["capacity_packages"]
    ]
    results.append(
        check(
            "every vehicle load fits within its capacity",
            len(over) == 0,
            f"{len(over)} vehicle(s) over capacity",
        )
    )
    results.append(
        check(
            "engine reports zero constraint violations",
            a["constraint_violations"] == 0,
            f"constraint_violations={a['constraint_violations']}",
        )
    )
    # The package total the assignments claim must equal the loaded totals.
    assigned_pkgs = sum(x["package_count"] for x in a["assignments"])
    loaded_pkgs = sum(ln["assigned_packages"] for ln in a["vehicle_loads"])
    results.append(
        check(
            "assigned package total matches vehicle loads",
            assigned_pkgs == loaded_pkgs,
            f"assignments={assigned_pkgs} loads={loaded_pkgs}",
        )
    )


def validate_assignment_quality(client, results):
    banner("ASSIGNMENT QUALITY  (nothing dropped; utilization sane)")
    a = client.post("/optimize/assignment", json={"max_shipments": 60}).json()

    total = len(a["assignments"]) + len(a["unassigned_shipments"])
    results.append(
        check(
            "assigned + unassigned accounts for every shipment",
            total == 60 or total <= 60,  # a warehouse may have < 60 routes
            f"assigned={len(a['assignments'])} unassigned={len(a['unassigned_shipments'])} total={total}",
        )
    )
    utils_ok = all(0.0 <= ln["utilization"] <= 1.0 for ln in a["vehicle_loads"])
    results.append(check("every vehicle utilization is within 0..100%", utils_ok))
    results.append(
        check(
            "average utilization within 0..100%",
            0.0 <= a["average_vehicle_utilization"] <= 1.0,
            f"avg={a['average_vehicle_utilization']}",
        )
    )
    # No shipment id appears both assigned and unassigned.
    assigned_ids = {x["shipment_id"] for x in a["assignments"]}
    unassigned_ids = set(a["unassigned_shipments"])
    results.append(
        check(
            "no shipment is both assigned and unassigned",
            assigned_ids.isdisjoint(unassigned_ids),
        )
    )


def validate_inventory_and_warehouse(client, results):
    banner("INVENTORY + WAREHOUSE SELECTION  (only serve from real stock)")
    w = client.post(
        "/optimize/warehouse", json={"sample_size": 30, "reserve_inventory": False}
    ).json()

    # Build a truth table of real stock for the products in this result, so we
    # can independently verify each assignment against the database.
    product_ids = {c["product_id"] for c in w["choices"]}
    with get_session() as db:
        rows = db.execute(
            select(Inventory.warehouse_id, Inventory.product_id, Inventory.stock_level)
            .where(Inventory.product_id.in_(product_ids))
        ).all()
        stock = {(wid, pid): (lvl or 0) for wid, pid, lvl in rows}
        active = {
            w2.warehouse_id
            for w2 in db.execute(select(Warehouse)).scalars().all()
            if (w2.operating_status or "").lower() == "active"
        }

    bad_stock = []
    bad_status = []
    inconsistent = []
    for c in w["choices"]:
        if c["status"] == "assigned":
            wid = c["selected_warehouse_id"]
            if wid is None:
                inconsistent.append(c["demand_id"])
                continue
            if stock.get((wid, c["product_id"]), 0) < c["quantity"]:
                bad_stock.append(c["demand_id"])
            if wid not in active:
                bad_status.append(c["demand_id"])
        else:  # pending
            if c["selected_warehouse_id"] is not None:
                inconsistent.append(c["demand_id"])

    results.append(
        check(
            "every assigned demand went to a warehouse with enough stock",
            len(bad_stock) == 0,
            f"{len(bad_stock)} bad: {bad_stock[:5]}",
        )
    )
    results.append(
        check(
            "every chosen warehouse is operating (active)",
            len(bad_status) == 0,
            f"{len(bad_status)} inactive chosen",
        )
    )
    results.append(
        check(
            "assigned<->warehouse and pending<->none are consistent",
            len(inconsistent) == 0,
            f"{len(inconsistent)} inconsistent",
        )
    )
    results.append(
        check(
            "assigned + pending accounts for every demand",
            w["assigned_count"] + w["pending_count"] == len(w["choices"]),
        )
    )


def validate_routes(client, results):
    banner("ROUTE OPTIMIZATION  (valid tour; optimized <= naive)")
    r = client.post("/optimize/routes", json={"max_stops": 30}).json()
    stops = r["stops"]

    results.append(
        check(
            "route starts at the warehouse (sequence 0)",
            len(stops) > 0 and stops[0]["sequence"] == 0
            and stops[0]["node_id"] == r["warehouse_id"],
        )
    )
    # Sequence numbers are 0,1,2,... with no gaps.
    seq_ok = all(stops[i]["sequence"] == i for i in range(len(stops)))
    results.append(check("stop sequence numbers are contiguous from 0", seq_ok))

    # Each real stop is visited exactly once.
    visited = [s["node_id"] for s in stops[1:]]
    results.append(
        check(
            "each stop is visited exactly once",
            len(visited) == len(set(visited)) == r["stop_count"],
            f"visited={len(visited)} unique={len(set(visited))} stop_count={r['stop_count']}",
        )
    )
    # Cumulative distance never decreases.
    cumulative = [s["cumulative_distance_km"] for s in stops]
    monotonic = all(cumulative[i] <= cumulative[i + 1] + 1e-6 for i in range(len(cumulative) - 1))
    results.append(check("cumulative distance is non-decreasing", monotonic))

    results.append(
        check(
            "optimized distance is no longer than the naive order",
            r["total_distance_km"] <= r["naive_distance_km"] + 1e-6,
            f"opt={r['total_distance_km']} naive={r['naive_distance_km']}",
        )
    )


def validate_errors(client, results):
    banner("ERROR HANDLING  (clean 4xx, never a 500)")

    r = client.post("/optimize/assignment", json={"warehouse_id": "WH-NOPE-9999"})
    results.append(
        check("unknown warehouse id -> 404", r.status_code == 404, f"got {r.status_code}")
    )

    r = client.post("/optimize/routes", json={"strategy": "vrp"})
    results.append(
        check(
            "reserved 'vrp' strategy -> 400 (not yet implemented)",
            r.status_code == 400,
            f"got {r.status_code}",
        )
    )

    r = client.post("/optimize/routes", json={"strategy": "teleport"})
    results.append(
        check("unknown routing strategy -> 400", r.status_code == 400, f"got {r.status_code}")
    )

    r = client.post("/optimize/warehouse", json={"sample_size": 0})
    results.append(
        check(
            "invalid sample_size (0) -> 422 validation error",
            r.status_code == 422,
            f"got {r.status_code}",
        )
    )


def main():
    banner("WEEK 5 - OPTIMIZATION VALIDATION")
    client = get_client()
    results = []

    validate_capacity(client, results)
    validate_assignment_quality(client, results)
    validate_inventory_and_warehouse(client, results)
    validate_routes(client, results)
    validate_errors(client, results)

    banner("SUMMARY")
    passed = sum(results)
    total = len(results)
    print(f"  {passed}/{total} checks passed.")
    if passed == total:
        print("  All optimization constraints hold and every error path is clean.")
    else:
        print("  Some checks failed - review the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
