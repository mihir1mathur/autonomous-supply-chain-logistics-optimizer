"""
============================================================================
WEEK 2 - WAREHOUSE GENERATION SCRIPT
Project: Supply Chain & Logistics Optimizer
Dataset: Brazilian E-Commerce Public Dataset by Olist
============================================================================

WHERE WE ARE (continuity from Week 0 and Week 1)
------------------------------------------------
  Week 0 = understood the business + profiled the 9 raw CSV files.
  Week 1 = CLEANED those files into processed/ and JOINED them into one
           order-item master table, and wrote the logistics DATA MODEL
           (docs/logistics_data_model.md). That model made one key decision:

               an Olist SELLER is treated as a WAREHOUSE / fulfillment origin.

WHY WE ARE HERE NOW (Week 2)
----------------------------
  Olist records online SALES. It does NOT contain a logistics operation:
  there are no warehouses, no stock levels, no trucks, no live traffic.
  To build (later) an optimization + planning system, we need those things.

  So Week 2 SIMULATES a realistic logistics layer ON TOP of the real,
  cleaned Week 1 data. This first script builds the WAREHOUSES - the places
  shipments start from.

WHAT IS REAL vs WHAT IS SIMULATED HERE
--------------------------------------
  REAL (from Olist, via processed/):
    - which sellers exist
    - their city / state / zip prefix
    - their map coordinates (from the zip -> lat/lng lookup)
    - how many items each seller actually shipped (their real volume)
  SIMULATED (invented by this script, clearly flagged):
    - capacity            (Olist has no warehouse size)
    - current_utilization (Olist has no "how full is it" number)
    - operating_status    (active / overloaded / inactive)

OUTPUT
------
    simulation/warehouses.csv   (one row per warehouse)

GOLDEN RULE (unchanged from Week 1)
-----------------------------------
  We only READ from data/ and processed/.  We only WRITE to simulation/.
  The original raw CSV files in data/ are NEVER modified.

HOW TO RUN
----------
    pip install pandas numpy
    python notebooks/week2_generate_warehouses.py

  Run this FIRST. The other Week 2 scripts read simulation/warehouses.csv.
============================================================================
"""

import os
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# STEP 0: Folder paths and reproducibility.
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))   # .../notebooks
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)                # project root
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "processed")   # cleaned inputs
SIM_DIR = os.path.join(PROJECT_ROOT, "simulation")        # simulated outputs

os.makedirs(SIM_DIR, exist_ok=True)

# A FIXED random seed means "random" values come out the SAME every run.
# Reproducibility matters: anyone re-running gets the identical dataset.
RANDOM_SEED = 42
rng = np.random.default_rng(RANDOM_SEED)

# How many sellers to promote to "warehouses".
# WHY a subset: Olist has 3,095 sellers, but real fulfillment networks have a
# handful of busy hubs, not thousands. We keep the TOP sellers by real shipped
# volume - the top ~150 already account for roughly half of all items shipped,
# so they form a realistic, manageable "main network". (Documented assumption.)
TOP_N_WAREHOUSES = 150


