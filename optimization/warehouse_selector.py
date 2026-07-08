"""
============================================================================
WAREHOUSE SELECTOR  (Week 5)
Project: Supply Chain & Logistics Optimizer
============================================================================

THE PROBLEM (in plain words)
----------------------------
  A demand arrives: "deliver `quantity` units of `product` to this place."
  Which warehouse should fulfil it? The rule for Week 5 is simple and sensible:
    - the warehouse must be operating ("active"),
    - it must actually hold enough stock of that product,
    - and among the warehouses that qualify, pick the NEAREST to the customer
      (nearest = shortest estimated road distance).
  If NO warehouse qualifies, the demand is marked PENDING (we could not serve
  it) rather than forcing a bad choice.

WHY THIS IS A "GREEDY" SELECTOR, NOT A CP-SAT SOLVE
---------------------------------------------------
  Each demand is decided on its own by a clear ranking rule (nearest feasible
  warehouse). That is a GREEDY heuristic: make the locally-best choice for each
  demand in turn. It is fast, easy to explain, and exactly right for "serve
  from the closest place that has stock". (A future week could upgrade this to
  a global facility-assignment optimization; the interface would not change.)

INVENTORY RESERVATION
---------------------
  When `reserve_inventory` is on (the default), each fulfilment DECREMENTS the
  running stock we track for that (warehouse, product). This stops two demands
  from both being promised the same last unit - the second correctly falls
  through to the next-nearest warehouse or to pending. Turn it off to score
  every demand against the original stock independently.

HOW IT CONNECTS TO WEEK 3
-------------------------
  `stock_by_warehouse_product` is built by the service from the inventory table
  (inventory.stock_level per (warehouse_id, product_id)); warehouse locations
  and operating_status come from the warehouses table. The selector itself is
  database-free - it only sees the plain input dataclasses.
============================================================================
"""

from __future__ import annotations

from optimization.config import OptimizationSettings, get_optimization_settings
from optimization.constraints import can_warehouse_serve
from optimization.solution_models import (
    DemandInput,
    WarehouseChoice,
    WarehouseInput,
    WarehouseSelectionSolution,
)
from optimization.utils import Timer, road_distance_km, safe_divide


class WarehouseSelector:
    """
    Choose the nearest in-stock, operating warehouse for each demand, marking
    a demand pending when none qualifies.
    """

    def __init__(self, settings: OptimizationSettings | None = None):
        self.settings = settings or get_optimization_settings()

    def solve(
        self,
        demands: list[DemandInput],
        warehouses: list[WarehouseInput],
        stock_by_warehouse_product: dict[tuple[str, str], int],
        *,
        reserve_inventory: bool = True,
    ) -> WarehouseSelectionSolution:
        """
        Return a WarehouseSelectionSolution.

        stock_by_warehouse_product maps (warehouse_id, product_id) -> stock_level.
        A missing key is treated as zero stock.
        """
        with Timer() as timer:
            solution = self._solve_inner(
                demands, warehouses, stock_by_warehouse_product, reserve_inventory
            )
        solution.execution_time_ms = timer.elapsed_ms
        return solution

    def _solve_inner(
        self,
        demands: list[DemandInput],
        warehouses: list[WarehouseInput],
        stock: dict[tuple[str, str], int],
        reserve_inventory: bool,
    ) -> WarehouseSelectionSolution:
        if not demands:
            return WarehouseSelectionSolution(
                success=True,
                status="OK",
                message="No demands to place - nothing to do.",
            )

        # Work on a COPY of the stock so reservation does not mutate the caller's
        # data (the service passes a fresh dict, but this keeps us safe anyway).
        remaining = dict(stock)

        choices: list[WarehouseChoice] = []
        assigned = 0
        pending = 0
        total_distance = 0.0

        for demand in demands:
            best_wh, best_distance = self._nearest_feasible(demand, warehouses, remaining)

            if best_wh is None:
                choices.append(
                    WarehouseChoice(
                        demand_id=demand.demand_id,
                        product_id=demand.product_id,
                        quantity=demand.quantity,
                        selected_warehouse_id=None,
                        distance_km=0.0,
                        status="pending",
                        reason="No operating warehouse holds enough stock of this product.",
                    )
                )
                pending += 1
                continue

            # Reserve the stock we just promised, so it cannot be double-booked.
            if reserve_inventory:
                key = (best_wh.warehouse_id, demand.product_id)
                remaining[key] = remaining.get(key, 0) - demand.quantity

            choices.append(
                WarehouseChoice(
                    demand_id=demand.demand_id,
                    product_id=demand.product_id,
                    quantity=demand.quantity,
                    selected_warehouse_id=best_wh.warehouse_id,
                    distance_km=round(best_distance, 2),
                    status="assigned",
                    reason="Nearest operating warehouse with sufficient stock.",
                )
            )
            assigned += 1
            total_distance += best_distance

        avg_distance = safe_divide(total_distance, assigned, default=0.0)
        message = (
            f"Placed {assigned} of {len(demands)} demand(s); {pending} pending. "
            f"Average distance {round(avg_distance, 2)} km."
        )
        return WarehouseSelectionSolution(
            success=True,
            status="OK",
            choices=choices,
            assigned_count=assigned,
            pending_count=pending,
            average_distance_km=round(avg_distance, 2),
            total_distance_km=round(total_distance, 2),
            message=message,
        )

    def _nearest_feasible(
        self,
        demand: DemandInput,
        warehouses: list[WarehouseInput],
        remaining_stock: dict[tuple[str, str], int],
    ) -> tuple[WarehouseInput | None, float]:
        """
        Return the (warehouse, road_distance_km) of the nearest warehouse that
        is operating and holds enough stock of the demanded product, or
        (None, 0.0) if none qualifies.
        """
        best_wh: WarehouseInput | None = None
        best_distance = float("inf")

        for wh in warehouses:
            stock = remaining_stock.get((wh.warehouse_id, demand.product_id), 0)
            if not can_warehouse_serve(wh, demand, stock):
                continue

            distance = road_distance_km(
                wh.latitude,
                wh.longitude,
                demand.destination_latitude,
                demand.destination_longitude,
                self.settings.winding_factor,
            )
            if distance < best_distance:
                best_distance = distance
                best_wh = wh

        if best_wh is None:
            return None, 0.0
        return best_wh, best_distance


# A ready-to-use instance for the common case (default settings).
warehouse_selector = WarehouseSelector()
