"""
============================================================================
OPTIMIZATION RUN SERVICE  (Week 6)   entity: optimization_runs
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SERVICE DOES
----------------------
  The execution_service WRITES optimization runs to the optimization_runs table.
  This service READS them back for the history endpoints:

      GET /optimization/history      -> list past runs (filter / sort / paginate)
      GET /optimization/{run_id}     -> one run by id
      GET /optimization/metrics      -> aggregate KPIs across the stored runs

WHY IT REUSES THE WEEK 4 BaseService (no new CRUD code)
-------------------------------------------------------
  Listing with filters + sorting + pagination and "get one by id (or 404)" are
  EXACTLY what the Week 4 BaseService already provides for the seven entities.
  A stored optimization run is just another table, so this service subclasses
  BaseService and only declares its safelists - the list/get logic is inherited
  unchanged. The one Week 6-specific addition is the metrics AGGREGATE, which is
  a small custom query.
============================================================================
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import OptimizationRun

from api.services.base_service import BaseService
from api.utils.pagination import PageParams


class OptimizationRunService(BaseService):
    model = OptimizationRun
    pk_name = "run_id"
    entity_name = "Optimization run"

    # Callers may filter history by which scenario / optimizer produced it,
    # by the target warehouse, and by the solver status.
    filterable_fields = {"scenario", "optimizer", "warehouse_id", "solver_status", "success"}
    # Free-text search across the descriptive string columns.
    searchable_fields = {"run_id", "scenario", "optimizer", "warehouse_id"}
    # Sortable columns: the timestamp (default view) and the headline KPIs.
    sortable_fields = {
        "created_at",
        "scenario",
        "optimizer",
        "total_cost",
        "travel_distance_km",
        "vehicle_utilization",
        "orders_fulfilled",
        "stockouts",
        "late_deliveries",
        "runtime_ms",
    }

    def list_history(
        self,
        db: Session,
        params: PageParams,
        *,
        filters: dict | None = None,
        search: str | None = None,
    ):
        """
        List stored runs. Defaults to newest-first when the caller does not ask
        for a specific sort, so "history" reads naturally as a timeline.
        """
        if params.sort_by is None:
            params.sort_by = "created_at"
            params.sort_dir = "desc"
        return self.list(db, params, filters=filters, search=search)

    def aggregate_metrics(
        self,
        db: Session,
        *,
        scenario: str | None = None,
        optimizer: str | None = None,
    ) -> dict:
        """
        Summarise the KPIs across the stored runs (optionally filtered by
        scenario and/or optimizer): how many runs, and the average / total of
        the headline metrics. Powers GET /optimization/metrics.
        """
        conditions = []
        if scenario is not None:
            conditions.append(OptimizationRun.scenario == scenario)
        if optimizer is not None:
            conditions.append(OptimizationRun.optimizer == optimizer)

        stmt = select(
            func.count().label("run_count"),
            func.coalesce(func.sum(OptimizationRun.total_cost), 0.0),
            func.coalesce(func.avg(OptimizationRun.total_cost), 0.0),
            func.coalesce(func.sum(OptimizationRun.travel_distance_km), 0.0),
            func.coalesce(func.avg(OptimizationRun.vehicle_utilization), 0.0),
            func.coalesce(func.sum(OptimizationRun.orders_fulfilled), 0),
            func.coalesce(func.sum(OptimizationRun.stockouts), 0),
            func.coalesce(func.sum(OptimizationRun.late_deliveries), 0),
            func.coalesce(func.avg(OptimizationRun.runtime_ms), 0.0),
        )
        if conditions:
            stmt = stmt.where(*conditions)
        row = db.execute(stmt).one()

        (
            run_count,
            total_cost,
            avg_cost,
            total_distance,
            avg_util,
            total_orders,
            total_stockouts,
            total_late,
            avg_runtime,
        ) = row

        # A small breakdown of how many runs exist per scenario (a handy index).
        per_scenario_rows = db.execute(
            select(OptimizationRun.scenario, func.count())
            .group_by(OptimizationRun.scenario)
            .order_by(func.count().desc())
        ).all()

        return {
            "run_count": int(run_count or 0),
            "filters": {"scenario": scenario, "optimizer": optimizer},
            "total_cost": round(float(total_cost or 0.0), 2),
            "average_cost": round(float(avg_cost or 0.0), 2),
            "total_distance_km": round(float(total_distance or 0.0), 2),
            "average_vehicle_utilization": round(float(avg_util or 0.0), 4),
            "total_orders_fulfilled": int(total_orders or 0),
            "total_stockouts": int(total_stockouts or 0),
            "total_late_deliveries": int(total_late or 0),
            "average_runtime_ms": round(float(avg_runtime or 0.0), 3),
            "runs_per_scenario": {scn: int(cnt) for scn, cnt in per_scenario_rows},
        }


# A ready-to-use singleton, mirroring the Week 4 / Week 5 services.
optimization_run_service = OptimizationRunService()
