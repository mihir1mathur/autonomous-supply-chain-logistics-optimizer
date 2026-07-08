"""
============================================================================
WEEK 2 - DISRUPTION GENERATION SCRIPT
Project: Supply Chain & Logistics Optimizer
Dataset: Brazilian E-Commerce Public Dataset by Olist
============================================================================

WHAT IS A DISRUPTION?
---------------------
  A DISRUPTION is anything that gets in the way of a smooth delivery:
  heavy traffic, a storm, a flooded road, a warehouse that is too full to ship,
  or a product that has run out. In the real world these happen constantly and
  they make deliveries late.

WHY DO WE SIMULATE DISRUPTIONS?
-------------------------------
  The Olist dataset is HISTORICAL - a frozen record of orders from 2016-2018.
  It contains NO live traffic, NO weather, NO road closures. But a logistics
  system earns its keep precisely when things go wrong: it must notice a
  problem and RE-PLAN around it. To build and test that behaviour later, we
  need problems to react to. So we invent a realistic set of disruptions now.

  These simulated disruptions are the raw material the later optimization and
  agent layers (Week 3 / Week 5 / Week 7) will use to trigger re-routing and
  re-stocking decisions.

DISRUPTION TYPES WE GENERATE
----------------------------
  heavy_traffic       - congestion slows vehicles in a city.
  severe_weather      - storms / heavy rain delay or stop deliveries.
  warehouse_overload  - a warehouse is too full / backed up to ship on time.
  inventory_shortage  - a needed product has run out at a warehouse.
  road_closure        - a route is physically blocked (accident, flooding).

WHAT IS REAL vs WHAT IS SIMULATED HERE
--------------------------------------
  REAL (from Olist, via simulation/warehouses.csv):
    - the cities / states / warehouses a disruption can land on
  SIMULATED (entirely invented - none of this is in Olist):
    - the disruption events themselves, their severity, timing, delay impact,
      and status.

OUTPUT
------
    simulation/disruptions.csv

GOLDEN RULE: READ simulation/warehouses.csv; WRITE only to simulation/.

HOW TO RUN
----------
    python notebooks/week2_generate_warehouses.py   # must run first
    python notebooks/week2_disruption_generation.py
============================================================================
"""

import os
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# STEP 0: paths, seed, fixed "simulated present", and tunables.
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SIM_DIR = os.path.join(PROJECT_ROOT, "simulation")
os.makedirs(SIM_DIR, exist_ok=True)

RANDOM_SEED = 42
rng = np.random.default_rng(RANDOM_SEED)

# Same fixed "today" used across Week 2 so all simulated dates line up. The
# Olist window ends 2018-10-17; we centre disruptions around just after it.
SIM_REFERENCE_DATE = pd.Timestamp("2018-11-01")

# How many disruption events to generate. A few dozen is enough to create
# interesting scenarios without overwhelming the (later) planner.
NUM_DISRUPTIONS = 80

DISRUPTION_TYPES = [
    "heavy_traffic",
    "severe_weather",
    "warehouse_overload",
    "inventory_shortage",
    "road_closure",
]

SEVERITIES = ["low", "medium", "high", "critical"]
SEVERITY_WEIGHTS = [0.35, 0.35, 0.22, 0.08]   # most events are minor; few critical

STATUSES = ["active", "resolved", "scheduled"]
STATUS_WEIGHTS = [0.45, 0.40, 0.15]

# How long (in minutes) each severity typically delays a delivery. These ranges
# are documented assumptions - bigger severity, bigger delay.
SEVERITY_DELAY_RANGE = {
    "low":      (10, 45),
    "medium":   (45, 120),
    "high":     (120, 300),
    "critical": (300, 720),
}

# A short, human-readable sentence per type (filled in with the location).
IMPACT_TEMPLATES = {
    "heavy_traffic":      "Heavy traffic congestion around {city}, {state} slowing deliveries.",
    "severe_weather":     "Severe weather near {city}, {state} delaying or halting routes.",
    "warehouse_overload": "Warehouse {wh} in {city}, {state} overloaded and backed up.",
    "inventory_shortage": "Inventory shortage at warehouse {wh} in {city}, {state}.",
    "road_closure":       "Road closure near {city}, {state} blocking delivery routes.",
}


