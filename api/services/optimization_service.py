"""
============================================================================
OPTIMIZATION SERVICE  (Week 5)   -- the bridge: database <-> engine
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SERVICE DOES (and why it is the ONLY layer that touches both)
-----------------------------------------------------------------------
  The optimization engine (optimization/) is deliberately database-free: it
  speaks only in plain input dataclasses. The FastAPI routers are deliberately
  thin: they only speak HTTP. THIS service is the bridge between them, exactly
  like the seven Week 4 entity services:

      1. READ the Week 3 database with SQLAlchemy (warehouses, vehicles,
         inventory, delivery_routes).
      2. MAP those rows into the engine's input dataclasses (ShipmentInput,
         VehicleInput, WarehouseInput, DemandInput).
      3. CALL the right solver and return its solution dataclass.

  Routers never import the solvers or the models directly; they call this
  service. That keeps the layering identical to Week 4 (Router -> Service ->
  data), and means Week 7's agents can reuse these same methods.

SIMULATED SHIPMENT SIZE (documented honesty, like Week 2)
---------------------------------------------------------
  The Olist data has no per-shipment package count, so each delivery route's
  size is filled in with optimization.utils.simulated_package_demand() - a
  stable, deterministic stand-in. This is clearly simulated, never presented as
  real data, in keeping with the project's real-vs-simulated discipline.

SENSIBLE DEFAULTS (zero-setup endpoints)
----------------------------------------
  Every request may omit its target: if no warehouse_id is given, the service
  picks a suitable one (has vehicles and routes); if no demands are given, it
  builds a small sample from real inventory and route destinations. This makes
  each endpoint runnable with an empty body while still accepting precise input.
============================================================================
"""

from __future__ import annotations

import ortools
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import DeliveryRoute, Inventory, Vehicle, Warehouse

from api.utils.exceptions import BadRequestError, NotFoundError
from optimization.assignment_solver import assignment_solver
from optimization.config import get_optimization_settings
from optimization.route_optimizer import route_optimizer
from optimization.solution_models import (
    AssignmentSolution,
    DemandInput,
    FleetUtilizationSolution,
    RouteSolution,
    ShipmentInput,
    VehicleInput,
    WarehouseInput,
    WarehouseSelectionSolution,
)
from optimization.utils import simulated_package_demand
from optimization.vehicle_optimizer import vehicle_optimizer
from optimization.warehouse_selector import warehouse_selector

# Only vehicles in this state may be dispatched by the optimizer.
_DISPATCHABLE_STATUS = "available"


