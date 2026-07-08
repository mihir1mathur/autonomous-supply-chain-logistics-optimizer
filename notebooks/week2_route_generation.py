"""
============================================================================
WEEK 2 - DELIVERY ROUTE GENERATION SCRIPT
Project: Supply Chain & Logistics Optimizer
Dataset: Brazilian E-Commerce Public Dataset by Olist
============================================================================

WHAT IS A DELIVERY ROUTE?
-------------------------
  A ROUTE is the journey a package takes from where it starts (a WAREHOUSE)
  to where it must go (a CUSTOMER).

        WAREHOUSE  --------------------->  CUSTOMER
        (origin)        the route         (destination)

  For each shipment we want to know: how far is it, how long will it take, and
  roughly what will it cost? Those three numbers are what later optimization
  (Week 3, OR-Tools) will try to MINIMIZE.

HOW WE USE GEOLOCATION DATA
---------------------------
  In Week 1 we turned every zip-code prefix into a single (latitude, longitude)
  point. A warehouse and a customer each sit at such a point. The distance
  between two points on Earth is computed with the HAVERSINE formula (great-
  circle / "as the crow flies" distance). That is an APPROXIMATION of the real
  road distance - good enough for a first estimate, and we improve it later.

WHY THIS IS A SIMPLE ESTIMATE (NOT OPTIMIZATION YET)
----------------------------------------------------
  This script does NOT optimize anything. It does not pick the best vehicle,
  combine stops, or avoid disruptions. It just produces one straightforward
  estimated route per shipment leg. The real optimization (OR-Tools) arrives
  in a later week; this dataset is the input it will improve upon.

WHAT IS REAL vs WHAT IS SIMULATED HERE
--------------------------------------
  REAL (from Olist, via processed/ + simulation/warehouses.csv):
    - order_id, customer_id, the warehouse (seller) fulfilling each leg
    - source & destination cities/states and their coordinates
    - the order's status (used to set a believable route_status)
  COMPUTED / SIMULATED here:
    - estimated_distance_km  (haversine - computed from real coordinates)
    - estimated_time_minutes (distance / a representative average speed)
    - estimated_cost         (distance x a representative freight rate)
    - route_status           (derived from the real order status)

OUTPUT
------
    simulation/delivery_routes.csv

GOLDEN RULE: READ processed/ + simulation/warehouses.csv; WRITE only simulation/.

HOW TO RUN
----------
    python notebooks/week2_generate_warehouses.py   # must run first
    python notebooks/week2_route_generation.py
============================================================================
"""

import os
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# STEP 0: paths, seed, and tunable assumptions.
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "processed")
SIM_DIR = os.path.join(PROJECT_ROOT, "simulation")
os.makedirs(SIM_DIR, exist_ok=True)

RANDOM_SEED = 42
rng = np.random.default_rng(RANDOM_SEED)

# Representative numbers used to turn distance into a time and a cost. These are
# documented assumptions; the optimizer will replace them with per-vehicle
# values later (vehicles already carry their own speed/cost in vehicles.csv).
AVG_SPEED_KMPH = 50.0          # a blended road speed for estimation
FREIGHT_RATE_PER_KM = 1.20     # generic cost units per km
# Straight-line distance understates real road distance. A "winding factor"
# nudges the haversine distance up toward a plausible road distance.
ROAD_WINDING_FACTOR = 1.30

# Routes are generated per (order, warehouse) shipment leg. There are ~50k such
# legs for our warehouses; we keep a reproducible SAMPLE to keep the file light
# and GitHub-friendly. Set to None to generate every leg.
MAX_ROUTES = 10000


