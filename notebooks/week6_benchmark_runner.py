"""
============================================================================
WEEK 6 - BENCHMARK RUNNER  (Part 7)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SCRIPT DOES
---------------------
  Automatically runs the SAME optimizer under several SCENARIOS and produces
  ONE benchmark report comparing them side by side. This is how a planning team
  answers "how does our plan hold up under a holiday peak, a demand spike, a
  vehicle failure, a supplier delay - versus a normal day?".

  The default sweep is the Week 6 benchmark set (optimization/scenarios.py,
  BENCHMARK_SCENARIOS):
        normal -> holiday -> demand_spike -> vehicle_failure -> supplier_delay

  For each scenario it runs the optimizer (default: assignment) through the REST
  API, collects the KPIs, and then writes a single report to:
        benchmarks/week6_benchmark_report.md    (human-readable table)
        benchmarks/week6_benchmark_report.json   (machine-readable, full detail)

HOW THE REQUESTS ARE MADE (no separate server needed)
-----------------------------------------------------
  Same pattern as the Week 4/5/6 scripts: the in-process TestClient by default,
  or a real running server if API_BASE_URL is set. Each run is persisted, so the
  benchmark also populates the /optimization/history and /optimization/metrics
  endpoints.

PREREQUISITES
-------------
        pip install -r requirements.txt
        python database/init_db.py                 # creates optimization_runs
        python notebooks/week3_load_database.py
        python notebooks/week6_benchmark_runner.py
============================================================================
"""

import json
import os
import sys
import warnings

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*httpx.*")
warnings.filterwarnings("ignore", message=".*starlette.testclient.*")

from optimization.scenarios import BENCHMARK_SCENARIOS  # noqa: E402

# Where the report is written (created if missing). Not required in version
# control - it is a generated artifact, like processed/ and simulation/.
BENCHMARK_DIR = os.path.join(PROJECT_ROOT, "benchmarks")
MD_PATH = os.path.join(BENCHMARK_DIR, "week6_benchmark_report.md")
JSON_PATH = os.path.join(BENCHMARK_DIR, "week6_benchmark_report.json")

# The optimizer to benchmark and how many shipments to include per run. Assignment
# is the most scenario-sensitive (demand, fleet size, and fuel all bite), which
# makes it the clearest optimizer to compare scenarios with.
OPTIMIZER = os.getenv("BENCHMARK_OPTIMIZER", "assignment")
MAX_SHIPMENTS = int(os.getenv("BENCHMARK_MAX_SHIPMENTS", "50"))


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


def run_benchmark(client):
    """Run OPTIMIZER under each benchmark scenario; return a list of run dicts."""
    runs = []
    for scenario in BENCHMARK_SCENARIOS:
        print(f"  running {OPTIMIZER} under scenario '{scenario}' ...")
        resp = client.post(
            "/optimization/run",
            json={
                "optimizer": OPTIMIZER,
                "scenario": scenario,
                "max_shipments": MAX_SHIPMENTS,
            },
        )
        if resp.status_code != 200:
            print(f"    WARNING: scenario '{scenario}' returned {resp.status_code}: {resp.text[:200]}")
            continue
        runs.append(resp.json())
    return runs


