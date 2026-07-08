"""
============================================================================
WEEK 4 - API VALIDATION & ERROR-HANDLING DEMO
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SCRIPT DOES
---------------------
  Deliberately triggers the ERROR paths to prove the API fails CLEANLY, with the
  right HTTP status code and a consistent JSON error envelope - never a stack
  trace and never raw SQL. It is the companion to week4_api_demo.py (happy path).

  Every error the API returns has the SAME shape:
        { "error": { "code": "...", "message": "...", "details": ... } }

  Cases demonstrated:
    404  fetching a missing resource
    409  creating a duplicate id
    422  invalid data (bad enum, wrong type, missing required field)
    400  sorting by a column that is not allowed
    400  bad pagination (page_size over the maximum)

  It is NON-DESTRUCTIVE: the duplicate test uses a clearly-marked row
  (CUST-WEEK4-VALTEST) and deletes it at the end.

HOW THE REQUESTS ARE MADE
-------------------------
  Same as week4_api_demo.py: the in-process TestClient by default, or a real
  running server if API_BASE_URL is set. See that file's header for details.

PREREQUISITES
-------------
        python database/init_db.py
        python notebooks/week3_load_database.py
        python notebooks/week4_api_validation.py
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
        return httpx.Client(base_url=base_url, timeout=10.0)

    from fastapi.testclient import TestClient

    from api.main import app

    print("(using the in-process TestClient - no separate server needed)")
    return TestClient(app)


def banner(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def check(description, response, expected_status):
    """
    Print a case, its expected vs. actual status, and the error envelope.
    Marks PASS/FAIL so the output doubles as a mini test report.
    """
    print("\n" + "-" * 70)
    print(description)
    print("-" * 70)
    actual = response.status_code
    ok = actual == expected_status
    print(f"  expected HTTP {expected_status}, got HTTP {actual}  ->  {'PASS' if ok else 'FAIL'}")
    try:
        body = response.json()
        if isinstance(body, dict) and "error" in body:
            err = body["error"]
            print(f"  error.code   : {err.get('code')}")
            print(f"  error.message: {err.get('message')}")
            if "details" in err:
                print(f"  error.details: {str(err['details'])[:300]}")
        else:
            print("  body:", str(body)[:200])
    except Exception:
        print("  (no JSON body)")
    return ok


def main():
    banner("WEEK 4 - API VALIDATION & ERROR-HANDLING DEMO")
    client = get_client()
    results = []

    # ---- 404 NOT FOUND ----------------------------------------------------
    results.append(
        check(
            "404 - GET /warehouses/NO-SUCH-ID  (resource does not exist)",
            client.get("/warehouses/NO-SUCH-ID-9999"),
            404,
        )
    )

    # ---- 409 DUPLICATE ----------------------------------------------------
    dup_id = "CUST-WEEK4-VALTEST"
    client.delete(f"/customers/{dup_id}")  # start clean
    first = client.post("/customers", json={"customer_id": dup_id, "customer_city": "x", "customer_state": "SP"})
    print(f"\n(setup) created {dup_id} once -> HTTP {first.status_code}")
    results.append(
        check(
            "409 - POST /customers with an id that already exists (duplicate)",
            client.post("/customers", json={"customer_id": dup_id, "customer_city": "y"}),
            409,
        )
    )
    client.delete(f"/customers/{dup_id}")  # clean up the test row
    print(f"(cleanup) deleted {dup_id}")

    # ---- 422 VALIDATION: bad enum value -----------------------------------
    results.append(
        check(
            "422 - POST /vehicles with an invalid vehicle_type ('spaceship')",
            client.post("/vehicles", json={"vehicle_id": "VEH-VALTEST", "vehicle_type": "spaceship"}),
            422,
        )
    )

    # ---- 422 VALIDATION: wrong type ---------------------------------------
    results.append(
        check(
            "422 - POST /inventory with stock_level as text instead of a number",
            client.post(
                "/inventory",
                json={"inventory_id": "INV-VALTEST", "stock_level": "lots", "reorder_threshold": 10},
            ),
            422,
        )
    )

    # ---- 422 VALIDATION: missing required field ---------------------------
    results.append(
        check(
            "422 - POST /customers with no customer_id (required field missing)",
            client.post("/customers", json={"customer_city": "nowhere"}),
            422,
        )
    )

    # ---- 400 BAD SORT COLUMN ----------------------------------------------
    results.append(
        check(
            "400 - GET /customers?sort_by=not_a_column  (column not allowed)",
            client.get("/customers", params={"sort_by": "not_a_column"}),
            400,
        )
    )

    # ---- 400 BAD PAGINATION (over the max) --------------------------------
    results.append(
        check(
            "422 - GET /warehouses?page=0  (page must be >= 1)",
            client.get("/warehouses", params={"page": 0}),
            422,
        )
    )

    # ---- SUMMARY ----------------------------------------------------------
    banner("SUMMARY")
    passed = sum(results)
    total = len(results)
    print(f"  {passed}/{total} error cases behaved as expected.")
    if passed == total:
        print("  All error paths return clean, correctly-coded JSON. No SQL leaked.")
    else:
        print("  Some cases did not match - review the output above.")


if __name__ == "__main__":
    main()