class OptimizationService:
    """
    Orchestrates the Week 5 optimization engine over the Week 3 database.

    Holds no per-request state; it just carries the optimization settings and
    exposes one method per optimization problem plus a status report.
    """

    def __init__(self):
        self.settings = get_optimization_settings()

    # =======================================================================
    # STATUS  -- is the engine ready, and what can it do?
    # =======================================================================
    def status(self) -> dict:
        """
        Report the engine's readiness and capabilities. Does NOT touch the
        database, so it stays a fast liveness/capability check (like /health).
        """
        s = self.settings
        return {
            "engine": "Google OR-Tools (CP-SAT) + heuristics",
            "ortools_version": getattr(ortools, "__version__", "unknown"),
            "available": True,
            "solvers": [
                "assignment (CP-SAT)",
                "warehouse_selection (nearest-feasible)",
                "fleet_utilization (CP-SAT)",
                "route (nearest_neighbor)",
            ],
            "route_strategies": route_optimizer.available_strategies(),
            "settings": {
                "solver_time_limit_seconds": s.solver_time_limit_seconds,
                "winding_factor": s.winding_factor,
                "min_packages_per_shipment": s.min_packages_per_shipment,
                "max_packages_per_shipment": s.max_packages_per_shipment,
                "overloaded_utilization": s.overloaded_utilization,
                "underutilized_utilization": s.underutilized_utilization,
                "max_shipments_per_request": s.max_shipments_per_request,
                "max_route_stops_per_request": s.max_route_stops_per_request,
                "max_warehouse_demands_per_request": s.max_warehouse_demands_per_request,
            },
        }

    # =======================================================================
    # 1) SHIPMENT ASSIGNMENT
    # =======================================================================
    def optimize_assignment(
        self,
        db: Session,
        *,
        warehouse_id: str | None = None,
        max_shipments: int | None = None,
    ) -> AssignmentSolution:
        """Assign a warehouse's waiting shipments to its available vehicles."""
        warehouse_id = self._resolve_dispatch_warehouse(db, warehouse_id)
        limit = self._clamp(max_shipments, self.settings.max_shipments_per_request)

        shipments = self._load_shipments(db, warehouse_id, limit)
        vehicles = self._load_vehicles(db, warehouse_id)
        if not vehicles:
            raise BadRequestError(
                f"Warehouse '{warehouse_id}' has no available vehicles to assign to."
            )
        return assignment_solver.solve(shipments, vehicles)

    # =======================================================================
    # 2) WAREHOUSE SELECTION
    # =======================================================================
    def select_warehouses(
        self,
        db: Session,
        *,
        demands: list[DemandInput] | None = None,
        sample_size: int | None = None,
        reserve_inventory: bool = True,
    ) -> WarehouseSelectionSolution:
        """
        Choose the nearest in-stock, operating warehouse for each demand. If no
        demands are supplied, build a sample from real inventory + destinations.
        """
        if demands is None:
            size = self._clamp(
                sample_size or 20, self.settings.max_warehouse_demands_per_request
            )
            demands = self._sample_demands(db, size)
        else:
            demands = demands[: self.settings.max_warehouse_demands_per_request]

        if not demands:
            raise BadRequestError(
                "No demands to place and none could be sampled from the database."
            )

        warehouses = self._load_warehouses(db)
        product_ids = {d.product_id for d in demands}
        stock = self._load_stock(db, product_ids)
        return warehouse_selector.solve(
            demands, warehouses, stock, reserve_inventory=reserve_inventory
        )

    # =======================================================================
    # 3) VEHICLE UTILIZATION
    # =======================================================================
    def optimize_fleet(
        self,
        db: Session,
        *,
        warehouse_id: str | None = None,
        max_shipments: int | None = None,
    ) -> FleetUtilizationSolution:
        """Balance a warehouse's shipments evenly across its available vehicles."""
        warehouse_id = self._resolve_dispatch_warehouse(db, warehouse_id)
        limit = self._clamp(max_shipments, self.settings.max_shipments_per_request)

        shipments = self._load_shipments(db, warehouse_id, limit)
        vehicles = self._load_vehicles(db, warehouse_id)
        if not vehicles:
            raise BadRequestError(
                f"Warehouse '{warehouse_id}' has no available vehicles to balance."
            )
        return vehicle_optimizer.solve(shipments, vehicles)

    # =======================================================================
    # 4) ROUTE OPTIMIZATION
    # =======================================================================
    def optimize_routes(
        self,
        db: Session,
        *,
        warehouse_id: str | None = None,
        max_stops: int | None = None,
        strategy: str | None = None,
    ) -> RouteSolution:
        """Order a warehouse's delivery stops into a short route."""
        warehouse_id = self._resolve_route_warehouse(db, warehouse_id)
        limit = self._clamp(max_stops, self.settings.max_route_stops_per_request)

        warehouse_row = db.get(Warehouse, warehouse_id)
        warehouse = self._to_warehouse_input(warehouse_row)
        stops = self._load_shipments(db, warehouse_id, limit)
        if not stops:
            raise BadRequestError(
                f"Warehouse '{warehouse_id}' has no delivery routes to optimize."
            )
        try:
            return route_optimizer.solve(warehouse, stops, strategy=strategy)
        except NotImplementedError as exc:
            # The 'vrp' strategy is reserved for later -> a clean 400, not a 500.
            raise BadRequestError(str(exc)) from exc
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

    # =======================================================================
    # HELPERS: resolving a default warehouse
    # =======================================================================
    def _resolve_dispatch_warehouse(
        self, db: Session, warehouse_id: str | None
    ) -> str:
        """
        Validate an explicit warehouse id, or pick a good default for
        assignment/fleet: the warehouse with the most AVAILABLE vehicles that
        also has at least one delivery route.
        """
        if warehouse_id is not None:
            if db.get(Warehouse, warehouse_id) is None:
                raise NotFoundError(f"Warehouse '{warehouse_id}' was not found.")
            return warehouse_id

        # warehouse_id -> count of available vehicles, most first.
        rows = (
            db.execute(
                select(Vehicle.warehouse_id, func.count())
                .where(Vehicle.availability_status == _DISPATCHABLE_STATUS)
                .group_by(Vehicle.warehouse_id)
                .order_by(func.count().desc())
            )
            .all()
        )
        for wid, _count in rows:
            if wid is None:
                continue
            has_route = db.execute(
                select(DeliveryRoute.route_id)
                .where(DeliveryRoute.warehouse_id == wid)
                .limit(1)
            ).first()
            if has_route is not None:
                return wid

        raise BadRequestError(
            "Could not find any warehouse with both available vehicles and "
            "delivery routes to optimize."
        )

    def _resolve_route_warehouse(self, db: Session, warehouse_id: str | None) -> str:
        """
        Validate an explicit warehouse id, or pick the warehouse with the most
        delivery routes (the most interesting one to route).
        """
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
    # HELPERS: loading + mapping database rows into engine inputs
    # =======================================================================
    def _load_shipments(
        self, db: Session, warehouse_id: str, limit: int
    ) -> list[ShipmentInput]:
        """A warehouse's delivery routes, as ShipmentInput (simulated sizes)."""
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
        shipments: list[ShipmentInput] = []
        for r in rows:
            shipments.append(
                ShipmentInput(
                    shipment_id=r.route_id,
                    warehouse_id=r.warehouse_id,
                    package_count=simulated_package_demand(
                        r.route_id,
                        self.settings.min_packages_per_shipment,
                        self.settings.max_packages_per_shipment,
                    ),
                    destination_city=r.destination_city,
                    destination_state=r.destination_state,
                    destination_latitude=r.destination_latitude,
                    destination_longitude=r.destination_longitude,
                    distance_km=r.estimated_distance_km,
                )
            )
        return shipments

    def _load_vehicles(self, db: Session, warehouse_id: str) -> list[VehicleInput]:
        """A warehouse's AVAILABLE vehicles, as VehicleInput."""
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

    def _load_warehouses(self, db: Session) -> list[WarehouseInput]:
        """Every warehouse as a WarehouseInput (for warehouse selection)."""
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

    def _load_stock(
        self, db: Session, product_ids: set[str]
    ) -> dict[tuple[str, str], int]:
        """(warehouse_id, product_id) -> stock_level for the demanded products."""
        if not product_ids:
            return {}
        rows = (
            db.execute(
                select(
                    Inventory.warehouse_id,
                    Inventory.product_id,
                    Inventory.stock_level,
                ).where(Inventory.product_id.in_(product_ids))
            )
            .all()
        )
        return {(wid, pid): int(stock or 0) for wid, pid, stock in rows}

    def _sample_demands(self, db: Session, size: int) -> list[DemandInput]:
        """
        Build a sample of `size` demands from REAL data: products that are
        stocked in the most warehouses (so nearest-selection has choices) paired
        with real route destinations (so distances are meaningful). Quantities
        are simulated and deliberately varied so some demands exceed the stock on
        hand and correctly fall through to 'pending'.
        """
        # Products with the widest warehouse coverage.
        product_rows = (
            db.execute(
                select(
                    Inventory.product_id,
                    func.count(func.distinct(Inventory.warehouse_id)).label("n"),
                )
                .group_by(Inventory.product_id)
                .order_by(func.count(func.distinct(Inventory.warehouse_id)).desc())
                .limit(max(1, size))
            )
            .all()
        )
        products = [pid for pid, _n in product_rows]
        if not products:
            return []

        # Real destinations from delivery routes.
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
            # Varied quantity 1..40 so some demands exceed low stock -> pending.
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

    @staticmethod
    def _clamp(requested: int | None, maximum: int) -> int:
        """Clamp a requested size to the configured maximum (default = maximum)."""
        if requested is None:
            return maximum
        return max(1, min(int(requested), maximum))


# A ready-to-use singleton, mirroring the Week 4 entity services.
optimization_service = OptimizationService()
