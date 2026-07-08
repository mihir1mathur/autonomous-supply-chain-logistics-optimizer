"""
============================================================================
WEEK 4 - API DEMO  (happy paths)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SCRIPT DOES
---------------------
  Exercises the Week 4 REST API end to end and prints clean, explained output:
  listing, fetching one, creating, updating (PUT + PATCH), deleting, plus
  filtering, sorting, searching, and pagination. It is the "everything works"
  companion to week4_api_validation.py (which shows the ERROR paths).

  It is NON-DESTRUCTIVE: the create/update/delete demo uses a clearly-marked
  test row (CUST-WEEK4-DEMO) and deletes it at the end, so running this script
  leaves the data unchanged.

HOW THE REQUESTS ARE MADE (no separate server needed)
-----------------------------------------------------
  We use FastAPI's TestClient, which sends REAL HTTP requests straight into the
  app in-process - so you can run this with ONE command and no running server.

  To instead test a REAL running server (more realistic), start it in another
  terminal:
        uvicorn api.main:app --reload
  then set the environment variable API_BASE_URL, e.g. (PowerShell):
        $env:API_BASE_URL = "http://127.0.0.1:8000"
  and the script will use httpx against that live URL instead.

PREREQUISITES
-------------
  The Week 3 database must exist and be loaded:
        python database/init_db.py
        python notebooks/week3_load_database.py
  Then run:
        python notebooks/week4_api_demo.py
============================================================================
"""

import os
import sys
import warnings

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# TestClient prints a harmless deprecation note about httpx internals; hide it
# so the demo output stays clean.
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*httpx.*")
warnings.filterwarnings("ignore", message=".*starlette.testclient.*")


def get_client():
    """
    Return a client that talks to the API.

    - If API_BASE_URL is set, use httpx against that REAL running server.
    - Otherwise use FastAPI's in-process TestClient (no server to start).
    Both send real HTTP requests and return the same kind of response object.
    """
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


def step(title):
    print("\n" + "-" * 70)
    print(title)
    print("-" * 70)


def show(response):
    """Print the status code and a short preview of the JSON body."""
    print(f"  -> HTTP {response.status_code}")
    try:
        body = response.json()
    except Exception:
        print("  (no JSON body)")
        return
    text = str(body)
    print("  ", text[:400] + (" ..." if len(text) > 400 else ""))


def main():
    banner("WEEK 4 - API DEMO (happy paths)")
    client = get_client()

    # ---- META -------------------------------------------------------------
    step("GET /health  (is the API alive?)")
    print("  A quick liveness check that does NOT touch the database.")
    show(client.get("/health"))

    # ---- LIST + PAGINATION ------------------------------------------------
    step("GET /warehouses?page=1&page_size=3  (LIST with pagination)")
    print("  Lists warehouses one small PAGE at a time (3 per page here).")
    r = client.get("/warehouses", params={"page": 1, "page_size": 3})
    show(r)
    warehouses = r.json()["items"]
    print("  pagination:", r.json()["pagination"])
    sample_wh = warehouses[0]["warehouse_id"] if warehouses else None
    print(f"  We'll reuse warehouse id: {sample_wh}")

    # ---- GET ONE ----------------------------------------------------------
    step(f"GET /warehouses/{sample_wh}  (fetch ONE by id)")
    print("  Fetches a single resource by its primary key.")
    show(client.get(f"/warehouses/{sample_wh}"))

    # ---- FILTERING --------------------------------------------------------
    step("GET /warehouses?operating_status=active&page_size=3  (FILTER)")
    print("  Filters are exact matches on safelisted columns.")
    show(client.get("/warehouses", params={"operating_status": "active", "page_size": 3}))

    # ---- SORTING ----------------------------------------------------------
    step("GET /warehouses?sort_by=capacity&sort_dir=desc&page_size=3  (SORT)")
    print("  Sorting is only allowed on safelisted columns.")
    r = client.get("/warehouses", params={"sort_by": "capacity", "sort_dir": "desc", "page_size": 3})
    show(r)
    caps = [w.get("capacity") for w in r.json()["items"]]
    print("  capacities (should be descending):", caps)

    # ---- SEARCHING --------------------------------------------------------
    step("GET /customers?search=sao&page_size=3  (SEARCH free text)")
    print("  Case-insensitive partial match across the documented text columns.")
    r = client.get("/customers", params={"search": "sao", "page_size": 3})
    show(r)
    print("  total matches:", r.json()["pagination"]["total"])

    # ---- INVENTORY FILTER (business status) -------------------------------
    step("GET /inventory?inventory_status=low_stock&page_size=3")
    print("  Uses the derived inventory_status (healthy/low_stock/out_of_stock).")
    show(client.get("/inventory", params={"inventory_status": "low_stock", "page_size": 3}))

    # ---- CONVENIENCE ENDPOINT --------------------------------------------
    step("GET /disruptions/active  (reuses the Week 3 'active' query)")
    r = client.get("/disruptions/active")
    print(f"  -> HTTP {r.status_code}; active disruptions returned: {len(r.json())}")

    # ---- CREATE / UPDATE / DELETE cycle (non-destructive) -----------------
    banner("WRITE CYCLE  (POST -> PATCH -> PUT -> DELETE, on a test row)")
    test_id = "CUST-WEEK4-DEMO"
    # Clean any leftover from a previous run so the demo is repeatable.
    client.delete(f"/customers/{test_id}")

    step(f"POST /customers  (CREATE {test_id})")
    print("  Creates a new customer. Note the state 'sp' is validated to 'SP'.")
    r = client.post(
        "/customers",
        json={
            "customer_id": test_id,
            "customer_city": "demo city",
            "customer_state": "sp",
            "customer_zip_code_prefix": 12345,
        },
    )
    show(r)

    step(f"GET /customers/{test_id}  (confirm it exists, state uppercased)")
    r = client.get(f"/customers/{test_id}")
    show(r)
    print("  customer_state came back as:", r.json().get("customer_state"))

    step(f"PATCH /customers/{test_id}  (partial update: change the city only)")
    show(client.patch(f"/customers/{test_id}", json={"customer_city": "patched city"}))

    step(f"PUT /customers/{test_id}  (full replace of the editable fields)")
    show(
        client.put(
            f"/customers/{test_id}",
            json={"customer_city": "put city", "customer_state": "RJ", "customer_zip_code_prefix": 99999},
        )
    )

    step(f"DELETE /customers/{test_id}  (remove the test row)")
    r = client.delete(f"/customers/{test_id}")
    print(f"  -> HTTP {r.status_code}  (204 = success, no body)")

    step(f"GET /customers/{test_id}  (should now be 404)")
    print(f"  -> HTTP {client.get(f'/customers/{test_id}').status_code}  (gone, as expected)")

    banner("API DEMO COMPLETE - all happy paths worked; test row cleaned up.")


if __name__ == "__main__":
    main()