# ---------------------------------------------------------------------------
# Small helper functions (same reporting style as the Week 1 scripts).
# ---------------------------------------------------------------------------
def banner(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def step(msg):
    print(f"  - {msg}")


def load_processed(file_name):
    """Read one CLEANED CSV from processed/ (produced in Week 1)."""
    return pd.read_csv(os.path.join(PROCESSED_DIR, file_name))


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    banner("WEEK 2 - WAREHOUSE GENERATION")
    print("Reading cleaned data from processed/ (never modified).")
    print(f"Writing simulated warehouses to: {SIM_DIR}")

    # -------------------------------------------------------------------
    # 1) Load the real, cleaned inputs.
    # -------------------------------------------------------------------
    sellers = load_processed("sellers_clean.csv")
    order_items = load_processed("order_items_clean.csv")
    zip_lookup = load_processed("geolocation_zip_lookup.csv")
    step(f"Loaded {len(sellers):,} sellers, {len(order_items):,} order items.")

    # -------------------------------------------------------------------
    # 2) Measure each seller's REAL shipped volume.
    #    A warehouse that shipped more items is a busier, bigger hub - we
    #    will size its (simulated) capacity from this real number.
    # -------------------------------------------------------------------
    volume = (
        order_items.groupby("seller_id")
        .size()
        .reset_index(name="items_shipped")
    )
    step(f"Computed real shipped volume for {len(volume):,} sellers.")

    # -------------------------------------------------------------------
    # 3) Attach coordinates (REAL) via the zip -> lat/lng lookup from Week 1.
    #    Routing later needs a point on the map for each warehouse.
    # -------------------------------------------------------------------
    sellers = sellers.merge(
        zip_lookup,
        left_on="seller_zip_code_prefix",
        right_on="geolocation_zip_code_prefix",
        how="left",
    )
    missing_coord = sellers["geolocation_lat"].isna().sum()
    step(f"Joined coordinates; {missing_coord} sellers had no matching zip point.")

    # Combine volume + coordinates onto each seller.
    sellers = sellers.merge(volume, on="seller_id", how="left")
    sellers["items_shipped"] = sellers["items_shipped"].fillna(0).astype(int)

    # -------------------------------------------------------------------
    # 4) Pick the warehouse SUBSET: top sellers by real volume that also
    #    have valid coordinates (a warehouse with no location is useless
    #    for routing).
    # -------------------------------------------------------------------
    eligible = sellers[sellers["geolocation_lat"].notna()].copy()
    eligible = eligible.sort_values("items_shipped", ascending=False)
    chosen = eligible.head(TOP_N_WAREHOUSES).reset_index(drop=True)
    covered = chosen["items_shipped"].sum() / len(order_items) * 100
    step(
        f"Selected top {len(chosen)} sellers as warehouses "
        f"(they cover {covered:.1f}% of all shipped items)."
    )

    # -------------------------------------------------------------------
    # 5) SIMULATE the warehouse operational fields.
    #    Everything below is INVENTED (Olist has none of it) but tied to the
    #    real volume so the numbers stay believable.
    # -------------------------------------------------------------------

    # 5a) capacity = how many package-slots the warehouse can hold.
    #     Bigger shippers get bigger buildings. We give each warehouse enough
    #     room for its volume PLUS headroom (a real warehouse is rarely 100%
    #     full), then round to a tidy number. Floor of 500 so even small hubs
    #     are plausible buildings, cap kept generous for the biggest hubs.
    base = chosen["items_shipped"].to_numpy()
    headroom = rng.uniform(1.4, 2.2, size=len(chosen))   # 40%-120% spare room
    capacity = np.clip(np.round((base * headroom) / 100) * 100, 500, None)
    chosen["capacity"] = capacity.astype(int)

    # 5b) current_utilization = fraction of capacity currently in use (0-1).
    #     Drawn from a realistic spread centred around ~65% full. Clipped to
    #     a sane 25%-99% band (a working warehouse is neither empty nor literally
    #     overflowing). Rounded to 2 decimals for readability.
    utilization = rng.normal(loc=0.65, scale=0.15, size=len(chosen))
    utilization = np.clip(utilization, 0.25, 0.99)
    chosen["current_utilization"] = np.round(utilization, 2)

    # 5c) operating_status describes the warehouse's health RIGHT NOW:
    #       overloaded -> nearly full (utilization >= 0.90): a stockout/backlog risk
    #       inactive   -> temporarily closed (maintenance / offline): a small random set
    #       active     -> normal operation (the common case)
    #     We assign 'inactive' to a small random ~5% of warehouses, then mark
    #     the very-full ones as 'overloaded', and everything else 'active'.
    status = np.full(len(chosen), "active", dtype=object)
    inactive_mask = rng.random(len(chosen)) < 0.05
    status[inactive_mask] = "inactive"
    overloaded_mask = (chosen["current_utilization"] >= 0.90) & (~inactive_mask)
    status[overloaded_mask.to_numpy()] = "overloaded"
    chosen["operating_status"] = status
    step(
        "Simulated capacity, current_utilization, operating_status "
        f"({(status=='active').sum()} active, "
        f"{(status=='overloaded').sum()} overloaded, "
        f"{(status=='inactive').sum()} inactive)."
    )

    # -------------------------------------------------------------------
    # 6) Build a clean warehouse_id and assemble the final columns.
    #    warehouse_id (WH-0001 ...) is a stable, human-readable key the other
    #    Week 2 files (inventory, vehicles, routes) will reference.
    # -------------------------------------------------------------------
    chosen["warehouse_id"] = [f"WH-{i+1:04d}" for i in range(len(chosen))]

    warehouses = pd.DataFrame({
        "warehouse_id": chosen["warehouse_id"],                       # SIMULATED key
        "seller_id": chosen["seller_id"],                             # REAL (Olist)
        "warehouse_city": chosen["seller_city"],                      # REAL
        "warehouse_state": chosen["seller_state"],                    # REAL
        "warehouse_zip_code_prefix": chosen["seller_zip_code_prefix"],  # REAL
        "latitude": np.round(chosen["geolocation_lat"], 6),           # REAL
        "longitude": np.round(chosen["geolocation_lng"], 6),          # REAL
        "capacity": chosen["capacity"],                               # SIMULATED
        "current_utilization": chosen["current_utilization"],         # SIMULATED
        "operating_status": chosen["operating_status"],               # SIMULATED
    })

    out_path = os.path.join(SIM_DIR, "warehouses.csv")
    warehouses.to_csv(out_path, index=False)
    step(f"Saved -> simulation/warehouses.csv  ({len(warehouses):,} rows)")

    banner("DONE - warehouses generated")
    print("  Next: notebooks/week2_inventory_simulation.py  (stock per warehouse)")
    print("        notebooks/week2_vehicle_generation.py    (fleet per warehouse)")
    print("  Reminder: data/ and processed/ were NOT modified.")


if __name__ == "__main__":
    main()
