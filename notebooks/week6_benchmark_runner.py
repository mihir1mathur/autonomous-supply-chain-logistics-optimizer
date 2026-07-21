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

REPRODUCIBILITY (Week 6 reproducibility fix)
--------------------------------------------
  The business metrics of a benchmark are meant to be REPRODUCIBLE: the same
  numbers come out when the source data / input fingerprint, selected warehouse,
  code, configuration, Python version and OR-Tools version are identical. Only
  the runtime, the generated run_id and the created_at timestamp are allowed to
  differ (runtime is environment-dependent). For a FEASIBLE solution this is
  verified under the recorded deterministic configuration and dependency
  versions, not guaranteed across every solver version.

  Two things make that true, and both live here:
    1. ONE warehouse is pinned for the whole sweep. If BENCHMARK_WAREHOUSE_ID is
       set it is used verbatim; otherwise the runner resolves the default
       warehouse ONCE (deterministically - ties broken by smallest id) and
       reuses it for all five scenarios.
    2. DETERMINISTIC solver mode. Unless BENCHMARK_DETERMINISTIC is explicitly
       set, the runner turns it on (single CP-SAT worker + fixed seed), which
       removes the run-to-run drift a multi-worker solver would otherwise show.

  The report also records a SHA-256 fingerprint of the actual inputs (the
  selected warehouse, its 50 delivery routes, its available vehicles, and the
  solver configuration) so two reports can be compared for "same inputs" at a
  glance. The fingerprint is computed from the database the runner is configured
  to reach (the same database the in-process API uses), so run the benchmark on
  the host whose database you want to fingerprint.

PREREQUISITES
-------------
        pip install -r requirements.txt
        python database/init_db.py                 # creates optimization_runs
        python notebooks/week3_load_database.py
        python notebooks/week6_benchmark_runner.py

  Optional environment variables:
        BENCHMARK_WAREHOUSE_ID   pin an explicit warehouse (else auto-resolved)
        BENCHMARK_DETERMINISTIC  true (default here) / false
        BENCHMARK_OPTIMIZER      assignment (default) / fleet / routes / warehouse
        BENCHMARK_MAX_SHIPMENTS  50 (default)
        API_BASE_URL             use a real running server instead of TestClient