def banner(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def step(msg):
    print(f"  - {msg}")


def haversine_km(lat1, lon1, lat2, lon2):
    """
    Great-circle distance between two lat/lng points, in kilometres.
    This is the standard "distance over the curved Earth" formula. It works on
    whole numpy arrays at once, so we can distance ALL routes in one shot.
    """
    R = 6371.0  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def route_status_from_order(order_status):
    """
    Turn the REAL order status into a believable route_status:
      delivered                       -> completed
      shipped                         -> in_transit
      anything else (processing, etc) -> planned
    This keeps the simulated route grounded in the real order outcome.
    """
    if order_status == "delivered":
        return "completed"
    if order_status == "shipped":
        return "in_transit"
    return "planned"


def main():
    banner("WEEK 2 - DELIVERY ROUTE GENERATION")
    print("Building estimated warehouse -> customer routes from real coordinates.")
    print(f"Writing simulated routes to: {SIM_DIR}")

    # -------------------------------------------------------------------
    # 1) Load the master table (real, order-item grain, with coordinates) and
    #    the warehouses we chose.
    # -------------------------------------------------------------------
    master = pd.read_csv(os.path.join(PROCESSED_DIR, "orders_master_table.csv"))
    warehouses = pd.read_csv(os.path.join(SIM_DIR, "warehouses.csv"))
    step(f"Loaded {len(master):,} master rows, {len(warehouses):,} warehouses.")

    # Map seller_id -> warehouse_id, and keep only legs our warehouses fulfill.
    seller_to_wh = warehouses.set_index("seller_id")["warehouse_id"]
    df = master[master["seller_id"].isin(seller_to_wh.index)].copy()
    df["warehouse_id"] = df["seller_id"].map(seller_to_wh)

    # -------------------------------------------------------------------
    # 2) Collapse to one row per SHIPMENT LEG = (order_id, warehouse_id).
    #    If an order has three items from the same seller, that is still ONE
    #    delivery journey, so we de-duplicate to avoid counting it three times.
    # -------------------------------------------------------------------
    leg_cols = [
        "order_id", "warehouse_id", "customer_id", "order_status",
        "seller_city", "seller_state", "customer_city", "customer_state",
        "seller_lat", "seller_lng", "customer_lat", "customer_lng",
    ]
    legs = df[leg_cols].drop_duplicates(subset=["order_id", "warehouse_id"]).copy()
    step(f"Reduced to {len(legs):,} unique (order, warehouse) shipment legs.")

    # A route needs BOTH endpoints on the map. Drop legs missing any coordinate
    # (a small number of customers had no zip match in Week 1).
    coord_cols = ["seller_lat", "seller_lng", "customer_lat", "customer_lng"]
    before = len(legs)
    legs = legs.dropna(subset=coord_cols)
    step(f"Dropped {before - len(legs):,} legs missing coordinates.")

    # -------------------------------------------------------------------
    # 3) Keep a reproducible sample so the output file stays light.
    # -------------------------------------------------------------------
    if MAX_ROUTES is not None and len(legs) > MAX_ROUTES:
        legs = legs.sample(n=MAX_ROUTES, random_state=RANDOM_SEED).reset_index(drop=True)
        step(f"Sampled {len(legs):,} legs (cap = {MAX_ROUTES:,}, seed = {RANDOM_SEED}).")
    else:
        legs = legs.reset_index(drop=True)

    # -------------------------------------------------------------------
    # 4) COMPUTE distance, time, and cost for every route at once.
    # -------------------------------------------------------------------
    straight_km = haversine_km(
        legs["seller_lat"].to_numpy(), legs["seller_lng"].to_numpy(),
        legs["customer_lat"].to_numpy(), legs["customer_lng"].to_numpy(),
    )
    # Apply the winding factor so the estimate leans toward real road distance.
    distance_km = np.round(straight_km * ROAD_WINDING_FACTOR, 2)

    # time = distance / speed, converted from hours to minutes.
    time_min = np.round(distance_km / AVG_SPEED_KMPH * 60, 1)

    # cost = distance x freight rate (a simple linear estimate).
    cost = np.round(distance_km * FREIGHT_RATE_PER_KM, 2)

    # -------------------------------------------------------------------
    # 5) Assemble the final routes table.
    # -------------------------------------------------------------------
    routes = pd.DataFrame({
        "route_id": [f"RT-{i+1:06d}" for i in range(len(legs))],   # SIMULATED key
        "order_id": legs["order_id"],                               # REAL
        "warehouse_id": legs["warehouse_id"],                       # REAL link
        "customer_id": legs["customer_id"],                         # REAL
        "source_city": legs["seller_city"],                         # REAL
        "source_state": legs["seller_state"],                       # REAL
        "destination_city": legs["customer_city"],                  # REAL
        "destination_state": legs["customer_state"],                # REAL
        "source_latitude": np.round(legs["seller_lat"], 6),         # REAL
        "source_longitude": np.round(legs["seller_lng"], 6),        # REAL
        "destination_latitude": np.round(legs["customer_lat"], 6),  # REAL
        "destination_longitude": np.round(legs["customer_lng"], 6), # REAL
        "estimated_distance_km": distance_km,                       # COMPUTED (haversine)
        "estimated_time_minutes": time_min,                         # COMPUTED
        "estimated_cost": cost,                                     # COMPUTED
        "route_status": legs["order_status"].apply(route_status_from_order),  # derived from REAL
    })

    out_path = os.path.join(SIM_DIR, "delivery_routes.csv")
    routes.to_csv(out_path, index=False)
    step(f"Saved -> simulation/delivery_routes.csv  ({len(routes):,} rows)")
    step(
        f"Distance km - min {routes['estimated_distance_km'].min():.0f}, "
        f"median {routes['estimated_distance_km'].median():.0f}, "
        f"max {routes['estimated_distance_km'].max():.0f}."
    )
    step(f"Route status mix: {routes['route_status'].value_counts().to_dict()}")

    banner("DONE - delivery routes generated")
    print("  Each row = one estimated warehouse -> customer journey.")
    print("  This is the SIMPLE estimate; OR-Tools optimization comes later.")
    print("  Reminder: data/ and processed/ were NOT modified.")


if __name__ == "__main__":
    main()
