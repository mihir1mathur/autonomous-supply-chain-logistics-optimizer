"""
============================================================================
OPTIMIZATION EXECUTION ROUTER  (Week 6)   URL prefix: /optimization
Project: Supply Chain & Logistics Optimizer
============================================================================

REST endpoints for the Week 6 optimization EXECUTION layer. THIN, exactly like
the seven Week 4 entity routers and the Week 5 optimization router: each
endpoint reads the request, calls one method on a service, and returns the
result. No business logic and no database access live here.

  POST /optimization/run        run one optimization under a scenario, and STORE it
  POST /optimization/simulate   the same, but a throwaway what-if (not stored)
  GET  /optimization/scenarios  the catalog of available scenarios
  GET  /optimization/metrics    aggregate KPIs across the stored runs
  GET  /optimization/history    list past runs (filter / sort / paginate)
  GET  /optimization/{run_id}   one stored run by id

WHY A NEW /optimization PREFIX (and not more /optimize routes)?
  Week 5 owns /optimize/* (the raw, stateless solvers). Week 6 adds a DISTINCT
  /optimization/* namespace for the execution layer that wraps them - running,
  measuring, evaluating, and STORING runs. Keeping the two prefixes separate
  means Week 5 is untouched and the two concerns never collide. The Week 6
  goals' "POST /optimize" and "POST /simulate" map to /optimization/run and
  /optimization/simulate here.

ROUTE ORDER MATTERS
  The literal paths (/run, /simulate, /scenarios, /metrics, /history) are
  declared BEFORE the /{run_id} path parameter, so a request for e.g.
  /optimization/metrics matches the literal route rather than being read as a
  run whose id is "metrics".
============================================================================
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.dependencies import get_db, pagination_params, search_query
from api.schemas.base import PaginatedResponse
from api.schemas.execution import (
    MetricsAggregateResponse,
    OptimizationRunRequest,
    OptimizationRunResponse,
    OptimizationRunResult,
    ScenariosResponse,
)
from api.services.execution_service import execution_service
from api.services.optimization_run_service import optimization_run_service
from api.utils.pagination import PageParams

router = APIRouter(prefix="/optimization", tags=["Optimization Execution"])


# ===========================================================================
# RUN / SIMULATE
# ===========================================================================
@router.post(
    "/run",
    response_model=OptimizationRunResult,
    summary="Run one optimization under a scenario, measure it, and store it",
)
def run_optimization(
    payload: OptimizationRunRequest | None = None,
    db: Session = Depends(get_db),
):
    """Run an optimizer under a scenario, compute KPIs + evaluation, and persist the run."""
    req = payload or OptimizationRunRequest()
    return execution_service.run(
        db,
        optimizer=req.optimizer,
        scenario=req.scenario,
        warehouse_id=req.warehouse_id,
        max_shipments=req.max_shipments,
        max_stops=req.max_stops,
        sample_size=req.sample_size,
        strategy=req.strategy,
        reserve_inventory=req.reserve_inventory,
        evaluate_run=req.evaluate,
        persist=True,
    )


@router.post(
    "/simulate",
    response_model=OptimizationRunResult,
    summary="Simulate one optimization (a what-if) WITHOUT storing it",
)
def simulate_optimization(
    payload: OptimizationRunRequest | None = None,
    db: Session = Depends(get_db),
):
    """Run exactly like /run, but do not save the result to the history."""
    req = payload or OptimizationRunRequest()
    return execution_service.simulate(
        db,
        optimizer=req.optimizer,
        scenario=req.scenario,
        warehouse_id=req.warehouse_id,
        max_shipments=req.max_shipments,
        max_stops=req.max_stops,
        sample_size=req.sample_size,
        strategy=req.strategy,
        reserve_inventory=req.reserve_inventory,
        evaluate_run=req.evaluate,
    )


# ===========================================================================
# CATALOG + AGGREGATE (literal paths, declared before /{run_id})
# ===========================================================================
@router.get(
    "/scenarios",
    response_model=ScenariosResponse,
    summary="List the available optimization scenarios",
)
def list_scenarios():
    """Return the catalog of scenarios that /run and /simulate accept."""
    scenarios = execution_service.list_scenarios()
    return {"count": len(scenarios), "scenarios": scenarios}


@router.get(
    "/metrics",
    response_model=MetricsAggregateResponse,
    summary="Aggregate KPIs across the stored optimization runs",
)
def optimization_metrics(
    db: Session = Depends(get_db),
    scenario: str | None = Query(None, description="Only aggregate this scenario."),
    optimizer: str | None = Query(None, description="Only aggregate this optimizer."),
):
    """Summarise cost, distance, utilization, orders, and runtime across runs."""
    return optimization_run_service.aggregate_metrics(
        db, scenario=scenario, optimizer=optimizer
    )


@router.get(
    "/history",
    response_model=PaginatedResponse[OptimizationRunResponse],
    summary="List stored optimization runs (filter, search, sort, paginate)",
)
def optimization_history(
    db: Session = Depends(get_db),
    params: PageParams = Depends(pagination_params),
    search: str | None = Depends(search_query),
    scenario: str | None = Query(None, description="Filter by scenario."),
    optimizer: str | None = Query(None, description="Filter by optimizer."),
    warehouse_id: str | None = Query(None, description="Filter by target warehouse."),
    solver_status: str | None = Query(None, description="Filter by solver status."),
):
    """Return a page of past runs, newest first unless another sort is requested."""
    return optimization_run_service.list_history(
        db,
        params,
        filters={
            "scenario": scenario,
            "optimizer": optimizer,
            "warehouse_id": warehouse_id,
            "solver_status": solver_status,
        },
        search=search,
    )


# ===========================================================================
# GET ONE BY ID  (declared LAST so literal paths win)
# ===========================================================================
@router.get(
    "/{run_id}",
    response_model=OptimizationRunResponse,
    summary="Get one stored optimization run by id",
)
def get_optimization_run(run_id: str, db: Session = Depends(get_db)):
    """Return a single stored run, or 404 if the id does not exist."""
    return optimization_run_service.get(db, run_id)
