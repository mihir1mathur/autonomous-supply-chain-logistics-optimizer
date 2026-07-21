"""
============================================================================
WEEK 6 - BENCHMARK REPRODUCIBILITY CHECK
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SCRIPT DOES
---------------------
  Proves the Week 6 benchmark is REPRODUCIBLE: it runs the complete
  five-scenario sweep TWICE and confirms that every stable business metric is
  identical between the two runs, while deliberately IGNORING the fields that
  are allowed to differ (runtime, run_id, created_at).

  It also confirms the two runs used the SAME warehouse and the SAME input
  fingerprint, so a difference could only come from the code or the data - never
  from an accidental warehouse switch or a solver that searched differently.

  Exit code 0 = every stable field matched (PASSED).
  Exit code 1 = at least one stable field differed (FAILED); the offending
                fields are printed.

HOW THE REQUESTS ARE MADE
-------------------------
  Same as the Week 4/5/6 scripts: the in-process TestClient by default, or a
  real running server if API_BASE_URL is set.

PREREQUISITES
-------------
        pip install -r requirements.txt
        python database/init_db.py                 # creates optimization_runs
        python notebooks/week3_load_database.py
        python notebooks/week6_reproducibility_check.py
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

# Reproducibility requires deterministic solver mode. Pin it ON before the
# solvers (and the runner, which would default it on anyway) are imported.
os.environ["BENCHMARK_DETERMINISTIC"] = "true"

from notebooks.week6_benchmark_runner import (  # noqa: E402
    IGNORED_FIELDS,
    MAX_SHIPMENTS,
    compute_input_fingerprint,
    extract_stable_fields,
    get_client,
    resolve_benchmark_warehouse,
    run_benchmark,
)


def banner(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def _diff_stable(run_a: dict, run_b: dict) -> list[str]:
    """Return human-readable field-level differences between two runs' stable views."""
    a = extract_stable_fields(run_a)
    b = extract_stable_fields(run_b)
    diffs: list[str] = []
    scenario = a.get("scenario") or b.get("scenario")

    if a.get("warehouse_id") != b.get("warehouse_id"):
        diffs.append(
            f"[{scenario}] warehouse_id: {a.get('warehouse_id')} != {b.get('warehouse_id')}"
        )
    for section in ("metrics", "evaluation"):
        for key in a[section]:
            if a[section][key] != b[section][key]:
                diffs.append(
                    f"[{scenario}] {section}.{key}: {a[section][key]} != {b[section][key]}"
                )
    return diffs


def main():
    banner("WEEK 6 - BENCHMARK REPRODUCIBILITY CHECK")
    warehouse_id = resolve_benchmark_warehouse()

    # The fingerprint is a pure function of the inputs, so computing it twice
    # must agree; we also record it for the summary.
    fp1 = compute_input_fingerprint(warehouse_id, MAX_SHIPMENTS)["sha256"]
    fp2 = compute_input_fingerprint(warehouse_id, MAX_SHIPMENTS)["sha256"]

    print(f"\nWarehouse under test: {warehouse_id}")
    print(f"Input fingerprint:    {fp1}")
    print("\nRun 1 of 2:")
    runs1 = run_benchmark(get_client(), warehouse_id)
    print("\nRun 2 of 2:")
    runs2 = run_benchmark(get_client(), warehouse_id)

    if not runs1 or not runs2:
        print("\nA sweep produced no runs - is the database loaded? Aborting.")
        sys.exit(1)

    banner("COMPARISON  (stable business fields only)")
    ok = True

    if len(runs1) != len(runs2):
        print(f"  [FAIL] different scenario counts: {len(runs1)} vs {len(runs2)}")
        ok = False

    # Same warehouse across every run in both sweeps.
    warehouses = {r["warehouse_id"] for r in runs1 + runs2}
    same_warehouse = warehouses == {warehouse_id}
    print(f"  [{'PASS' if same_warehouse else 'FAIL'}] every run used warehouse {warehouse_id}")
    if not same_warehouse:
        print(f"         saw: {sorted(warehouses)}")
        ok = False

    # Same input fingerprint.
    same_fp = fp1 == fp2
    print(f"  [{'PASS' if same_fp else 'FAIL'}] input fingerprint is stable")
    if not same_fp:
        print(f"         {fp1} != {fp2}")
        ok = False

    # Stable-field equality, scenario by scenario.
    all_diffs: list[str] = []
    for ra, rb in zip(runs1, runs2):
        all_diffs.extend(_diff_stable(ra, rb))
    fields_match = len(all_diffs) == 0
    print(f"  [{'PASS' if fields_match else 'FAIL'}] stable business fields identical across both runs")
    if not fields_match:
        ok = False
        print("         field-level differences:")
        for d in all_diffs:
            print(f"           - {d}")

    banner("SUMMARY")
    if ok:
        print("  REPRODUCIBILITY CHECK PASSED")
        print(f"  Same warehouse: {warehouse_id}")
        print(f"  Same input fingerprint: {fp1}")
        print("  Stable benchmark fields: identical")
        print(f"  Ignored fields: {', '.join(IGNORED_FIELDS)}")
        sys.exit(0)
    else:
        print("  REPRODUCIBILITY CHECK FAILED")
        print("  A stable business field differed between two identical runs.")
        print(f"  (Ignored fields, allowed to differ: {', '.join(IGNORED_FIELDS)})")
        sys.exit(1)


if __name__ == "__main__":
    main()
