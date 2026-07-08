"""
============================================================================
OPTIMIZATION EXECUTION SERVICE  (Week 6)   -- run, measure, evaluate, store
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SERVICE IS (and how it sits ON TOP of Week 5)
-------------------------------------------------------
  Week 5 built the optimization ENGINE and a bridge service
  (api/services/optimization_service.py) that reads the database, calls a
  solver, and returns a plan. Week 6 adds the EXECUTION LAYER: one clean service
  that turns a single request into a complete, recorded outcome:

      1. LOAD the real inputs from the Week 3 database (the same rows Week 5
         reads: warehouses, vehicles, inventory, delivery routes).
      2. APPLY a SCENARIO (optimization/scenarios.py) - "high demand",
         "vehicle breakdown", ... - to those inputs.
      3. SOLVE with the Week 5 OR-Tools solvers (reused unchanged).
      4. MEASURE the run's KPIs (optimization/metrics.py, Week 6 Part 5).
      5. EVALUATE it against an un-optimized baseline
         (optimization/evaluation.py, Week 6 Part 6).
      6. PERSIST the run to the optimization_runs table so it appears in the
         history and the metrics aggregate.

  It reuses Week 5 and Week 4 without changing either: the solver singletons,
  the Week 3 models, and the Week 4 error envelope. The Week 5 service still
  serves the raw /optimize/* endpoints; this service powers the new
  /optimization/* endpoints. Neither is modified.

WHY THE LOGIC LIVES HERE, NOT IN THE ROUTER (the Week 4 rule, kept)
-------------------------------------------------------------------
  Routers stay thin (HTTP only). All of the "load -> scenario -> solve ->
  measure -> evaluate -> store" business logic lives in this one service, so it
  is testable without HTTP and reusable by later weeks (agents, dashboards).

SELF-CONTAINED LOADING (documented duplication)
-----------------------------------------------
  This service reads the SAME rows the Week 5 service reads, but it loads them
  itself so it can apply a scenario's effects BETWEEN loading and solving. That
  is a small, deliberate repetition (a scenario-aware loader), not a rewrite of
  Week 5 - the Week 5 service is left exactly as it was.
============================================================================
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import DeliveryRoute, Inventory, OptimizationRun, Vehicle, Warehouse

from api.utils.exceptions import BadRequestError, NotFoundError
from optimization.assignment_solver import assignment_solver
from optimization.config import get_optimization_settings
from optimization.evaluation import (
    EvaluationResult,
    evaluate,
    naive_assignment,
    naive_warehouse_selection,
)
from optimization.execution_config import get_execution_settings
from optimization.metrics import (
    RunMetrics,
    inventory_holding_cost,
    metrics_from_assignment,
    metrics_from_fleet,
    metrics_from_plan,
    metrics_from_route,
    metrics_from_warehouse,
)
from optimization.route_optimizer import route_optimizer
from optimization.scenarios import (
    apply_scenario,
    get_scenario,
    list_scenarios as _catalog_scenarios,
)
from optimization.solution_models import DemandInput, ShipmentInput, VehicleInput, WarehouseInput
from optimization.utils import simulated_package_demand
from optimization.vehicle_optimizer import vehicle_optimizer
from optimization.warehouse_selector import warehouse_selector

# Only vehicles in this state may be dispatched (same rule as Week 5).
_DISPATCHABLE_STATUS = "available"

# The optimizers this execution layer can run (the four Week 5 problems).
_OPTIMIZERS = {"assignment", "fleet", "routes", "warehouse"}


class OptimizationExecutionService:
    """
    Runs an optimization end to end - load, scenario, solve, measure, evaluate,
    store - and reads back the stored history. Holds no per-request state; it
    just carries the Week 5 and Week 6 settings.
    """

    def __init__(self):
        self.opt_settings = get_optimization_settings()      # Week 5 caps/limits.
        self.exec_settings = get_execution_settings()        # Week 6 KPI pricing.

    # =======================================================================
    # PUBLIC: the scenario catalog (for GET /optimization/scenarios)
    # =======================================================================
    def list_scenarios(self) -> list[dict]:
        """Return the JSON-friendly catalog of every available scenario."""
        return _catalog_scenarios()

    # =======================================================================
    # PUBLIC: run / simulate one optimization
    # =======================================================================
    def run(
        self,
        db: Session,
        *,
        optimizer: str = "assignment",
        scenario: str = "normal",
        warehouse_id: str | None = None,
        max_shipments: int | None = None,
        max_stops: int | None = None,
        sample_size: int | None = None,
        strategy: str | None = None,
        reserve_inventory: bool = True,
        evaluate_run: bool = True,
        persist: bool = True,
    ) -> dict:
        """
        Run one optimization under a scenario and return the full result.

        `optimizer` is one of assignment / fleet / routes / warehouse.
        `scenario` is a key from the catalog (default "normal" = no changes).
        When `persist` is true (the default) the run is saved to the
        optimization_runs table and the result carries its run_id; a "simulate"
        call sets persist=False for a throwaway what-if.
        """
        if optimizer not in _OPTIMIZERS:
            allowed = ", ".join(sorted(_OPTIMIZERS))
            raise BadRequestError(
                f"Unknown optimizer '{optimizer}'. Allowed: {allowed}."
            )
        # Validate the scenario up front so a bad key is a clean 400 (not a 500).
        try:
            scenario_obj = get_scenario(scenario)
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        # Dispatch to the per-optimizer runner. Each returns a common bundle.
        if optimizer in ("assignment", "fleet"):
            bundle = self._run_assignment_like(
                db, optimizer, scenario, warehouse_id, max_shipments, evaluate_run
            )
        elif optimizer == "routes":
            bundle = self._run_routes(db, scenario, warehouse_id, max_stops, strategy)
        else:  # warehouse
            bundle = self._run_warehouse(
                db, scenario, sample_size, reserve_inventory, evaluate_run
            )

        metrics: RunMetrics = bundle["metrics"]
        evaluation: EvaluationResult | None = bundle.get("evaluation")

        result = {
            "run_id": None,
            "persisted": False,
            "optimizer": optimizer,
            "scenario": scenario,
            "scenario_name": scenario_obj.name,
            "warehouse_id": bundle.get("warehouse_id"),
            "success": bundle["success"],
            "solver_status": metrics.solver_status,
            "created_at": None,
            "scenario_changes": bundle["changes"],
            "metrics": metrics.as_dict(),
            "evaluation": evaluation.as_dict() if evaluation else None,
            "message": bundle["message"],
        }

        if persist:
            run_id, created_at = self._persist(db, result, bundle)
            result["run_id"] = run_id
            result["persisted"] = True
            result["created_at"] = created_at.isoformat()

        return result

    def simulate(self, db: Session, **kwargs) -> dict:
        """
        A what-if: run exactly like run() but DO NOT store the result. Handy for
        trying a scenario without cluttering the history. Forces persist=False.
        """
        kwargs["persist"] = False
        return self.run(db, **kwargs)

    # =======================================================================
    # PUBLIC: run a whole benchmark sweep (Week 6, Part 7)
    # =======================================================================
    def run_benchmark(
        self,
        db: Session,
        *,
        scenarios: list[str],
        optimizer: str = "assignment",
        warehouse_id: str | None = None,
        max_shipments: int | None = None,
        persist: bool = True,
    ) -> dict:
        """
        Run the SAME optimizer under several scenarios and return one report:
        a row of KPIs per scenario plus the baseline for comparison. Reused by
        notebooks/week6_benchmark_runner.py.
        """
        rows: list[dict] = []
        for key in scenarios:
            outcome = self.run(
                db,
                optimizer=optimizer,
                scenario=key,
                warehouse_id=warehouse_id,
                max_shipments=max_shipments,
                evaluate_run=True,
                persist=persist,
            )
            rows.append(outcome)
        return {
            "optimizer": optimizer,
            "warehouse_id": rows[0]["warehouse_id"] if rows else None,
            "scenario_count": len(rows),
            "runs": rows,
        }

    # =======================================================================
    # PER-OPTIMIZER RUNNERS
    # =======================================================================
    def _run_assignment_like(
        self,
        db: Session,
        optimizer: str,
        scenario: str,
        warehouse_id: str | None,
        max_shipments: int | None,
        do_eval: bool,
    ) -> dict:
        """Run assignment or fleet balancing under a scenario, with evaluation."""
        warehouse_id = self._resolve_dispatch_warehouse(db, warehouse_id)
        limit = self._clamp(max_shipments, self.opt_settings.max_shipments_per_request)

        # 1) load the real inputs, then 2) apply the scenario's effects.
        shipments = self._load_shipments(db, warehouse_id, limit)
        vehicles = self._load_vehicles(db, warehouse_id)
        warehouses = self._load_all_warehouses(db)
        stock = {}  # not needed by assignment/fleet, but keeps apply_scenario uniform.
        applied = apply_scenario(scenario, shipments, vehicles, warehouses, stock)
        shipments, vehicles = applied.shipments, applied.vehicles

        if not vehicles:
            raise BadRequestError(
                f"Warehouse '{warehouse_id}' has no available vehicles after the "
                f"'{scenario}' scenario, so nothing can be dispatched."
            )

        # Context the KPIs need but the Solution objects do not carry.
        wh_util = self._warehouse_utilization(db, warehouse_id)
        holding = inventory_holding_cost(
            self._holding_units_for_warehouse(db, warehouse_id), self.exec_settings
        )
        distance_by_shipment = {s.shipment_id: (s.distance_km or 0.0) for s in shipments}
        cost_by_vehicle = {v.vehicle_id: v.cost_per_km for v in vehicles}

        # 3) solve with the reused Week 5 solver.
        if optimizer == "assignment":
            solution = assignment_solver.solve(shipments, vehicles)
            after = metrics_from_assignment(
                solution,
                distance_by_shipment=distance_by_shipment,
                cost_per_km_by_vehicle=cost_by_vehicle,
                warehouse_utilization=wh_util,
                inventory_holding_cost=holding,
                settings=self.exec_settings,
            )
            has_peak = False
        else:  # fleet
            solution = vehicle_optimizer.solve(shipments, vehicles)
            after = metrics_from_fleet(
                solution,
                distance_by_shipment=distance_by_shipment,
                cost_per_km_by_vehicle=cost_by_vehicle,
                warehouse_utilization=wh_util,
                inventory_holding_cost=holding,
                settings=self.exec_settings,
            )
            has_peak = True

        # 5) evaluate against the un-optimized "before" baseline (same inputs).
        evaluation = None
        if do_eval:
            n_assign, n_loads, n_unassigned = naive_assignment(shipments, vehicles)
            before = metrics_from_plan(
                optimizer,
                n_assign,
                n_loads,
                n_unassigned,
                status="BASELINE",
                runtime_ms=0.0,
                distance_by_shipment=distance_by_shipment,
                cost_per_km_by_vehicle=cost_by_vehicle,
                warehouse_utilization=wh_util,
                inventory_holding_cost=holding,
                has_peak=has_peak,
                settings=self.exec_settings,
            )
            evaluation = evaluate(before, after)

        return {
            "metrics": after,
            "evaluation": evaluation,
            "warehouse_id": warehouse_id,
            "success": solution.success,
            "changes": applied.changes,
            "message": solution.message,
            "details": {
                "scenario_changes": applied.changes,
                "shipments_considered": len(shipments),
                "vehicles_available": len(vehicles),
            },
        }

    def _run_routes(
        self,
        db: Session,
        scenario: str,
        warehouse_id: str | None,
        max_stops: int | None,
        strategy: str | None,
    ) -> dict:
        """Order a warehouse's stops under a scenario (routing distance is the KPI)."""
        warehouse_id = self._resolve_route_warehouse(db, warehouse_id)
        limit = self._clamp(max_stops, self.opt_settings.max_route_stops_per_request)

        warehouse_row = db.get(Warehouse, warehouse_id)
        warehouse = self._to_warehouse_input(warehouse_row)
        stops = self._load_shipments(db, warehouse_id, limit)
        applied = apply_scenario(scenario, stops, [], [warehouse], {})
        stops = applied.shipments

        if not stops:
            raise BadRequestError(
                f"Warehouse '{warehouse_id}' has no delivery routes to optimize "
                f"under the '{scenario}' scenario."
            )
        try:
            solution = route_optimizer.solve(warehouse, stops, strategy=strategy)
        except NotImplementedError as exc:
            raise BadRequestError(str(exc)) from exc
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        wh_util = self._warehouse_utilization(db, warehouse_id)
        holding = inventory_holding_cost(
            self._holding_units_for_warehouse(db, warehouse_id), self.exec_settings
        )
        after = metrics_from_route(
            solution,
            warehouse_utilization=wh_util,
            inventory_holding_cost=holding,
            settings=self.exec_settings,
        )

        # The route optimizer already reports its own "before": the naive
        # (arrival-order) distance. Build a before-metrics from it so the
        # evaluation framework can express the reduction consistently.
        before = RunMetrics(
            optimizer="routes",
            total_cost=round(solution.naive_distance_km * self.exec_settings.default_cost_per_km, 2),
            travel_distance_km=solution.naive_distance_km,
            orders_fulfilled=solution.stop_count,
            solver_status="BASELINE",
        )
        evaluation = evaluate(before, after)

        return {
            "metrics": after,
            "evaluation": evaluation,
            "warehouse_id": warehouse_id,
            "success": solution.success,
            "changes": applied.changes,
            "message": solution.message,
            "details": {
                "scenario_changes": applied.changes,
                "stops_considered": len(stops),
                "strategy": solution.strategy,
            },
        }

    def _run_warehouse(
        self,
        db: Session,
        scenario: str,
        sample_size: int | None,
        reserve_inventory: bool,
        do_eval: bool,
    ) -> dict:
        """Choose the nearest in-stock warehouse per demand, under a scenario."""
        size = self._clamp(
            sample_size or 20, self.opt_settings.max_warehouse_demands_per_request
        )
        demands = self._sample_demands(db, size)
        if not demands:
            raise BadRequestError(
                "No demands could be sampled from the database for warehouse selection."
            )

        warehouses = self._load_all_warehouses(db)
        product_ids = {d.product_id for d in demands}
        stock = self._load_stock(db, product_ids)

        # The scenario can close warehouses and shrink stock (a supplier delay).
        applied = apply_scenario(scenario, [], [], warehouses, stock)
        warehouses, stock = applied.warehouses, applied.stock

        solution = warehouse_selector.solve(
            demands, warehouses, stock, reserve_inventory=reserve_inventory
        )

        holding = inventory_holding_cost(self._holding_units_for_stock(stock), self.exec_settings)
        after = metrics_from_warehouse(
            solution,
            warehouse_utilization=0.0,   # selection spans many warehouses.
            inventory_holding_cost=holding,
            settings=self.exec_settings,
        )

        # Baseline for warehouse selection: serve each demand from the FIRST
        # operating, in-stock warehouse found (ignore distance). The Week 5
        # selector picks the NEAREST, so its total distance should be shorter.
        evaluation = None
        if do_eval:
            before_solution = naive_warehouse_selection(
                demands, warehouses, stock, self.opt_settings.winding_factor
            )
            before = metrics_from_warehouse(
                before_solution,
                warehouse_utilization=0.0,
                inventory_holding_cost=holding,
                settings=self.exec_settings,
            )
            evaluation = evaluate(before, after)

        return {
            "metrics": after,
            "evaluation": evaluation,
            "warehouse_id": None,
            "success": solution.success,
            "changes": applied.changes,
            "message": solution.message,
            "details": {
                "scenario_changes": applied.changes,
                "demands_considered": len(demands),
                "warehouses_considered": len(warehouses),
            },
        }

    # =======================================================================
    # PERSISTENCE  -- save one run to the optimization_runs table
    # =======================================================================
    def _persist(self, db: Session, result: dict, bundle: dict) -> tuple[str, datetime]:
        """Insert one OptimizationRun row and return its (run_id, created_at)."""
        m = result["metrics"]
        run_id = "RUN-" + uuid.uuid4().hex[:12]
        created_at = datetime.now(timezone.utc)
        row = OptimizationRun(
            run_id=run_id,
            created_at=created_at,
            scenario=result["scenario"],
            optimizer=result["optimizer"],
            warehouse_id=result["warehouse_id"],
            success=result["success"],
            solver_status=result["solver_status"],
            total_cost=m["total_cost"],
            travel_distance_km=m["travel_distance_km"],
            vehicle_utilization=m["vehicle_utilization"],
            warehouse_utilization=m["warehouse_utilization"],
            inventory_holding_cost=m["inventory_holding_cost"],
            stockouts=m["stockouts"],
            late_deliveries=m["late_deliveries"],
            orders_fulfilled=m["orders_fulfilled"],
            runtime_ms=m["optimization_runtime_ms"],
            num_constraints=m["num_constraints"],
            num_variables=m["num_variables"],
            vehicles_used=m["vehicles_used"],
            metrics=m,
            evaluation=result["evaluation"],
            details=bundle.get("details"),
        )
        db.add(row)
        db.commit()
        return run_id, created_at

    # =======================================================================
    # HELPERS: resolving a default warehouse (same rules as Week 5)
    # =======================================================================
    def _resolve_dispatch_warehouse(self, db: Session, warehouse_id: str | None) -> str:
        """Validate a given id, or pick the warehouse with the most available vehicles + routes."""
        if warehouse_id is not None:
            if db.get(Warehouse, warehouse_id) is None:
                raise NotFoundError(f"Warehouse '{warehouse_id}' was not found.")
            return warehouse_id

        rows = db.execute(
            select(Vehicle.warehouse_id, func.count())
            .where(Vehicle.availability_status == _DISPATCHABLE_STATUS)
            .group_by(Vehicle.warehouse_id)
            .order_by(func.count().desc())
        ).all()
        for wid, _count in rows:
            if wid is None:
                continue
            has_route = db.execute(
                select(DeliveryRoute.route_id).where(DeliveryRoute.warehouse_id == wid).limit(1)
            ).first()
            if has_route is not None:
                return wid
        raise BadRequestError(
            "Could not find any warehouse with both available vehicles and "
            "delivery routes to optimize."
        )

    def _resolve_route_warehouse(self, db: Session, warehouse_id: str | None) -> str:
        """Validate a given id, or pick the warehouse with the most delivery routes."""
        if warehouse_id is not None:
            if db.get(Warehouse, warehouse_id) is None:
                raise NotFoundError(f"Warehouse '{warehouse_id}' was not found.")
            return warehouse_id
        row = db.execute(
            select(DeliveryRoute.warehouse_id, func.count())
            .where(DeliveryRoute.warehouse_id.is_not(None))
            .group_by(DeliveryRoute.warehouse_id)
            .order_by(func.count().desc())
            .limit(1)
        ).first()
        if row is None:
            raise BadRequestError("No delivery routes exist to optimize.")
        return row[0]

    # =======================================================================
    # HELPERS: loading + mapping rows into engine inputs (mirrors Week 5)
    # =======================================================================
    def _load_shipments(self, db: Session, warehouse_id: str, limit: int) -> list[ShipmentInput]:
        rows = (
            db.execute(
                select(DeliveryRoute)
                .where(DeliveryRoute.warehouse_id == warehouse_id)
                .order_by(DeliveryRoute.route_id)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [
            ShipmentInput(
                shipment_id=r.route_id,
                warehouse_id=r.warehouse_id,
                package_count=simulated_package_demand(
                    r.route_id,
                    self.opt_settings.min_packages_per_shipment,
                    self.opt_settings.max_packages_per_shipment,
                ),
                destination_city=r.destination_city,
                destination_state=r.destination_state,
                destination_latitude=r.destination_latitude,
                destination_longitude=r.destination_longitude,
                distance_km=r.estimated_distance_km,
            )
            for r in rows
        ]

    def _load_vehicles(self, db: Session, warehouse_id: str) -> list[VehicleInput]:
        rows = (
            db.execute(
                select(Vehicle)
                .where(Vehicle.warehouse_id == warehouse_id)
                .where(Vehicle.availability_status == _DISPATCHABLE_STATUS)
                .order_by(Vehicle.vehicle_id)
            )
            .scalars()
            .all()
        )
        return [
            VehicleInput(
                vehicle_id=v.vehicle_id,
                warehouse_id=v.warehouse_id,
                capacity_packages=int(v.capacity_packages or 0),
                capacity_kg=v.capacity_kg,
                cost_per_km=v.cost_per_km,
                average_speed_kmph=v.average_speed_kmph,
            )
            for v in rows
        ]

    def _load_all_warehouses(self, db: Session) -> list[WarehouseInput]:
        rows = db.execute(select(Warehouse)).scalars().all()
        return [self._to_warehouse_input(w) for w in rows]

    @staticmethod
    def _to_warehouse_input(row: Warehouse | None) -> WarehouseInput:
        if row is None:
            return WarehouseInput(warehouse_id="UNKNOWN")
        return WarehouseInput(
            warehouse_id=row.warehouse_id,
            latitude=row.latitude,
            longitude=row.longitude,
            capacity=row.capacity,
            current_utilization=row.current_utilization,
            operating_status=row.operating_status,
        )

    def _load_stock(self, db: Session, product_ids: set[str]) -> dict[tuple[str, str], int]:
        if not product_ids:
            return {}
        rows = db.execute(
            select(Inventory.warehouse_id, Inventory.product_id, Inventory.stock_level)
            .where(Inventory.product_id.in_(product_ids))
        ).all()
        return {(wid, pid): int(stock or 0) for wid, pid, stock in rows}

    def _sample_demands(self, db: Session, size: int) -> list[DemandInput]:
        """Sample demands from real inventory + route destinations (as in Week 5)."""
        product_rows = db.execute(
            select(
                Inventory.product_id,
                func.count(func.distinct(Inventory.warehouse_id)).label("n"),
            )
            .group_by(Inventory.product_id)
            .order_by(func.count(func.distinct(Inventory.warehouse_id)).desc())
            .limit(max(1, size))
        ).all()
        products = [pid for pid, _n in product_rows]
        if not products:
            return []
        route_rows = (
            db.execute(
                select(DeliveryRoute)
                .where(DeliveryRoute.destination_latitude.is_not(None))
                .order_by(DeliveryRoute.route_id)
                .limit(size)
            )
            .scalars()
            .all()
        )
        if not route_rows:
            return []
        demands: list[DemandInput] = []
        for i in range(min(size, len(route_rows))):
            route = route_rows[i]
            product_id = products[i % len(products)]
            demand_id = f"DEM-{i:04d}"
            quantity = simulated_package_demand(f"{demand_id}-{product_id}", 1, 40)
            demands.append(
                DemandInput(
                    demand_id=demand_id,
                    product_id=product_id,
                    quantity=quantity,
                    destination_city=route.destination_city,
                    destination_state=route.destination_state,
                    destination_latitude=route.destination_latitude,
                    destination_longitude=route.destination_longitude,
                )
            )
        return demands

    # =======================================================================
    # HELPERS: KPI context (warehouse utilization, inventory on hand)
    # =======================================================================
    def _warehouse_utilization(self, db: Session, warehouse_id: str) -> float:
        """The resolved warehouse's current_utilization (0..1), 0 if unknown."""
        row = db.get(Warehouse, warehouse_id)
        if row is None or row.current_utilization is None:
            return 0.0
        return float(row.current_utilization)

    def _holding_units_for_warehouse(self, db: Session, warehouse_id: str) -> int:
        """Total units of stock held at one warehouse (for its holding cost)."""
        total = db.execute(
            select(func.coalesce(func.sum(Inventory.stock_level), 0))
            .where(Inventory.warehouse_id == warehouse_id)
        ).scalar()
        return int(total or 0)

    @staticmethod
    def _holding_units_for_stock(stock: dict[tuple[str, str], int]) -> int:
        """Total units across a (warehouse, product) -> level stock dictionary."""
        return int(sum(max(0, v) for v in stock.values()))

    @staticmethod
    def _clamp(requested: int | None, maximum: int) -> int:
        if requested is None:
            return maximum
        return max(1, min(int(requested), maximum))


# A ready-to-use singleton, mirroring the Week 4 / Week 5 services.
execution_service = OptimizationExecutionService()
