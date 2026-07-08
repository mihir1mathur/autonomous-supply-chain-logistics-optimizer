"""
============================================================================
SCENARIOS  (Week 6)   -- "what if?" conditions for the optimizer to face
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT A "SCENARIO" IS (zero-knowledge version)
---------------------------------------------
  The optimizer normally runs on the data as it is today ("normal"). But real
  logistics teams must plan for OTHER conditions too: a holiday demand spike,
  half the vans breaking down, a fuel price jump, a supplier shipping late. A
  SCENARIO is one such condition, expressed as a small set of CHANGES applied to
  the optimizer's inputs before it solves. Nothing about the solver changes -
  only the numbers it is fed - so every scenario reuses the SAME Week 5 solvers.

THE SEVEN CORE SCENARIOS (Week 6 goals, Part 4)
-----------------------------------------------
  high_demand        - customers order more (package counts scaled up).
  low_demand         - a quiet period (package counts scaled down).
  vehicle_breakdown  - part of the fleet is out of action (fewer vehicles).
  warehouse_closed   - a site is shut (its warehouse inactive + fleet reduced).
  fuel_price_increase- driving costs more (per-km rate scaled up).
  supplier_delay     - stock is short and demand a little higher (more pending).
  priority_orders    - only the highest-priority shipments are served.

  Plus a "normal" baseline and three extra BENCHMARK scenarios reused by the
  Week 6 benchmark runner (Part 7): holiday, demand_spike, vehicle_failure.

HOW A SCENARIO IS APPLIED (pure transforms, no database, no solver)
-------------------------------------------------------------------
  Each scenario is just a set of numeric EFFECTS. The functions here take the
  plain Week 5 input dataclasses (ShipmentInput, VehicleInput, WarehouseInput)
  and the stock dictionary, and return MODIFIED copies plus a human-readable
  list of what changed. They never mutate the originals (dataclasses.replace
  makes copies) and never touch the database - the Week 6 execution service
  loads the real inputs, calls apply_scenario(), and passes the result to a
  solver. This keeps scenarios reusable and unit-testable.

HONESTY (same discipline as Week 2)
-----------------------------------
  The multipliers below are SIMULATED planning assumptions, not real Olist
  figures. They are chosen to be illustrative (a demand spike really does
  stress capacity), documented here in one place, and clearly labelled as the
  "what if" knobs of a planning tool.
============================================================================
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from optimization.solution_models import ShipmentInput, VehicleInput, WarehouseInput


# ===========================================================================
# THE EFFECTS a scenario applies to the inputs
# ===========================================================================
@dataclass(frozen=True)
class ScenarioEffects:
    """
    The numeric changes one scenario makes to the optimizer's inputs. Every
    field defaults to "no change", so `normal` is simply all defaults.
    """

    # Multiply every shipment's package_count (demand) by this (>=1 -> busier).
    demand_multiplier: float = 1.0
    # Keep this fraction of each warehouse's vehicles (1.0 = all; 0.5 = half
    # out of action). The kept vehicles are the first ones by id (deterministic).
    vehicle_keep_fraction: float = 1.0
    # Multiply every vehicle's cost_per_km by this (a fuel-price change).
    fuel_multiplier: float = 1.0
    # Multiply the tracked stock levels by this (<1 = a supplier shortfall).
    stock_multiplier: float = 1.0
    # Mark this many operating warehouses as "inactive" (a site closure).
    close_warehouses: int = 0
    # If true, keep only the highest-priority half of the shipments (largest
    # package counts first) - "serve the priority orders".
    priority_only: bool = False


@dataclass(frozen=True)
class Scenario:
    """One named scenario: a key, a friendly name/description, and its effects."""

    key: str
    name: str
    category: str          # baseline / demand / resource / cost / supply / priority
    description: str
    effects: ScenarioEffects


# ===========================================================================
# THE CATALOG  -- every scenario the execution layer knows about
# ===========================================================================
SCENARIOS: dict[str, Scenario] = {
    "normal": Scenario(
        key="normal",
        name="Normal Operations",
        category="baseline",
        description="Business as usual: the data exactly as it is, no changes.",
        effects=ScenarioEffects(),
    ),
    "high_demand": Scenario(
        key="high_demand",
        name="High Demand",
        category="demand",
        description="Customers order more than usual; package counts scaled up "
        "1.8x, stressing vehicle capacity.",
        effects=ScenarioEffects(demand_multiplier=1.8),
    ),
    "low_demand": Scenario(
        key="low_demand",
        name="Low Demand",
        category="demand",
        description="A quiet period; package counts scaled down to 0.5x, leaving "
        "the fleet with spare room.",
        effects=ScenarioEffects(demand_multiplier=0.5),
    ),
    "vehicle_breakdown": Scenario(
        key="vehicle_breakdown",
        name="Vehicle Breakdown",
        category="resource",
        description="Half the fleet is out of action (vehicle_keep_fraction 0.5); "
        "the remaining vehicles must absorb the work.",
        effects=ScenarioEffects(vehicle_keep_fraction=0.5),
    ),
    "warehouse_closed": Scenario(
        key="warehouse_closed",
        name="Warehouse Closed",
        category="resource",
        description="A site is shut: one operating warehouse is marked inactive "
        "and its fleet is cut in half.",
        effects=ScenarioEffects(close_warehouses=1, vehicle_keep_fraction=0.5),
    ),
    "fuel_price_increase": Scenario(
        key="fuel_price_increase",
        name="Fuel Price Increase",
        category="cost",
        description="Driving costs more: every vehicle's per-km rate scaled up "
        "1.5x, so the same plan costs more.",
        effects=ScenarioEffects(fuel_multiplier=1.5),
    ),
    "supplier_delay": Scenario(
        key="supplier_delay",
        name="Supplier Delay",
        category="supply",
        description="A supplier ships late: tracked stock cut to 0.4x and demand "
        "1.2x, so more demands fall through to pending.",
        effects=ScenarioEffects(stock_multiplier=0.4, demand_multiplier=1.2),
    ),
    "priority_orders": Scenario(
        key="priority_orders",
        name="Priority Orders",
        category="priority",
        description="Only the highest-priority (largest) half of the shipments "
        "are served - a triage under pressure.",
        effects=ScenarioEffects(priority_only=True),
    ),
    # ---- Extra scenarios the benchmark runner (Part 7) reuses -------------
    "holiday": Scenario(
        key="holiday",
        name="Holiday Peak",
        category="demand",
        description="A holiday peak: demand 1.6x, 20% of vehicles unavailable, "
        "fuel 1.1x - several pressures at once.",
        effects=ScenarioEffects(
            demand_multiplier=1.6, vehicle_keep_fraction=0.8, fuel_multiplier=1.1
        ),
    ),
    "demand_spike": Scenario(
        key="demand_spike",
        name="Demand Spike",
        category="demand",
        description="A sudden surge: package counts scaled up 2.5x, well beyond "
        "normal capacity.",
        effects=ScenarioEffects(demand_multiplier=2.5),
    ),
    "vehicle_failure": Scenario(
        key="vehicle_failure",
        name="Vehicle Failure",
        category="resource",
        description="A major fleet failure: only half the vehicles remain "
        "available (vehicle_keep_fraction 0.5).",
        effects=ScenarioEffects(vehicle_keep_fraction=0.5),
    ),
}

# The scenarios the Week 6 benchmark runner sweeps by default (Part 7 list:
# Normal, Holiday, Demand Spike, Vehicle Failure, Supplier Delay).
BENCHMARK_SCENARIOS: list[str] = [
    "normal",
    "holiday",
    "demand_spike",
    "vehicle_failure",
    "supplier_delay",
]


# ===========================================================================
# LOOKUP HELPERS
# ===========================================================================
def get_scenario(key: str) -> Scenario:
    """Return the Scenario for `key`, or raise ValueError with the allowed set."""
    scenario = SCENARIOS.get(key)
    if scenario is None:
        allowed = ", ".join(sorted(SCENARIOS))
        raise ValueError(f"Unknown scenario '{key}'. Allowed: {allowed}.")
    return scenario


def list_scenarios() -> list[dict]:
    """A JSON-friendly catalog of every scenario (for GET /optimization/scenarios)."""
    return [
        {
            "key": s.key,
            "name": s.name,
            "category": s.category,
            "description": s.description,
        }
        for s in SCENARIOS.values()
    ]


# ===========================================================================
# THE TRANSFORMS  -- apply a scenario's effects to a set of inputs
# ===========================================================================
@dataclass
class ScenarioApplication:
    """The result of applying a scenario: the modified inputs + what changed."""

    shipments: list[ShipmentInput]
    vehicles: list[VehicleInput]
    warehouses: list[WarehouseInput]
    stock: dict[tuple[str, str], int]
    changes: list[str] = field(default_factory=list)


def apply_scenario(
    key: str,
    shipments: list[ShipmentInput],
    vehicles: list[VehicleInput],
    warehouses: list[WarehouseInput],
    stock: dict[tuple[str, str], int],
) -> ScenarioApplication:
    """
    Apply scenario `key`'s effects to COPIES of the given inputs and return the
    modified inputs together with a human-readable list of what changed.

    The originals are never mutated (we build new dataclasses / dicts), so the
    caller can run several scenarios against the same freshly-loaded data.
    """
    scenario = get_scenario(key)
    e = scenario.effects
    changes: list[str] = []

    new_shipments = _apply_to_shipments(shipments, e, changes)
    new_vehicles = _apply_to_vehicles(vehicles, e, changes)
    new_warehouses = _apply_to_warehouses(warehouses, e, changes)
    new_stock = _apply_to_stock(stock, e, changes)

    if not changes:
        changes.append("No changes - baseline 'normal' conditions.")

    return ScenarioApplication(
        shipments=new_shipments,
        vehicles=new_vehicles,
        warehouses=new_warehouses,
        stock=new_stock,
        changes=changes,
    )


def _apply_to_shipments(
    shipments: list[ShipmentInput], e: ScenarioEffects, changes: list[str]
) -> list[ShipmentInput]:
    """Scale demand and/or keep only the priority half of the shipments."""
    result = list(shipments)

    if e.priority_only and result:
        # Highest-priority = largest package counts. Keep the top half (at least
        # one), deterministically, so a triage under pressure is reproducible.
        result = sorted(result, key=lambda s: -(s.package_count or 0))
        keep = max(1, math.ceil(len(result) / 2))
        dropped = len(shipments) - keep
        result = result[:keep]
        changes.append(
            f"Priority orders: kept the {keep} largest shipment(s), dropped {dropped}."
        )

    if e.demand_multiplier != 1.0:
        scaled: list[ShipmentInput] = []
        for s in result:
            new_pkgs = max(1, int(round((s.package_count or 0) * e.demand_multiplier)))
            scaled.append(replace(s, package_count=new_pkgs))
        result = scaled
        changes.append(
            f"Demand x{e.demand_multiplier}: package counts scaled "
            f"({'up' if e.demand_multiplier > 1 else 'down'})."
        )

    return result


def _apply_to_vehicles(
    vehicles: list[VehicleInput], e: ScenarioEffects, changes: list[str]
) -> list[VehicleInput]:
    """Reduce the fleet and/or scale the per-km cost (fuel price)."""
    result = list(vehicles)

    if e.vehicle_keep_fraction < 1.0 and result:
        # Reduce EACH warehouse's fleet by the same fraction so no single site is
        # left with zero vehicles while another keeps all of its.
        by_wh: dict[str | None, list[VehicleInput]] = {}
        for v in result:
            by_wh.setdefault(v.warehouse_id, []).append(v)
        kept: list[VehicleInput] = []
        for wh_vehicles in by_wh.values():
            keep = max(1, int(math.floor(len(wh_vehicles) * e.vehicle_keep_fraction)))
            kept.extend(wh_vehicles[:keep])
        dropped = len(result) - len(kept)
        result = kept
        if dropped > 0:
            changes.append(
                f"Fleet reduced: kept {len(kept)} of {len(vehicles)} vehicles "
                f"(fraction {e.vehicle_keep_fraction}), {dropped} out of action."
            )

    if e.fuel_multiplier != 1.0:
        result = [
            replace(v, cost_per_km=(v.cost_per_km or 0.0) * e.fuel_multiplier)
            for v in result
        ]
        changes.append(f"Fuel x{e.fuel_multiplier}: per-km costs scaled up.")

    return result


def _apply_to_warehouses(
    warehouses: list[WarehouseInput], e: ScenarioEffects, changes: list[str]
) -> list[WarehouseInput]:
    """Mark up to `close_warehouses` operating warehouses as inactive (a closure)."""
    if e.close_warehouses <= 0:
        return list(warehouses)

    result: list[WarehouseInput] = []
    closed = 0
    for w in warehouses:
        is_active = (w.operating_status or "").lower() == "active"
        if is_active and closed < e.close_warehouses:
            result.append(replace(w, operating_status="inactive"))
            closed += 1
        else:
            result.append(w)
    if closed > 0:
        changes.append(f"Warehouse closure: {closed} operating warehouse(s) set inactive.")
    return result


def _apply_to_stock(
    stock: dict[tuple[str, str], int], e: ScenarioEffects, changes: list[str]
) -> dict[tuple[str, str], int]:
    """Scale the tracked stock levels (a supplier shortfall reduces them)."""
    if e.stock_multiplier == 1.0:
        return dict(stock)
    new_stock = {k: int(math.floor((v or 0) * e.stock_multiplier)) for k, v in stock.items()}
    changes.append(f"Stock x{e.stock_multiplier}: tracked inventory scaled down.")
    return new_stock