============================================================================
"""

import hashlib
import json
import os
import platform
import sys
import warnings

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*httpx.*")
warnings.filterwarnings("ignore", message=".*starlette.testclient.*")

# Turn ON deterministic solver mode for the benchmark BEFORE the solvers run,
# unless the caller has explicitly chosen a value. The solvers read this
# environment variable fresh on every solve, so setting it here is enough.
if os.getenv("BENCHMARK_DETERMINISTIC") is None:
    os.environ["BENCHMARK_DETERMINISTIC"] = "true"

from sqlalchemy import select  # noqa: E402

from database.connection import get_session  # noqa: E402
from models import DeliveryRoute, Vehicle, Warehouse  # noqa: E402
from optimization.config import get_optimization_settings  # noqa: E402
from optimization.execution_config import get_execution_settings  # noqa: E402
from optimization.scenarios import BENCHMARK_SCENARIOS  # noqa: E402
from optimization.utils import (  # noqa: E402
    BENCHMARK_MAX_DETERMINISTIC_TIME,
    BENCHMARK_RANDOM_SEED,
    benchmark_deterministic_enabled,
)

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

# An explicit warehouse to benchmark, if the caller supplies one. When absent we
# resolve ONE default warehouse deterministically and reuse it for every scenario.
BENCHMARK_WAREHOUSE_ID = os.getenv("BENCHMARK_WAREHOUSE_ID")

# Bump when the fingerprint recipe or the report shape changes.
BENCHMARK_VERSION = "1.0"

# The business fields whose values MUST match across identical runs. Runtime,
# run_id and created_at are deliberately excluded (they are environment- or
# clock-dependent, not a function of the inputs).
STABLE_METRIC_FIELDS: list[str] = [
    "total_cost",
    "travel_distance_km",
    "vehicle_utilization",
    "warehouse_utilization",
    "inventory_holding_cost",
    "stockouts",
    "late_deliveries",
    "orders_fulfilled",
    "solver_status",
    "num_constraints",
    "num_variables",
    "vehicles_used",
]
STABLE_EVALUATION_FIELDS: list[str] = [
    "cost_reduction_percent",
    "distance_reduction_percent",
    "inventory_reduction_percent",
    "stockout_reduction_percent",
    "late_delivery_reduction_percent",
    "utilization_improvement_percent",
    "delivery_improvement_percent",
    "resource_utilization_percent",
]
# Fields that are ALLOWED to differ between environments / runs.
IGNORED_FIELDS: list[str] = ["run_id", "created_at", "optimization_runtime_ms"]


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


# ===========================================================================
# WAREHOUSE RESOLUTION (once per sweep)
# ===========================================================================
def resolve_benchmark_warehouse() -> str:
    """
    Return the single warehouse the whole sweep will use.

    If BENCHMARK_WAREHOUSE_ID is set, use it verbatim. Otherwise resolve the
    default dispatch warehouse ONCE, deterministically, and reuse it for every
    scenario - never re-resolving per scenario.
    """
    if BENCHMARK_WAREHOUSE_ID:
        return BENCHMARK_WAREHOUSE_ID
    from api.services.execution_service import execution_service

    with get_session() as db:
        return execution_service.resolve_dispatch_warehouse(db, None)


# ===========================================================================
# INPUT FINGERPRINT  -- a stable SHA-256 over the actual benchmark inputs
# ===========================================================================
def _canonical(obj):
    """
    Normalise a value for stable serialisation: floats are formatted to a fixed
    number of decimals (so 46521.98 and 46521.980000001 never disagree), dict
    keys are sorted, and lists keep their (already-deterministic) order.
    """
    if isinstance(obj, float):
        return format(obj, ".6f")
    if isinstance(obj, dict):
        return {k: _canonical(obj[k]) for k in sorted(obj)}
    if isinstance(obj, (list, tuple)):
        return [_canonical(v) for v in obj]
    return obj


def _stable_json(obj) -> str:
    """Serialise a plain dict/list structure deterministically (sorted keys)."""
    return json.dumps(_canonical(obj), sort_keys=True, separators=(",", ":"))


def _solver_config_fingerprint_fields() -> dict:
    """The optimization configuration that actually affects the metrics."""
    opt = get_optimization_settings()
    exe = get_execution_settings()
    deterministic = benchmark_deterministic_enabled()
    return {
        "benchmark_deterministic": deterministic,
        "random_seed": BENCHMARK_RANDOM_SEED,
        "solver_workers_effective": 1 if deterministic else opt.solver_workers,
        # In deterministic mode the RESULT is governed by deterministic time, not
        # wall-clock, so that is the parameter the fingerprint records.
        "stopping_criterion": (
            f"max_deterministic_time={BENCHMARK_MAX_DETERMINISTIC_TIME}"
            if deterministic
            else f"max_time_in_seconds={opt.solver_time_limit_seconds}"
        ),
        "winding_factor": opt.winding_factor,
        "min_packages_per_shipment": opt.min_packages_per_shipment,
        "max_packages_per_shipment": opt.max_packages_per_shipment,
        "overloaded_utilization": opt.overloaded_utilization,
        "underutilized_utilization": opt.underutilized_utilization,
        "default_cost_per_km": exe.default_cost_per_km,
        "inventory_holding_cost_per_unit": exe.inventory_holding_cost_per_unit,
        "late_delivery_load_threshold": exe.late_delivery_load_threshold,
    }


def compute_input_fingerprint(warehouse_id: str, max_shipments: int) -> dict:
    """
    Build a stable SHA-256 fingerprint of the EXACT inputs a benchmark run
    consumes, plus the structured payload the digest was taken over.

    The payload covers, in deterministic sorted order:
      * the selected warehouse's relevant fields,
      * the selected delivery-route records (the same rows, ordered by route_id
        and capped at max_shipments, that the service loads as shipments),
      * the warehouse's available vehicle records, and
      * the optimization configuration that affects results.

    Runtime data (run_id, created_at, runtime) is never part of the fingerprint.
    Returns {"sha256": ..., "payload": {...}}.
    """
    with get_session() as db:
        wh = db.get(Warehouse, warehouse_id)
        warehouse_fields = (
            {
                "warehouse_id": wh.warehouse_id,
                "latitude": wh.latitude,
                "longitude": wh.longitude,
                "capacity": wh.capacity,
                "current_utilization": wh.current_utilization,
                "operating_status": wh.operating_status,
            }
            if wh is not None
            else {"warehouse_id": warehouse_id}
        )

        route_rows = (
            db.execute(
                select(DeliveryRoute)
                .where(DeliveryRoute.warehouse_id == warehouse_id)
                .order_by(DeliveryRoute.route_id)
                .limit(max_shipments)
            )
            .scalars()
            .all()
        )
        routes = [
            {
                "route_id": r.route_id,
                "warehouse_id": r.warehouse_id,
                "destination_city": r.destination_city,
                "destination_state": r.destination_state,
                "destination_latitude": r.destination_latitude,
                "destination_longitude": r.destination_longitude,
                "estimated_distance_km": r.estimated_distance_km,
            }
            for r in route_rows
        ]

        vehicle_rows = (
            db.execute(
                select(Vehicle)
                .where(Vehicle.warehouse_id == warehouse_id)
                .where(Vehicle.availability_status == "available")
                .order_by(Vehicle.vehicle_id)
            )
            .scalars()
            .all()
        )
        vehicles = [
            {
                "vehicle_id": v.vehicle_id,
                "warehouse_id": v.warehouse_id,
                "capacity_packages": v.capacity_packages,
                "capacity_kg": v.capacity_kg,
                "cost_per_km": v.cost_per_km,
                "average_speed_kmph": v.average_speed_kmph,
                "availability_status": v.availability_status,
            }
            for v in vehicle_rows
        ]

    payload = {
        "warehouse": warehouse_fields,
        "delivery_routes": routes,
        "vehicles": vehicles,
        "solver_config": _solver_config_fingerprint_fields(),
    }
    digest = hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()
    return {"sha256": digest, "payload": payload}


# ===========================================================================
# STABLE-FIELD EXTRACTION  (used by the reproducibility check + validation)
# ===========================================================================
def extract_stable_fields(run: dict) -> dict:
    """
    Project one run's response down to only the fields that must be
    reproducible: the scenario, the warehouse, the stable KPIs and the stable
    evaluation percentages. Runtime, run_id and created_at are dropped.
    """
    metrics = run.get("metrics") or {}
    evaluation = run.get("evaluation") or {}
    return {
        "scenario": run.get("scenario"),
        "warehouse_id": run.get("warehouse_id"),
        "metrics": {k: metrics.get(k) for k in STABLE_METRIC_FIELDS},
        "evaluation": {k: evaluation.get(k) for k in STABLE_EVALUATION_FIELDS},
    }


# ===========================================================================
# RUN THE SWEEP
# ===========================================================================
def run_benchmark(client, warehouse_id: str) -> list:
    """Run OPTIMIZER under each benchmark scenario, pinned to warehouse_id."""
    runs = []
    for scenario in BENCHMARK_SCENARIOS:
        print(f"  running {OPTIMIZER} under scenario '{scenario}' (warehouse {warehouse_id}) ...")
        resp = client.post(
            "/optimization/run",
            json={
                "optimizer": OPTIMIZER,
                "scenario": scenario,
                "warehouse_id": warehouse_id,
                "max_shipments": MAX_SHIPMENTS,
            },
        )
        if resp.status_code != 200:
            print(f"    WARNING: scenario '{scenario}' returned {resp.status_code}: {resp.text[:200]}")
            continue
        runs.append(resp.json())
    return runs


# ===========================================================================
# REPORT BUILDERS
# ===========================================================================
def _ortools_version() -> str:
    try:
        import ortools

        return getattr(ortools, "__version__", "unknown")
    except Exception:  # pragma: no cover - defensive only
        return "unknown"


# ===========================================================================
# REPORT SEMANTICS HELPERS  (shared by build_markdown AND the validation tests,
# so the report's wording and the checks can never drift apart)
# ===========================================================================
RUNTIME_NOTE = (
    "Runtime is environment-dependent; use repeated-run median/p95 measurements "
    "for performance comparisons."
)

OBJECTIVE_NOTE = (
    "The assignment optimizer's objective maximizes packages carried "
    "(fulfillment) and then minimizes the number of vehicles used "
    "(consolidation), subject to hard vehicle-capacity constraints; it does not "
    "minimize monetary cost. Consolidating onto fewer vehicles can raise the "
    "modeled cost when those vehicles have higher per-km rates. A positive cost "
    "change reflects an explicit trade-off in favor of capacity-feasible "
    "consolidation and fulfillment rather than direct monetary-cost minimization."
)

# Utilization gain is a RELATIVE percentage increase over the baseline, i.e.
# (optimized_utilization - baseline_utilization) / baseline_utilization * 100
# (see optimization/evaluation.py: increase_percent). It is NOT an arithmetic
# percentage-point difference, so it is reported in percent (%), never in "pp".
UTILIZATION_FORMULA_NOTE = (
    "Utilization gain is a relative percentage increase over the baseline: "
    "(optimized_utilization - baseline_utilization) / baseline_utilization x 100. "
    "It is reported in percent (%), not in percentage points (pp)."
)


def reproducibility_note() -> str:
    """The dependency-version-qualified reproducibility statement (no 'every machine')."""
    return (
        "Stable business metrics are reproducible when the source data/input "
        "fingerprint, selected warehouse, code, configuration, Python version and "
        "OR-Tools version are identical. Runtime, run_id and created_at remain "
        "environment-dependent. For the FEASIBLE scenario, reproducibility has "
        "been verified under the recorded deterministic configuration and "
        "dependency versions, rather than universally guaranteed across every "
        "solver version."
    )


def _join_names(names: list) -> str:
    """Join names as 'a', 'a and b', or 'a, b and c'."""
    names = list(names)
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def status_summary_text(runs: list) -> str:
    """
    A truthful solver-status summary generated from the runs (never hard-coded
    to a status), e.g. "4/5 scenarios returned OPTIMAL. The constrained
    vehicle_failure scenario returned a reproducible FEASIBLE solution within the
    configured solver time limit."
    """
    n = len(runs)
    by_status: dict = {}
    for r in runs:
        by_status.setdefault(r["metrics"]["solver_status"], []).append(r["scenario"])
    optimal = by_status.get("OPTIMAL", [])
    feasible = by_status.get("FEASIBLE", [])
    parts = [f"{len(optimal)}/{n} scenarios returned OPTIMAL."]
    if feasible:
        noun = "scenario" if len(feasible) == 1 else "scenarios"
        parts.append(
            f"The constrained {_join_names(feasible)} {noun} returned a reproducible "
            f"FEASIBLE solution within the configured solver time limit."
        )
    other = {s: v for s, v in by_status.items() if s not in ("OPTIMAL", "FEASIBLE")}
    for status, names in sorted(other.items()):
        parts.append(f"{_join_names(names)} returned {status}.")
    return " ".join(parts)


def cost_change_percent(cost_reduction_percent: float) -> float:
    """
    Convert a signed 'cost reduction' (positive = cost fell) into a 'cost change'
    (positive = cost ROSE). This only flips the sign of an already-computed
    number; it never recomputes or edits an optimizer result.
    """
    return round(-(cost_reduction_percent or 0.0), 1)


def cost_change_label(cost_reduction_percent: float) -> str:
    """Human-readable cost change, e.g. '+46.8% (cost increase)'."""
    change = cost_change_percent(cost_reduction_percent)
    if change > 0:
        return f"+{change:.1f}% (cost increase)"
    if change < 0:
        return f"{change:.1f}% (cost decrease)"
    return "0.0% (no change)"


def _signed_pct(value: float) -> str:
    """Format a signed percentage; a true zero prints without a sign."""
    value = round(value or 0.0, 1)
    if value == 0:
        return "0.0%"
    return f"{value:+.1f}%"


def normal_scenario_observation(runs: list) -> str:
    """
    Describe the OPTIMIZED 'normal' scenario (not the unoptimized baseline).
    Numbers are read from the run, never hard-coded. The word 'baseline' is
    reserved for the unoptimized comparison plan, so it is not used here.
    """
    normal = next((r for r in runs if r["scenario"] == "normal"), runs[0] if runs else None)
    if normal is None:
        return "No normal scenario was run."
    m = normal["metrics"]
    return (
        f"Normal optimized scenario: cost is {m['total_cost']} and vehicle "
        f"utilization is {m['vehicle_utilization'] * 100:.1f}%."
    )


def describe_max_observation(runs: list, metric: str, label: str, zero_message: str) -> str:
    """
    Describe the scenario(s) with the highest value of a metric:
      * if the maximum is zero, return zero_message (nothing occurred);
      * if several scenarios tie for a nonzero maximum, list them all.
    """
    pairs = [(r["scenario"], r["metrics"].get(metric, 0) or 0) for r in runs]
    max_value = max((v for _, v in pairs), default=0)
    if max_value == 0:
        return zero_message
    tied = [s for s, v in pairs if v == max_value]
    if len(tied) == 1:
        return f"Highest {label}: {tied[0]} with {max_value}."
    return f"Highest {label}: {_join_names(tied)}, tied at {max_value}."


def distance_note(runs: list) -> str:
    """
    Explain the assignment benchmark's distance column. When every distance
    change is zero, state plainly that no route-distance reduction is
    demonstrated here (route optimization is a separate optimizer).
    """
    changes = [
        (r.get("evaluation") or {}).get("distance_reduction_percent", 0.0) or 0.0
        for r in runs
    ]
    base = (
        "This benchmark evaluates the **assignment** optimizer, which assigns "
        "shipments to vehicles; it does not reorder stops, so it does not "
        "demonstrate route-distance reduction. Route optimization is evaluated "
        "separately by the `routes` optimizer."
    )
    if all(c == 0.0 for c in changes):
        base += (
            " Every scenario shows a 0.0% distance change: total driven distance "
            "is the sum of each assigned shipment's fixed leg and does not depend "
            "on which vehicle carries it, so no distance savings are claimed here."
        )
    return base


def build_metadata(warehouse_id: str, fingerprint: dict) -> dict:
    """The reproducibility metadata recorded in both report files."""
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "warehouse_id": warehouse_id,
        "warehouse_source": "BENCHMARK_WAREHOUSE_ID" if BENCHMARK_WAREHOUSE_ID else "auto-resolved (deterministic)",
        "max_shipments": MAX_SHIPMENTS,
        "scenarios": list(BENCHMARK_SCENARIOS),
        "deterministic_mode": benchmark_deterministic_enabled(),
        "deterministic_seed": BENCHMARK_RANDOM_SEED,
        "python_version": platform.python_version(),
        "ortools_version": _ortools_version(),
        "input_fingerprint": fingerprint["sha256"],
    }


def build_markdown(runs, meta) -> str:
    """Render the runs into one Markdown benchmark report."""
    lines = []
    lines.append("# Week 6 Benchmark Report")
    lines.append("")
    lines.append(
        f"Optimizer: **{OPTIMIZER}**  |  Shipments per run: **{MAX_SHIPMENTS}**  |  "
        f"Scenarios: **{len(runs)}**  |  Warehouse: **{meta['warehouse_id']}**"
    )
    lines.append("")

    # ---- Reproducibility metadata ---------------------------------------
    lines.append("## Reproducibility")
    lines.append("")
    lines.append(reproducibility_note())
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| Benchmark version | {meta['benchmark_version']} |")
    lines.append(f"| Selected warehouse | {meta['warehouse_id']} ({meta['warehouse_source']}) |")
    lines.append(f"| Max shipments | {meta['max_shipments']} |")
    lines.append(f"| Scenarios | {', '.join(meta['scenarios'])} |")
    lines.append(f"| Deterministic mode | {meta['deterministic_mode']} |")
    lines.append(f"| Deterministic seed | {meta['deterministic_seed']} |")
    lines.append(f"| Python version | {meta['python_version']} |")
    lines.append(f"| OR-Tools version | {meta['ortools_version']} |")
    lines.append(f"| Input fingerprint (SHA-256) | `{meta['input_fingerprint']}` |")
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
    lines.append(f"**Solver status:** {status_summary_text(runs)}")
    lines.append("")
    lines.append(
        "> Runtime (ms) is environment-dependent and is excluded from "
        "reproducibility comparison. Every other column above is a stable "
        "business metric. " + RUNTIME_NOTE
    )
    lines.append("")

    # ---- Change-relative-to-baseline table -------------------------------
    lines.append("## Change relative to the unoptimized baseline")
    lines.append("")
    lines.append(
        "Not every metric improves, so these are signed CHANGES, not guaranteed "
        "gains. For cost, a positive percentage means the optimized plan costs "
        "MORE than the naive baseline; a negative percentage means it costs less. "
        + OBJECTIVE_NOTE
    )
    lines.append("")
    lines.append("| Scenario | Cost change vs baseline | Distance change | Utilization gain (relative %) |")
    lines.append("|---|---|---|---|")
    for r in runs:
        e = r.get("evaluation") or {}
        lines.append(
            f"| {r['scenario']} | {cost_change_label(e.get('cost_reduction_percent', 0))} | "
            f"{_signed_pct(-(e.get('distance_reduction_percent', 0) or 0))} | "
            f"{_signed_pct(e.get('utilization_improvement_percent', 0))} |"
        )
    lines.append("")
    lines.append("> " + UTILIZATION_FORMULA_NOTE)
    lines.append("")
    lines.append("> " + distance_note(runs))
    lines.append("")

    # ---- Observations (pick out the extremes) ----------------------------
    lines.append("## Observations")
    lines.append("")
    if runs:
        lines.append("- " + normal_scenario_observation(runs))
        lines.append(
            "- **Stockouts:** "
            + describe_max_observation(
                runs, "stockouts", "stockout count",
                "No stockouts occurred in any tested scenario.",
            )
        )
        lines.append(
            "- **Late deliveries:** "
            + describe_max_observation(
                runs, "late_deliveries", "late-delivery count",
                "No late deliveries occurred in any tested scenario.",
            )
        )
        lines.append(
            "- **Cost:** "
            + describe_max_observation(
                runs, "total_cost", "modeled cost",
                "All scenarios had zero modeled cost.",
            )
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

    warehouse_id = resolve_benchmark_warehouse()
    fingerprint = compute_input_fingerprint(warehouse_id, MAX_SHIPMENTS)
    meta = build_metadata(warehouse_id, fingerprint)

    print(f"\nBenchmark warehouse: {warehouse_id} ({meta['warehouse_source']})")
    print(f"Deterministic mode:  {meta['deterministic_mode']} (seed {meta['deterministic_seed']})")
    print(f"Input fingerprint:   {meta['input_fingerprint']}")
    print(f"\nBenchmarking optimizer '{OPTIMIZER}' across {len(BENCHMARK_SCENARIOS)} scenarios:")
    print(f"  {', '.join(BENCHMARK_SCENARIOS)}\n")

    runs = run_benchmark(client, warehouse_id)

    if not runs:
        print("\nNo runs completed - is the database loaded? Aborting.")
        sys.exit(1)

    os.makedirs(BENCHMARK_DIR, exist_ok=True)

    markdown = build_markdown(runs, meta)
    with open(MD_PATH, "w", encoding="utf-8") as fh:
        fh.write(markdown)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(
            {
                **meta,
                "optimizer": OPTIMIZER,
                "solver_status_summary": status_summary_text(runs),
                "runs": runs,
            },
            fh,
            indent=2,
        )

    banner("BENCHMARK REPORT")
    print(markdown)
    print(f"\nWrote report to:\n  {MD_PATH}\n  {JSON_PATH}")


if __name__ == "__main__":
    main()