def build_markdown(runs):
    """Render the runs into one Markdown benchmark report."""
    lines = []
    lines.append("# Week 6 Benchmark Report")
    lines.append("")
    lines.append(
        f"Optimizer: **{OPTIMIZER}**  |  Shipments per run: **{MAX_SHIPMENTS}**  |  "
        f"Scenarios: **{len(runs)}**"
    )
    lines.append("")
    lines.append(
        "Each row runs the same optimizer on the same warehouse's shipments, but "
        "with the scenario's changes applied to the inputs first. Lower cost / "
        "distance / stockouts / late deliveries is better; higher utilization and "
        "orders fulfilled is better."
    )
    lines.append("")

    # ---- KPI table -------------------------------------------------------
    header = (
        "| Scenario | Cost | Distance (km) | Veh. Util | Orders | Stockouts | "
        "Late | Runtime (ms) | Status |"
    )
    sep = "|" + "---|" * 9
    lines.append(header)
    lines.append(sep)
    for r in runs:
        m = r["metrics"]
        lines.append(
            f"| {r['scenario']} | {m['total_cost']} | {m['travel_distance_km']} | "
            f"{m['vehicle_utilization']*100:.1f}% | {m['orders_fulfilled']} | "
            f"{m['stockouts']} | {m['late_deliveries']} | "
            f"{m['optimization_runtime_ms']} | {m['solver_status']} |"
        )
    lines.append("")

    # ---- Improvement-over-baseline table ---------------------------------
    lines.append("## Improvement over the un-optimized baseline")
    lines.append("")
    lines.append("| Scenario | Cost reduction | Distance reduction | Utilization gain |")
    lines.append("|---|---|---|---|")
    for r in runs:
        e = r.get("evaluation") or {}
        lines.append(
            f"| {r['scenario']} | {e.get('cost_reduction_percent', 0)}% | "
            f"{e.get('distance_reduction_percent', 0)}% | "
            f"+{e.get('utilization_improvement_percent', 0)}% |"
        )
    lines.append("")

    # ---- Observations (pick out the extremes) ----------------------------
    lines.append("## Observations")
    lines.append("")
    if runs:
        normal = next((r for r in runs if r["scenario"] == "normal"), runs[0])
        worst_stockout = max(runs, key=lambda r: r["metrics"]["stockouts"])
        worst_late = max(runs, key=lambda r: r["metrics"]["late_deliveries"])
        costliest = max(runs, key=lambda r: r["metrics"]["total_cost"])
        base_cost = normal["metrics"]["total_cost"]
        lines.append(
            f"- **Baseline (`normal`)** cost is {base_cost}, "
            f"utilization {normal['metrics']['vehicle_utilization']*100:.1f}%."
        )
        lines.append(
            f"- **Most stockouts:** `{worst_stockout['scenario']}` with "
            f"{worst_stockout['metrics']['stockouts']} (demand outran capacity/stock)."
        )
        lines.append(
            f"- **Most at-risk-of-late deliveries:** `{worst_late['scenario']}` with "
            f"{worst_late['metrics']['late_deliveries']} (vehicles pushed near capacity)."
        )
        lines.append(
            f"- **Costliest scenario:** `{costliest['scenario']}` at "
            f"{costliest['metrics']['total_cost']} "
            f"({costliest['metrics']['total_cost'] - base_cost:+.2f} vs normal)."
        )
    lines.append("")
    lines.append(
        "> Generated by `notebooks/week6_benchmark_runner.py`. Every run above is "
        "also stored in the `optimization_runs` table and visible via "
        "`GET /optimization/history` and `GET /optimization/metrics`."
    )
    lines.append("")
    return "\n".join(lines)


def main():
    banner("WEEK 6 - BENCHMARK RUNNER")
    client = get_client()

    print(f"\nBenchmarking optimizer '{OPTIMIZER}' across {len(BENCHMARK_SCENARIOS)} scenarios:")
    print(f"  {', '.join(BENCHMARK_SCENARIOS)}\n")
    runs = run_benchmark(client)

    if not runs:
        print("\nNo runs completed - is the database loaded? Aborting.")
        sys.exit(1)

    os.makedirs(BENCHMARK_DIR, exist_ok=True)

    markdown = build_markdown(runs)
    with open(MD_PATH, "w", encoding="utf-8") as fh:
        fh.write(markdown)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump({"optimizer": OPTIMIZER, "max_shipments": MAX_SHIPMENTS, "runs": runs}, fh, indent=2)

    banner("BENCHMARK REPORT")
    print(markdown)
    print(f"\nWrote report to:\n  {MD_PATH}\n  {JSON_PATH}")


if __name__ == "__main__":
    main()
