"""
============================================================================
WEEK 2 - VEHICLE GENERATION SCRIPT
Project: Supply Chain & Logistics Optimizer
Dataset: Brazilian E-Commerce Public Dataset by Olist
============================================================================

WHY DO LOGISTICS SYSTEMS NEED VEHICLE MANAGEMENT?
-------------------------------------------------
  Goods do not teleport. Every package that leaves a warehouse rides in a
  VEHICLE - a van or a truck - to reach the customer. To plan deliveries we
  must know what vehicles we have, where they are, and what they can carry.

WHY DO VEHICLES HAVE CAPACITY, AND WHY DOES IT MATTER?
------------------------------------------------------
  A vehicle can only hold so much weight and so many packages. A small van
  cannot carry a truck's load. CAPACITY is the limit. It matters because route
  planning (later, Week 3) must NOT overload a vehicle: if 200 packages need
  delivering but each van holds 60, you need at least 4 vans. Capacity turns
  "deliver everything" into a concrete, solvable plan.

WHY DOES VEHICLE AVAILABILITY MATTER?
-------------------------------------
  A vehicle that is already on a delivery, under maintenance, or off-shift
  cannot be assigned new work. The planner can only use AVAILABLE vehicles, so
  availability_status is a hard constraint on what can be scheduled right now.

WHAT IS REAL vs WHAT IS SIMULATED HERE
--------------------------------------
  REAL (from Olist, via simulation/warehouses.csv):
    - the warehouse each vehicle is based at, and that warehouse's city/state
  SIMULATED (invented here - Olist has NO carrier/vehicle data at all):
    - vehicle_type, capacity_kg, capacity_packages
    - current location, availability_status
    - cost_per_km, average_speed_kmph

OUTPUT
------
    simulation/vehicles.csv

GOLDEN RULE: READ simulation/warehouses.csv; WRITE only to simulation/.

HOW TO RUN
----------
    python notebooks/week2_generate_warehouses.py   # must run first
    python notebooks/week2_vehicle_generation.py
============================================================================
"""

import os
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# STEP 0: paths and reproducible randomness.
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SIM_DIR = os.path.join(PROJECT_ROOT, "simulation")
os.makedirs(SIM_DIR, exist_ok=True)

RANDOM_SEED = 42
rng = np.random.default_rng(RANDOM_SEED)

# Vehicle "spec sheet". Each type has a realistic weight + package capacity,
# a running cost per kilometre (fuel + wear, in our generic cost units), and a
# typical average speed (smaller vehicles weave through cities faster; big
# trucks are slower but carry far more). These ranges are documented assumptions.
VEHICLE_TYPES = {
    #                capacity_kg  capacity_packages  cost_per_km   avg_speed_kmph
    "van":          {"kg": 800,   "pkgs": 60,        "cost": 0.80, "speed": 55},
    "small_truck":  {"kg": 2500,  "pkgs": 180,       "cost": 1.30, "speed": 50},
    "medium_truck": {"kg": 6000,  "pkgs": 420,       "cost": 2.00, "speed": 45},
    "large_truck":  {"kg": 12000, "pkgs": 900,       "cost": 3.20, "speed": 40},
}

# Possible states a vehicle can be in right now (a hard constraint for planning).
AVAILABILITY = ["available", "on_delivery", "maintenance"]
AVAILABILITY_WEIGHTS = [0.60, 0.32, 0.08]   # most are free or out delivering


def banner(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def step(msg):
    print(f"  - {msg}")


def load_sim(file_name):
    return pd.read_csv(os.path.join(SIM_DIR, file_name))


def fleet_size_for(capacity):
    """
    Decide how many vehicles a warehouse keeps, from its (simulated) capacity.
    Bigger warehouses run bigger fleets. Simple tiers keep it understandable.
    """
    if capacity >= 4000:
        return 5
    if capacity >= 2500:
        return 4
    if capacity >= 1500:
        return 3
    if capacity >= 800:
        return 2
    return 1


def main():
    banner("WEEK 2 - VEHICLE GENERATION")
    print("Reading simulated warehouses; inventing a delivery fleet for each.")
    print(f"Writing simulated vehicles to: {SIM_DIR}")

    warehouses = load_sim("warehouses.csv")
    step(f"Loaded {len(warehouses):,} warehouses.")

    rows = []
    vehicle_counter = 0

    # Build a small fleet per warehouse. We loop warehouse-by-warehouse so each
    # vehicle starts out STATIONED at (and located at) its home warehouse.
    for _, wh in warehouses.iterrows():
        n_vehicles = fleet_size_for(wh["capacity"])

        # Bigger fleets skew toward bigger vehicles; small hubs use vans. We
        # weight the type choice by fleet size so a 5-vehicle hub is likely to
        # own at least one large truck, while a 1-vehicle hub just has a van.
        if n_vehicles >= 4:
            type_weights = [0.30, 0.30, 0.25, 0.15]   # van .. large_truck
        elif n_vehicles >= 2:
            type_weights = [0.45, 0.35, 0.18, 0.02]
        else:
            type_weights = [0.70, 0.25, 0.05, 0.00]

        chosen_types = rng.choice(
            list(VEHICLE_TYPES.keys()), size=n_vehicles, p=type_weights
        )

        for vtype in chosen_types:
            vehicle_counter += 1
            spec = VEHICLE_TYPES[vtype]

            # Capacities and speed get a small +/- jitter so vehicles of the
            # same type are not identical clones (real fleets vary by model/age).
            cap_kg = int(round(spec["kg"] * rng.uniform(0.9, 1.1)))
            cap_pkgs = int(round(spec["pkgs"] * rng.uniform(0.9, 1.1)))
            cost_km = round(spec["cost"] * rng.uniform(0.9, 1.1), 2)
            speed = int(round(spec["speed"] * rng.uniform(0.95, 1.05)))

            availability = rng.choice(AVAILABILITY, p=AVAILABILITY_WEIGHTS)

            rows.append({
                "vehicle_id": f"VEH-{vehicle_counter:05d}",      # SIMULATED key
                "warehouse_id": wh["warehouse_id"],              # REAL link (home base)
                "vehicle_type": vtype,                           # SIMULATED
                "capacity_kg": cap_kg,                           # SIMULATED
                "capacity_packages": cap_pkgs,                   # SIMULATED
                "current_location_city": wh["warehouse_city"],   # starts at home (REAL city)
                "current_location_state": wh["warehouse_state"], # REAL state
                "availability_status": availability,             # SIMULATED
                "cost_per_km": cost_km,                          # SIMULATED
                "average_speed_kmph": speed,                     # SIMULATED
            })

    vehicles = pd.DataFrame(rows)

    out_path = os.path.join(SIM_DIR, "vehicles.csv")
    vehicles.to_csv(out_path, index=False)
    step(f"Saved -> simulation/vehicles.csv  ({len(vehicles):,} rows)")

    # A short summary so the output is easy to sanity-check.
    by_type = vehicles["vehicle_type"].value_counts().to_dict()
    by_avail = vehicles["availability_status"].value_counts().to_dict()
    step(f"Fleet by type: {by_type}")
    step(f"Fleet by availability: {by_avail}")

    banner("DONE - vehicles generated")
    print("  Each row = one delivery vehicle based at a warehouse.")
    print("  Next: notebooks/week2_disruption_generation.py")
    print("  Reminder: data/ and processed/ were NOT modified.")


if __name__ == "__main__":
    main()
