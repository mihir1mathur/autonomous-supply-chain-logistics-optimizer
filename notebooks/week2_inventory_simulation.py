"""
============================================================================
WEEK 2 - INVENTORY SIMULATION SCRIPT
Project: Supply Chain & Logistics Optimizer
Dataset: Brazilian E-Commerce Public Dataset by Olist
============================================================================

WHAT IS INVENTORY? (first principles)
-------------------------------------
  INVENTORY = the actual STOCK a warehouse is holding right now: how many
  units of each product are sitting on the shelves, ready to ship.

  Tiny story: a customer orders a phone charger. For that order to ship today,
  some warehouse must already HAVE a charger in stock. If it has zero, the
  order is delayed (a "stockout"). Inventory is the count that tells us that.

WHY MUST WE SIMULATE IT?
------------------------
  The Olist dataset records SALES (what was bought), not WAREHOUSE STATE
  (what was on the shelf). There is no stock column anywhere. So to reason
  about stockouts, restocking, and fulfillment later, we must INVENT realistic
  stock numbers. That is what this script does.

HOW INVENTORY CONNECTS PRODUCTS TO WAREHOUSES
---------------------------------------------
  A product on its own is just a catalog entry. A warehouse on its own is just
  a building. INVENTORY is the link: "warehouse WH-0007 holds 240 units of
  product X." One row = one (warehouse, product) pairing with a quantity.

WHAT IS REAL vs WHAT IS SIMULATED HERE
--------------------------------------
  REAL (from Olist, via processed/):
    - which warehouse (seller) actually shipped which product
    - how many units of that product it shipped (its real demand signal)
    - the product's category
  SIMULATED (invented here, tied to the real demand so it stays believable):
    - stock_level        (units currently on hand)
    - reorder_threshold  (the "order more when we drop to here" line)
    - reorder_quantity   (how many we order when we restock)
    - last_restock_date  (when stock was last topped up)
    - inventory_status   (healthy / low_stock / out_of_stock)

OUTPUT
------
    simulation/inventory.csv

GOLDEN RULE: READ from processed/ + simulation/warehouses.csv;
             WRITE only to simulation/.  data/ is never touched.

HOW TO RUN
----------
    python notebooks/week2_generate_warehouses.py   # must run first
    python notebooks/week2_inventory_simulation.py
============================================================================
"""

import os
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# STEP 0: paths, seed, and a fixed "simulated present" date.
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "processed")
SIM_DIR = os.path.join(PROJECT_ROOT, "simulation")
os.makedirs(SIM_DIR, exist_ok=True)

RANDOM_SEED = 42
rng = np.random.default_rng(RANDOM_SEED)

# The Olist data ends on 2018-10-17. We anchor all simulated "current" dates to
# a fixed point just after that window, so the simulation has a consistent
# "today" and results are reproducible (we never use the real clock).
SIM_REFERENCE_DATE = pd.Timestamp("2018-11-01")


