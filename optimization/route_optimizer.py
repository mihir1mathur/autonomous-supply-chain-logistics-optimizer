"""
============================================================================
ROUTE OPTIMIZER  (Week 5, simplified)
Project: Supply Chain & Logistics Optimizer
============================================================================

THE PROBLEM (in plain words)
----------------------------
  A vehicle leaves a warehouse, must visit several delivery stops, and we want
  a SHORT order to visit them in. Visiting stops in a silly order (zig-zagging
  back and forth) burns distance, time, fuel, and money. Choosing a good order
  is the heart of route optimization.

WHAT WEEK 5 IMPLEMENTS: THE NEAREST-NEIGHBOUR HEURISTIC
-------------------------------------------------------
  A HEURISTIC is a quick, sensible rule of thumb that usually gives a good
  answer without guaranteeing the perfect one. Nearest-neighbour is the classic
  starter:
      1. Start at the warehouse.
      2. Repeatedly drive to the NEAREST stop you have not visited yet.
      3. Stop when every stop has been visited.
  It is fast, easy to explain, and typically far better than a random order -
  a great first optimizer and a baseline the "real" solver must beat later.

WHY IT IS ONLY A STARTING POINT (and the interface for the future)
------------------------------------------------------------------
  Nearest-neighbour is greedy: an early cheap hop can force an expensive one
  later, so it does not find the true shortest tour. The full problem is the
  Vehicle Routing Problem (VRP), which OR-Tools has a dedicated solver for
  (multiple vehicles, capacities, time windows). To keep Week 5 ready for that,
  routing is written behind a small STRATEGY interface:

      RoutingStrategy (abstract)
        - NearestNeighbourStrategy   <- implemented now
        - VehicleRoutingProblemStrategy <- placeholder, raises NotImplementedError

  A future week drops in the VRP strategy without touching the solver's callers:
  same inputs, same RouteSolution output. This is the Open/Closed principle from
  SOLID - open to a better algorithm, closed against rewrites of everything else.

DISTANCES
---------
  Legs use the same estimate as the rest of Week 5 and Week 2: haversine
  distance * winding factor. We also compute the NAIVE distance (the stops in
  the order they arrived) so we can report how much the optimizer saved.
============================================================================
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from optimization.config import OptimizationSettings, get_optimization_settings
from optimization.solution_models import RouteSolution, RouteStop, ShipmentInput, WarehouseInput
from optimization.utils import Timer, road_distance_km, safe_divide


# ===========================================================================
# STRATEGY INTERFACE  -- swappable routing algorithms (Open/Closed principle)
# ===========================================================================
class RoutingStrategy(ABC):
    """
    The contract every routing algorithm must fulfil: given a start point and a
    list of stops, return the ORDER (a list of indices into `stops`) to visit
    them in. Callers depend on this interface, not on a specific algorithm, so a
    better one can be swapped in later without changing them.
    """

    name: str = "abstract"

    @abstractmethod
    def order_stops(
        self,
        start_lat: float | None,
        start_lon: float | None,
        stops: list[ShipmentInput],
        winding_factor: float,
    ) -> list[int]:
        """Return the visiting order as indices into `stops`."""
        raise NotImplementedError


class NearestNeighbourStrategy(RoutingStrategy):
    """The greedy nearest-neighbour heuristic described in the file header."""

    name = "nearest_neighbor"

    def order_stops(
        self,
        start_lat: float | None,
        start_lon: float | None,
        stops: list[ShipmentInput],
        winding_factor: float,
    ) -> list[int]:
        n = len(stops)
        visited = [False] * n
        order: list[int] = []

        # We always start "standing at" the warehouse coordinates.
        current_lat, current_lon = start_lat, start_lon

        for _ in range(n):
            nearest = -1
            nearest_distance = float("inf")
            for i in range(n):
                if visited[i]:
                    continue
                distance = road_distance_km(
                    current_lat,
                    current_lon,
                    stops[i].destination_latitude,
                    stops[i].destination_longitude,
                    winding_factor,
                )
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest = i
            if nearest == -1:
                break
            visited[nearest] = True
            order.append(nearest)
            # Move to the chosen stop; the next hop is measured from here.
            current_lat = stops[nearest].destination_latitude
            current_lon = stops[nearest].destination_longitude

        return order


class VehicleRoutingProblemStrategy(RoutingStrategy):
    """
    PLACEHOLDER for a future OR-Tools VRP solver (multiple vehicles, capacities,
    time windows). Intentionally not implemented in Week 5: it exists so the
    interface and the wiring are ready. A later week fills in order_stops() (or
    a richer solve) using ortools.constraint_solver.routing_enums / RoutingModel.
    """

    name = "vrp"

    def order_stops(
        self,
        start_lat: float | None,
        start_lon: float | None,
        stops: list[ShipmentInput],
        winding_factor: float,
    ) -> list[int]:
        raise NotImplementedError(
            "The VRP strategy is reserved for a future week. Use "
            "'nearest_neighbor' for now."
        )


# The strategies this module knows about, by name (what the API accepts).
_STRATEGIES: dict[str, type[RoutingStrategy]] = {
    NearestNeighbourStrategy.name: NearestNeighbourStrategy,
    VehicleRoutingProblemStrategy.name: VehicleRoutingProblemStrategy,
}


class RouteOptimizer:
    """
    Order a warehouse's delivery stops into a short route using a chosen
    RoutingStrategy (nearest-neighbour by default) and report the distance saved
    versus the un-optimized order.
    """

    def __init__(self, settings: OptimizationSettings | None = None):
        self.settings = settings or get_optimization_settings()

    def available_strategies(self) -> list[str]:
        """The strategy names callers may request."""
        return list(_STRATEGIES.keys())

    def solve(
        self,
        warehouse: WarehouseInput,
        stops: list[ShipmentInput],
        *,
        strategy: str | None = None,
    ) -> RouteSolution:
        """
        Build an ordered route for `warehouse` visiting `stops`.

        Raises ValueError for an unknown strategy name and NotImplementedError
        for a strategy that is reserved for later (e.g. "vrp") - both surfaced
        as clean API errors by the service/router.
        """
        strategy_name = strategy or self.settings.default_route_strategy
        strategy_cls = _STRATEGIES.get(strategy_name)
        if strategy_cls is None:
            allowed = ", ".join(self.available_strategies())
            raise ValueError(
                f"Unknown routing strategy '{strategy_name}'. Allowed: {allowed}."
            )

        with Timer() as timer:
            solution = self._solve_with(strategy_cls(), warehouse, stops)
        solution.execution_time_ms = timer.elapsed_ms
        return solution

    def _solve_with(
        self,
        strategy: RoutingStrategy,
        warehouse: WarehouseInput,
        stops: list[ShipmentInput],
    ) -> RouteSolution:
        if not stops:
            return RouteSolution(
                success=True,
                status="OK",
                strategy=strategy.name,
                warehouse_id=warehouse.warehouse_id if warehouse else None,
                message="No stops to route.",
            )

        wf = self.settings.winding_factor
        start_lat = warehouse.latitude if warehouse else None
        start_lon = warehouse.longitude if warehouse else None

        # The optimized visiting order (indices into `stops`).
        order = strategy.order_stops(start_lat, start_lon, stops, wf)

        # Build the ordered stop list with running distances, beginning at the
        # warehouse itself as sequence 0.
        route_stops: list[RouteStop] = [
            RouteStop(
                sequence=0,
                node_id=warehouse.warehouse_id if warehouse else "START",
                city=None,
                state=None,
                latitude=start_lat,
                longitude=start_lon,
                leg_distance_km=0.0,
                cumulative_distance_km=0.0,
            )
        ]

        cumulative = 0.0
        prev_lat, prev_lon = start_lat, start_lon
        for seq, idx in enumerate(order, start=1):
            stop = stops[idx]
            leg = road_distance_km(
                prev_lat, prev_lon, stop.destination_latitude, stop.destination_longitude, wf
            )
            cumulative += leg
            route_stops.append(
                RouteStop(
                    sequence=seq,
                    node_id=stop.shipment_id,
                    city=stop.destination_city,
                    state=stop.destination_state,
                    latitude=stop.destination_latitude,
                    longitude=stop.destination_longitude,
                    leg_distance_km=round(leg, 2),
                    cumulative_distance_km=round(cumulative, 2),
                )
            )
            prev_lat, prev_lon = stop.destination_latitude, stop.destination_longitude

        optimized_distance = cumulative
        naive_distance = self._naive_distance(warehouse, stops, wf)
        reduction = max(0.0, naive_distance - optimized_distance)
        reduction_pct = safe_divide(reduction, naive_distance, default=0.0) * 100.0

        message = (
            f"Ordered {len(order)} stop(s) with '{strategy.name}': "
            f"{round(optimized_distance, 2)} km "
            f"(naive {round(naive_distance, 2)} km, "
            f"saved {round(reduction_pct, 1)}%)."
        )
        return RouteSolution(
            success=True,
            status="OK",
            strategy=strategy.name,
            warehouse_id=warehouse.warehouse_id if warehouse else None,
            stops=route_stops,
            total_distance_km=round(optimized_distance, 2),
            naive_distance_km=round(naive_distance, 2),
            distance_reduction_km=round(reduction, 2),
            distance_reduction_percent=round(reduction_pct, 1),
            stop_count=len(order),
            message=message,
        )

    @staticmethod
    def _naive_distance(
        warehouse: WarehouseInput,
        stops: list[ShipmentInput],
        winding_factor: float,
    ) -> float:
        """
        Total distance if we visited the stops in the order they arrived (no
        optimization). This is the baseline the optimized route is compared to.
        """
        total = 0.0
        prev_lat = warehouse.latitude if warehouse else None
        prev_lon = warehouse.longitude if warehouse else None
        for stop in stops:
            total += road_distance_km(
                prev_lat, prev_lon, stop.destination_latitude, stop.destination_longitude, winding_factor
            )
            prev_lat, prev_lon = stop.destination_latitude, stop.destination_longitude
        return total


# A ready-to-use instance for the common case (default settings).
route_optimizer = RouteOptimizer()