def banner(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def step(msg):
    print(f"  - {msg}")


def load_sim(file_name):
    return pd.read_csv(os.path.join(SIM_DIR, file_name))


def main():
    banner("WEEK 2 - DISRUPTION GENERATION")
    print("Reading simulated warehouses; inventing realistic disruption events.")
    print(f"Writing simulated disruptions to: {SIM_DIR}")

    warehouses = load_sim("warehouses.csv")
    step(f"Loaded {len(warehouses):,} warehouses to anchor disruptions to.")

    rows = []
    for i in range(NUM_DISRUPTIONS):
        dtype = rng.choice(DISRUPTION_TYPES)
        severity = rng.choice(SEVERITIES, p=SEVERITY_WEIGHTS)
        status = rng.choice(STATUSES, p=STATUS_WEIGHTS)

        # Pick a real warehouse to anchor the event's location. Warehouse-
        # specific disruptions (overload / shortage) name that warehouse;
        # the others are area-wide but still placed in a real city/state.
        wh = warehouses.iloc[rng.integers(0, len(warehouses))]
        city, state = wh["warehouse_city"], wh["warehouse_state"]

        # warehouse_overload and inventory_shortage are tied to a specific
        # warehouse. Traffic / weather / road events affect an area, so we
        # leave affected_warehouse_id blank for those.
        if dtype in ("warehouse_overload", "inventory_shortage"):
            affected_wh = wh["warehouse_id"]
        else:
            affected_wh = ""

        # --- timing -----------------------------------------------------
        # Start time: somewhere in a +/- 30 day window around our fixed "today"
        # (scheduled events lean future, resolved events lean past - handled by
        # the offset sign below). Duration depends loosely on severity.
        day_offset = int(rng.integers(-30, 31))
        minute_offset = int(rng.integers(0, 24 * 60))
        start_time = SIM_REFERENCE_DATE + pd.Timedelta(days=day_offset, minutes=minute_offset)

        low, high = SEVERITY_DELAY_RANGE[severity]
        estimated_delay = int(rng.integers(low, high + 1))

        # The event lasts roughly as long as its delay impact, plus slack.
        duration_min = int(estimated_delay * rng.uniform(1.0, 2.5))
        end_time = start_time + pd.Timedelta(minutes=duration_min)

        impact = IMPACT_TEMPLATES[dtype].format(
            city=city, state=state, wh=wh["warehouse_id"]
        )

        rows.append({
            "disruption_id": f"DIS-{i+1:04d}",            # SIMULATED key
            "disruption_type": dtype,                     # SIMULATED
            "severity": severity,                         # SIMULATED
            "location_city": city,                        # REAL place name
            "location_state": state,                      # REAL place name
            "affected_warehouse_id": affected_wh,         # REAL link (when relevant)
            "start_time": start_time,                     # SIMULATED
            "end_time": end_time,                         # SIMULATED
            "impact_description": impact,                 # SIMULATED
            "estimated_delay_minutes": estimated_delay,   # SIMULATED
            "status": status,                             # SIMULATED
        })

    disruptions = pd.DataFrame(rows)

    out_path = os.path.join(SIM_DIR, "disruptions.csv")
    disruptions.to_csv(out_path, index=False)
    step(f"Saved -> simulation/disruptions.csv  ({len(disruptions):,} rows)")
    step(f"By type: {disruptions['disruption_type'].value_counts().to_dict()}")
    step(f"By severity: {disruptions['severity'].value_counts().to_dict()}")
    step(f"By status: {disruptions['status'].value_counts().to_dict()}")

    banner("DONE - disruptions generated")
    print("  Each row = one simulated real-world problem affecting deliveries.")
    print("  Next: notebooks/week2_route_generation.py")
    print("  Reminder: data/ and processed/ were NOT modified.")


if __name__ == "__main__":
    main()