def banner(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def step(msg):
    print(f"  - {msg}")


def load_processed(file_name):
    return pd.read_csv(os.path.join(PROCESSED_DIR, file_name))


def load_sim(file_name):
    return pd.read_csv(os.path.join(SIM_DIR, file_name))


def main():
    banner("WEEK 2 - INVENTORY SIMULATION")
    print("Reading cleaned data + simulated warehouses.")
    print(f"Writing simulated inventory to: {SIM_DIR}")

    # -------------------------------------------------------------------
    # 1) Load inputs: the warehouses we built, plus the real order items
    #    (the demand signal) and products (categories).
    # -------------------------------------------------------------------
    warehouses = load_sim("warehouses.csv")
    order_items = load_processed("order_items_clean.csv")
    products = load_processed("products_clean.csv")
    step(
        f"Loaded {len(warehouses):,} warehouses, "
        f"{len(order_items):,} order items, {len(products):,} products."
    )

    # Only keep order items shipped by our chosen warehouses. We use the
    # seller_id -> warehouse_id mapping so inventory references warehouse_id.
    seller_to_wh = warehouses.set_index("seller_id")["warehouse_id"]
    items = order_items[order_items["seller_id"].isin(seller_to_wh.index)].copy()
    items["warehouse_id"] = items["seller_id"].map(seller_to_wh)
    step(f"Kept {len(items):,} order items belonging to our warehouses.")

    # -------------------------------------------------------------------
    # 2) REAL demand signal: for each (warehouse, product), how many units
    #    were actually shipped? A warehouse stocks the products it sells, and
    #    the best-selling products deserve the most stock.
    # -------------------------------------------------------------------
    demand = (
        items.groupby(["warehouse_id", "product_id"])
        .size()
        .reset_index(name="units_sold")
    )
    step(f"Built {len(demand):,} (warehouse, product) stock pairs from real sales.")

    # Attach the product category (REAL) so inventory rows are readable.
    cat = products[["product_id", "product_category_name"]]
    demand = demand.merge(cat, on="product_id", how="left")
    demand["product_category_name"] = demand["product_category_name"].fillna("unknown")

    # -------------------------------------------------------------------
    # 3) SIMULATE stock levels, tied to real demand.
    #    Logic (documented assumptions):
    #      * A warehouse keeps roughly a few "sales-worth" of stock on hand.
    #        We scale the on-hand target to units_sold with a random multiplier,
    #        so popular items carry deeper stock than slow movers.
    #      * reorder_threshold = the low-water mark (~30% of the target stock):
    #        when stock falls to here, it is time to reorder.
    #      * reorder_quantity  = how much we bring in per restock (~the target).
    # -------------------------------------------------------------------
    units_sold = demand["units_sold"].to_numpy()

    # Target "full shelf" level: scale demand up with a random factor, floor of
    # 10 units so even one-off products have a small plausible shelf.
    stock_multiplier = rng.uniform(2.0, 6.0, size=len(demand))
    target_stock = np.maximum(np.round(units_sold * stock_multiplier), 10).astype(int)

    # reorder threshold ~30% of target (each warehouse a little different).
    threshold_frac = rng.uniform(0.20, 0.40, size=len(demand))
    reorder_threshold = np.maximum(np.round(target_stock * threshold_frac), 5).astype(int)

    # reorder quantity ~ the target shelf (how much we pull in to refill).
    reorder_quantity = np.maximum(np.round(target_stock * rng.uniform(0.8, 1.2, size=len(demand))), 10).astype(int)

    # -------------------------------------------------------------------
    # 4) SIMULATE the CURRENT stock_level (where the shelf is right now).
    #    We draw current stock as a random fraction of the target so that some
    #    items are full, some are running low, and a few are out of stock - a
    #    realistic snapshot the later weeks can react to.
    # -------------------------------------------------------------------
    current_frac = rng.uniform(0.0, 1.1, size=len(demand))
    stock_level = np.round(target_stock * current_frac).astype(int)
    stock_level = np.clip(stock_level, 0, None)

    # -------------------------------------------------------------------
    # 5) DERIVE inventory_status from stock vs threshold (the rule the later
    #    stockout-detection logic will reuse):
    #       out_of_stock -> stock_level == 0
    #       low_stock    -> stock_level <= reorder_threshold (time to reorder)
    #       healthy      -> stock_level above the threshold
    # -------------------------------------------------------------------
    status = np.where(
        stock_level == 0, "out_of_stock",
        np.where(stock_level <= reorder_threshold, "low_stock", "healthy"),
    )

    # -------------------------------------------------------------------
    # 6) SIMULATE last_restock_date: a random number of days before our fixed
    #    "today". Items with more stock were generally restocked more recently.
    # -------------------------------------------------------------------
    days_ago = rng.integers(0, 90, size=len(demand))
    last_restock = SIM_REFERENCE_DATE - pd.to_timedelta(days_ago, unit="D")

    # -------------------------------------------------------------------
    # 7) Assemble the final table with a clean inventory_id key.
    # -------------------------------------------------------------------
    inventory = pd.DataFrame({
        "inventory_id": [f"INV-{i+1:06d}" for i in range(len(demand))],  # SIMULATED key
        "warehouse_id": demand["warehouse_id"],                          # REAL link
        "product_id": demand["product_id"],                              # REAL (Olist)
        "product_category_name": demand["product_category_name"],        # REAL
        "stock_level": stock_level,                                      # SIMULATED
        "reorder_threshold": reorder_threshold,                          # SIMULATED
        "reorder_quantity": reorder_quantity,                            # SIMULATED
        "last_restock_date": last_restock.date.astype(str),              # SIMULATED
        "inventory_status": status,                                      # SIMULATED (derived)
    })

    out_path = os.path.join(SIM_DIR, "inventory.csv")
    inventory.to_csv(out_path, index=False)
    step(f"Saved -> simulation/inventory.csv  ({len(inventory):,} rows)")
    step(
        "Status mix: "
        f"{(status=='healthy').sum()} healthy, "
        f"{(status=='low_stock').sum()} low_stock, "
        f"{(status=='out_of_stock').sum()} out_of_stock."
    )

    banner("DONE - inventory generated")
    print("  Each row = one product stocked at one warehouse, with a quantity.")
    print("  Next: notebooks/week2_vehicle_generation.py")
    print("  Reminder: data/ and processed/ were NOT modified.")


if __name__ == "__main__":
    main()
