"""
============================================================================
WEEK 1 - DATASET JOINS SCRIPT
Project: Supply Chain & Logistics Optimizer
Dataset: Brazilian E-Commerce Public Dataset by Olist
============================================================================

WHERE WE ARE (continuity)
-------------------------
- Week 0 (note 07) taught the THEORY of joins: tables, rows, primary keys,
  foreign keys, and how the 9 files link together.
- Week 1 (week1_data_cleaning.py) produced cleaned files in processed/.
- THIS script puts the theory into practice: it actually JOINS the cleaned
  files into ONE big "order-level" table - the foundation every later week
  will analyze and optimize.

WHAT IS A JOIN? (quick reminder)
--------------------------------
A join snaps two tables together by matching a key column. Example:
orders has a customer_id; customers also has customer_id. Matching them
lets us see the customer's city right next to each order. (Week 0, note 07.)

THE JOURNEY WE BUILD (one order across the whole dataset):
    Orders
      -> Customers      (who ordered + WHERE it must go = destination)
      -> Order Items    (WHAT products are in the order)
      -> Products       (details of each item: category, weight)
      -> Sellers        (who ships it + WHERE from = origin / warehouse)
      -> Geolocation    (map coordinates for origin AND destination)

WHY READ FROM processed/?
-------------------------
We join the CLEANED files so the result is trustworthy. If processed/ is
missing, run week1_data_cleaning.py first.

HOW TO RUN
----------
    python notebooks/week1_data_cleaning.py     (first, once)
    python notebooks/week1_dataset_joins.py
============================================================================
"""

import os
import sys
import pandas as pd


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "processed")


def banner(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def load_clean(file_name):
    """Read a cleaned CSV from processed/. Stop with a friendly message if missing."""
    path = os.path.join(PROCESSED_DIR, file_name)
    if not os.path.exists(path):
        print(f"\n!! Missing {path}")
        print("   Please run: python notebooks/week1_data_cleaning.py  first.")
        sys.exit(1)
    return pd.read_csv(path)


def show(df, label):
    """Print the shape (rows x columns) of a table after a join step."""
    rows, cols = df.shape
    print(f"    -> {label}: {rows:,} rows x {cols} columns")


def main():
    banner("WEEK 1 DATASET JOINS - building one order-level table")
    print("Reading cleaned files from processed/ and joining them step by step.")

    # -----------------------------------------------------------------------
    # Load the cleaned tables we need.
    # -----------------------------------------------------------------------
    orders = load_clean("orders_clean.csv")
    customers = load_clean("customers_clean.csv")
    order_items = load_clean("order_items_clean.csv")
    products = load_clean("products_clean.csv")
    sellers = load_clean("sellers_clean.csv")
    geo = load_clean("geolocation_zip_lookup.csv")   # one point per zip prefix
    show(orders, "orders (starting point)")

    # =======================================================================
    # JOIN 1: ORDERS  +  CUSTOMERS   (key: customer_id)
    # =======================================================================
    banner("JOIN 1: Orders -> Customers   (key = customer_id)")
    print("  WHY: an order only stores a customer_id. To know WHERE the order")
    print("       must be delivered, we attach the customer's city/state/zip.")
    print("  NEW INFO UNLOCKED: the delivery DESTINATION of every order.")
    df = orders.merge(customers, on="customer_id", how="left")
    show(df, "orders + customers")

    # =======================================================================
    # JOIN 2: + ORDER ITEMS   (key: order_id)
    # =======================================================================
    banner("JOIN 2: + Order Items   (key = order_id)")
    print("  WHY: one order can contain several products. Order items lists")
    print("       each product line, with its price, freight, and seller.")
    print("  NEW INFO: WHAT was bought + shipping cost. NOTE the row count")
    print("       GROWS - a 3-item order becomes 3 rows (item-level detail).")
    df = df.merge(order_items, on="order_id", how="left")
    show(df, "orders + customers + order_items")

    # =======================================================================
    # JOIN 3: + PRODUCTS   (key: product_id)
    # =======================================================================
    banner("JOIN 3: + Products   (key = product_id)")
    print("  WHY: order items only store a product_id. We attach product")
    print("       details: category (English) and weight/size for logistics.")
    print("  NEW INFO: the INVENTORY ITEM characteristics (weight, category).")
    product_cols = [
        "product_id", "product_category_name",
        "product_category_name_english", "product_weight_g",
        "product_length_cm", "product_height_cm", "product_width_cm",
    ]
    df = df.merge(products[product_cols], on="product_id", how="left")
    show(df, "+ products")

    # =======================================================================
    # JOIN 4: + SELLERS   (key: seller_id)
    # =======================================================================
    banner("JOIN 4: + Sellers   (key = seller_id)")
    print("  WHY: each item ships from a seller. In our logistics model the")
    print("       seller is the ORIGIN / warehouse. We attach its location.")
    print("  NEW INFO: the shipment ORIGIN (seller city/state/zip).")
    df = df.merge(sellers, on="seller_id", how="left")
    show(df, "+ sellers")

    # =======================================================================
    # JOIN 5: + GEOLOCATION  (twice: once for customer, once for seller)
    # =======================================================================
    banner("JOIN 5: + Geolocation   (key = zip code prefix, used TWICE)")
    print("  WHY: city names can't measure distance - we need coordinates.")
    print("       We look up lat/lng for BOTH the customer zip (destination)")
    print("       and the seller zip (origin).")
    print("  NEW INFO: map points for origin AND destination -> enables")
    print("       distance + routing in Week 3.")

    # Customer side: rename the lookup columns so we know they're the customer's.
    cust_geo = geo.rename(
        columns={
            "geolocation_zip_code_prefix": "customer_zip_code_prefix",
            "geolocation_lat": "customer_lat",
            "geolocation_lng": "customer_lng",
        }
    )
    df = df.merge(cust_geo, on="customer_zip_code_prefix", how="left")
    show(df, "+ customer coordinates")

    # Seller side: same lookup, renamed for the seller.
    sell_geo = geo.rename(
        columns={
            "geolocation_zip_code_prefix": "seller_zip_code_prefix",
            "geolocation_lat": "seller_lat",
            "geolocation_lng": "seller_lng",
        }
    )
    df = df.merge(sell_geo, on="seller_zip_code_prefix", how="left")
    show(df, "+ seller coordinates (FINAL order-level table)")

    # =======================================================================
    # RESULT: save the combined order-level table.
    # =======================================================================
    banner("RESULT: one combined order-level table")
    missing_cust_coord = df["customer_lat"].isna().sum()
    missing_sell_coord = df["seller_lat"].isna().sum()
    print(f"  Rows missing customer coordinates: {missing_cust_coord:,}")
    print(f"  Rows missing seller coordinates:   {missing_sell_coord:,}")
    print("  (Some zip prefixes have no geolocation match - normal; later")
    print("   weeks can fall back to city/state averages.)")

    out_path = os.path.join(PROCESSED_DIR, "orders_master_table.csv")
    df.to_csv(out_path, index=False)
    print(f"\n  Saved -> processed/orders_master_table.csv ({len(df):,} rows)")

    banner("DONE - the dataset is now ONE connected logistics table")
    print("  Each row = one item in one order, with its origin, destination,")
    print("  product details, costs, and delivery dates - all in one place.")
    print("  This master table is the foundation for Weeks 2-8.")


if __name__ == "__main__":
    main()
