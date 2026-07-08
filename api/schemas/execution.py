"""
============================================================================
EXECUTION SCHEMAS  (Week 6)   endpoints: /optimization/*
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE HOLDS
--------------------
  The Pydantic REQUEST and RESPONSE schemas for the Week 6 optimization
  EXECUTION endpoints (run, simulate, history, get-by-id, metrics, scenarios).
  Same idea as the Week 4 entity schemas and the Week 5 optimization schemas:
  the request schemas validate/shape the JSON coming in, and the response
  schemas control exactly what goes out.

TWO KINDS OF RESPONSE HERE
--------------------------
  1. A RUN RESULT (OptimizationRunResult) mirrors the dict the execution
     service returns from run()/simulate(): the KPIs, the before/after
     evaluation, and the scenario changes applied.
  2. A STORED RUN (OptimizationRunResponse) mirrors a row of the
     optimization_runs table, read back by the history endpoints. It inherits
     ORMModel (from_attributes=True), the Week 4 ORM bridge, so FastAPI builds
     the JSON straight off the SQLAlchemy row.

EVERY REQUEST IS HAPPY WITH AN EMPTY BODY
-----------------------------------------
  As in Week 5, every field defaults sensibly, so `POST /optimization/run` with
  `{}` runs the default optimizer under the "normal" scenario on an
  auto-selected warehouse. Callers narrow it down as they learn.
============================================================================
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from api.schemas.base import ORMModel


# ===========================================================================
# REQUESTS
# ===========================================================================
class OptimizationRunRequest(BaseModel):
    """Run (or simulate) one optimization under a scenario."""

    optimizer: str = Field(
        "assignment",
        description="Which optimizer to run: assignment / fleet / routes / warehouse.",
    )
    scenario: str = Field(
        "normal",
        description="Which scenario to apply (see GET /optimization/scenarios). "
        "'normal' means no changes.",
    )
    warehouse_id: str | None = Field(
        None,
        description="Target warehouse (assignment / fleet / routes). If omitted, "
        "one is auto-selected.",
    )
    max_shipments: int | None = Field(
        None, ge=1, description="Cap on shipments to include (clamped by config)."
    )
    max_stops: int | None = Field(
        None, ge=1, description="Cap on route stops to include (routes optimizer)."
    )
    sample_size: int | None = Field(
        None, ge=1, description="How many demands to sample (warehouse optimizer)."
    )
    strategy: str | None = Field(
        None, description="Routing strategy (routes optimizer): 'nearest_neighbor'."
    )
    reserve_inventory: bool = Field(
        True, description="Warehouse optimizer: reserve stock as it is promised."
    )
    evaluate: bool = Field(
        True, description="Also compute the before-vs-after evaluation."
    )


# ===========================================================================
# SHARED RESPONSE PIECES
# ===========================================================================
class RunMetricsSchema(BaseModel):
    """The twelve KPIs of a run (Week 6, Part 5), plus a couple of extras."""

    total_cost: float
    travel_distance_km: float
    vehicle_utilization: float
    warehouse_utilization: float
    inventory_holding_cost: float
    stockouts: int
    late_deliveries: int
    orders_fulfilled: int
    optimization_runtime_ms: float
    solver_status: str
    num_constraints: int
    num_variables: int
    optimizer: str = ""
    vehicles_used: int = 0
    model_size_is_estimated: bool = False


class EvaluationSchema(BaseModel):
    """The before-vs-after improvement percentages (Week 6, Part 6)."""

    cost_reduction_percent: float
    distance_reduction_percent: float
    inventory_reduction_percent: float
    stockout_reduction_percent: float
    late_delivery_reduction_percent: float
    utilization_improvement_percent: float
    delivery_improvement_percent: float
    resource_utilization_percent: float
    before: dict
    after: dict
    summary: str


# ===========================================================================
# RESPONSES
# ===========================================================================
class OptimizationRunResult(BaseModel):
    """
    The result of POST /optimization/run and /simulate - the full outcome of one
    optimization: its metrics, its evaluation, and what the scenario changed.
    """

    run_id: str | None = None
    persisted: bool
    optimizer: str
    scenario: str
    scenario_name: str
    warehouse_id: str | None = None
    success: bool
    solver_status: str
    created_at: str | None = None
    scenario_changes: list[str] = []
    metrics: RunMetricsSchema
    evaluation: EvaluationSchema | None = None
    message: str


class OptimizationRunResponse(ORMModel):
    """One STORED run, read back from the optimization_runs table (history)."""

    run_id: str
    created_at: datetime | None = None
    scenario: str | None = None
    optimizer: str | None = None
    warehouse_id: str | None = None
    success: bool | None = None
    solver_status: str | None = None
    total_cost: float | None = None
    travel_distance_km: float | None = None
    vehicle_utilization: float | None = None
    warehouse_utilization: float | None = None
    inventory_holding_cost: float | None = None
    stockouts: int | None = None
    late_deliveries: int | None = None
    orders_fulfilled: int | None = None
    runtime_ms: float | None = None
    num_constraints: int | None = None
    num_variables: int | None = None
    vehicles_used: int | None = None
    metrics: dict | None = None
    evaluation: dict | None = None
    details: dict | None = None


class ScenarioSchema(BaseModel):
    """One entry in the scenario catalog (GET /optimization/scenarios)."""

    key: str
    name: str
    category: str
    description: str


class ScenariosResponse(BaseModel):
    """The full scenario catalog plus a count."""

    count: int
    scenarios: list[ScenarioSchema]


class MetricsAggregateResponse(BaseModel):
    """Aggregate KPIs across the stored runs (GET /optimization/metrics)."""

    run_count: int
    filters: dict
    total_cost: float
    average_cost: float
    total_distance_km: float
    average_vehicle_utilization: float
    total_orders_fulfilled: int
    total_stockouts: int
    total_late_deliveries: int
    average_runtime_ms: float
    runs_per_scenario: dict
