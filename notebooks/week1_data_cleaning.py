"""
============================================================================
WEEK 1 - DATA CLEANING SCRIPT
Project: Supply Chain & Logistics Optimizer
Dataset: Brazilian E-Commerce Public Dataset by Olist
============================================================================

WHERE WE ARE (continuity from Week 0)
-------------------------------------
In Week 0 we OPENED every box (notebooks/week0_dataset_analysis.py) and
described what was inside each of the 9 CSV files - their shape, columns,
missing values, and duplicates. We did NOT change anything.

WHY WE ARE HERE NOW (Week 1)
----------------------------
Raw data is almost never ready to use. Before we can join the files,
analyze delays, or (in later weeks) optimize routes, we must CLEAN the data:
fix obvious problems so later steps don't silently break.

This script:
  1. Loads every raw CSV from data/ (the originals are NEVER changed).
  2. Reports the data-quality problems we found in Week 0 + a few new ones.
  3. Produces CLEANED copies inside a new folder: processed/
  4. Explains, in plain English, every cleaning decision and WHY it matters.

GOLDEN RULE: we only WRITE to processed/. We only READ from data/.

HOW TO RUN
----------
    pip install pandas
    python notebooks/week1_data_cleaning.py

WHERE THIS LEADS (future weeks)
-------------------------------
  - Week 1 (next script): join these cleaned files together.
  - Week 2: simulate inventory on the cleaned products/sellers.
  - Week 3: use cleaned geolocation to compute distances and routes.
  - Week 4: load these cleaned tables into a real database (PostgreSQL).
============================================================================
"""

import os
import pandas as pd


# ---------------------------------------------------------------------------
# STEP 0: Folder paths. We READ from data/, we WRITE to processed/.
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))   # .../notebooks
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)                # project root
DATA_DIR = os.path.join(PROJECT_ROOT, "data")             # raw inputs
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "processed")   # cleaned outputs

# Create the processed/ folder if it does not exist yet.
# (exist_ok=True means "don't error if it's already there".)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Brazil's rough geographic bounding box. Any coordinate outside this box
# is almost certainly a data-entry error, because Olist is a Brazilian
# company. (lat = north/south, lng = east/west - see Week 0 note 06.)
BRAZIL_LAT_MIN, BRAZIL_LAT_MAX = -34.0, 6.0
BRAZIL_LNG_MIN, BRAZIL_LNG_MAX = -74.0, -34.0


# ---------------------------------------------------------------------------
# Small helper functions so the report reads nicely.
# ---------------------------------------------------------------------------
def banner(title):
    """Print a big, easy-to-find section header."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def step(msg):
    """Print one cleaning step in a consistent style."""
    print(f"  - {msg}")


def load_raw(file_name):
    """Read one raw CSV from data/ into a pandas DataFrame (a table)."""
    return pd.read_csv(os.path.join(DATA_DIR, file_name))


def save_clean(df, file_name):
    """Write a cleaned DataFrame to processed/ (index=False = no extra column)."""
    out_path = os.path.join(PROCESSED_DIR, file_name)
    df.to_csv(out_path, index=False)
    step(f"Saved cleaned file -> processed/{file_name}  ({len(df):,} rows)")


# ===========================================================================
# 1) CUSTOMERS
# ===========================================================================
def clean_customers():
    banner("1) CUSTOMERS  (the delivery DESTINATIONS)")
    df = load_raw("olist_customers_dataset.csv")
    print(f"  Loaded {len(df):,} rows.")

    # IMPORTANT CONCEPT (from Week 0 note 04 & 05):
    #   customer_id        = one code PER ORDER record.
    #   customer_unique_id = one code PER REAL PERSON.
    # So 'duplicate' customer_unique_id values are NOT errors - they are
    # repeat customers. We check both so we understand the difference.
    dup_rows = df.duplicated().sum()
    unique_people = df["customer_unique_id"].nunique()
    repeat_people = len(df) - unique_people
    step(f"Exact duplicate rows: {dup_rows} (expected 0).")
    step(f"Distinct real people (customer_unique_id): {unique_people:,}.")
    step(f"Repeat-customer records (same person, new order): {repeat_people:,}.")
    step("Decision: keep all rows. Repeats are real behaviour, not errors.")

    # Tidy the text: city names have inconsistent spacing/case. We lowercase
    # and strip spaces so 'Sao Paulo ' and 'sao paulo' are treated the same.
    df["customer_city"] = df["customer_city"].str.strip().str.lower()
    df["customer_state"] = df["customer_state"].str.strip().str.upper()
    step("Standardized customer_city (lowercase) and customer_state (uppercase).")

    save_clean(df, "customers_clean.csv")
    return df


# ===========================================================================
# 2) GEOLOCATION  (this is the messiest file - the biggest cleaning win)
# ===========================================================================
def clean_geolocation():
    banner("2) GEOLOCATION  (zip prefix -> map coordinates, for ROUTING)")
    df = load_raw("olist_geolocation_dataset.csv")
    print(f"  Loaded {len(df):,} rows.")

    # PROBLEM 1: huge number of EXACT duplicate rows (Week 0 found 261,831).
    # Duplicates waste space and slow down joins, so we drop exact copies.
    before = len(df)
    df = df.drop_duplicates()
    step(f"Dropped {before - len(df):,} exact duplicate rows.")

    # PROBLEM 2: invalid coordinates. Some lat/lng values fall outside Brazil
    # (typos / bad GPS). We keep only coordinates inside Brazil's bounding box.
    valid = (
        df["geolocation_lat"].between(BRAZIL_LAT_MIN, BRAZIL_LAT_MAX)
        & df["geolocation_lng"].between(BRAZIL_LNG_MIN, BRAZIL_LNG_MAX)
    )
    bad = (~valid).sum()
    df = df[valid]
    step(f"Removed {bad:,} rows with coordinates outside Brazil's bounds.")

    # Tidy text columns, same as customers.
    df["geolocation_city"] = df["geolocation_city"].str.strip().str.lower()
    df["geolocation_state"] = df["geolocation_state"].str.strip().str.upper()

    # Save the de-duplicated, valid-coordinate version.
    save_clean(df, "geolocation_clean.csv")

    # PROBLEM 3 (the key one for routing): one zip prefix still has MANY
    # coordinate rows. For distance/routing we want ONE representative point
    # per zip prefix. We take the MEDIAN lat/lng (median resists outliers
    # better than the average). This small lookup table is what later weeks
    # will actually use to place a seller or customer on the map.
    zip_lookup = (
        df.groupby("geolocation_zip_code_prefix")
        .agg(
            geolocation_lat=("geolocation_lat", "median"),
            geolocation_lng=("geolocation_lng", "median"),
        )
        .reset_index()
    )
    step(f"Built one-point-per-zip lookup: {len(zip_lookup):,} unique zip prefixes.")
    save_clean(zip_lookup, "geolocation_zip_lookup.csv")
    return df, zip_lookup


# ===========================================================================
# 3) ORDER ITEMS
# ===========================================================================
def clean_order_items():
    banner("3) ORDER ITEMS  (one row per product inside an order)")
    df = load_raw("olist_order_items_dataset.csv")
    print(f"  Loaded {len(df):,} rows.")

    # shipping_limit_date is stored as TEXT. We convert it to a real datetime
    # so later code can do date math (e.g. was the item shipped in time?).
    # errors='coerce' turns any unparseable value into NaT (missing date)
    # instead of crashing the whole script.
    df["shipping_limit_date"] = pd.to_datetime(
        df["shipping_limit_date"], errors="coerce"
    )
    bad_dates = df["shipping_limit_date"].isna().sum()
    step(f"Parsed shipping_limit_date to datetime ({bad_dates} unparseable).")

    # Sanity check: price and freight should never be negative.
    bad_price = (df["price"] < 0).sum()
    bad_freight = (df["freight_value"] < 0).sum()
    step(f"Negative prices: {bad_price}; negative freight: {bad_freight} (expect 0).")

    save_clean(df, "order_items_clean.csv")
    return df


# ===========================================================================
# 4) PAYMENTS
# ===========================================================================
def clean_payments():
    banner("4) PAYMENTS  (how each order was paid)")
    df = load_raw("olist_order_payments_dataset.csv")
    print(f"  Loaded {len(df):,} rows.")

    # This file was clean in Week 0. We just standardize the text category
    # and confirm there are no negative payment values.
    df["payment_type"] = df["payment_type"].str.strip().str.lower()
    bad_value = (df["payment_value"] < 0).sum()
    step(f"Standardized payment_type. Negative payment values: {bad_value} (expect 0).")

    save_clean(df, "payments_clean.csv")
    return df


# ===========================================================================
# 5) REVIEWS
# ===========================================================================
def clean_reviews():
    banner("5) REVIEWS  (customer satisfaction, 1-5 stars)")
    df = load_raw("olist_order_reviews_dataset.csv")
    print(f"  Loaded {len(df):,} rows.")

    # The comment columns are mostly EMPTY (Week 0: title 88.3%, message
    # 58.7% missing). That is NORMAL - most people rate but don't write text.
    # We do NOT delete these rows. We fill the empty text with "" so the
    # column is consistent (all text), while keeping the numeric score.
    df["review_comment_title"] = df["review_comment_title"].fillna("")
    df["review_comment_message"] = df["review_comment_message"].fillna("")
    step("Filled empty review comment title/message with '' (blank, not deleted).")

    # The two date columns are text -> convert to datetime for later analysis.
    for col in ["review_creation_date", "review_answer_timestamp"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    step("Parsed review_creation_date and review_answer_timestamp to datetime.")

    # review_score should be 1..5. Flag anything outside that range.
    out_of_range = (~df["review_score"].between(1, 5)).sum()
    step(f"Review scores outside 1-5: {out_of_range} (expect 0).")

    save_clean(df, "reviews_clean.csv")
    return df


# ===========================================================================
# 6) ORDERS  (the central table - the SHIPMENT REQUESTS)
# ===========================================================================
def clean_orders():
    banner("6) ORDERS  (the heart of the dataset: status + delivery dates)")
    df = load_raw("olist_orders_dataset.csv")
    print(f"  Loaded {len(df):,} rows.")

    # The five timestamp columns are all TEXT. Convert each to datetime.
    date_cols = [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    step("Parsed all 5 timestamp columns from text to datetime.")

    # MISSING dates are EXPECTED here: an order that was never delivered has
    # no delivery date. We do NOT drop these - whether an order was delivered
    # is itself useful information. We just report the counts (matches Week 0).
    for col in date_cols:
        miss = df[col].isna().sum()
        if miss:
            step(f"{col}: {miss:,} missing (usually = not delivered / not approved).")

    # LOGICAL CHECK (a new Week-1 idea): a delivery cannot happen BEFORE the
    # purchase. If delivered_customer_date < purchase_timestamp, the row is
    # logically impossible. We flag (count) these rather than silently trust.
    delivered = df["order_delivered_customer_date"]
    purchased = df["order_purchase_timestamp"]
    impossible = (delivered.notna() & (delivered < purchased)).sum()
    step(f"Logically impossible deliveries (delivered before purchase): {impossible}.")

    # Standardize the status text.
    df["order_status"] = df["order_status"].str.strip().str.lower()

    save_clean(df, "orders_clean.csv")
    return df


# ===========================================================================
# 7) PRODUCTS  (the INVENTORY ITEMS) + English category names
# ===========================================================================
def clean_products():
    banner("7) PRODUCTS  (inventory items: category, weight, size)")
    df = load_raw("olist_products_dataset.csv")
    print(f"  Loaded {len(df):,} rows.")

    # PROBLEM 1: two column names are MISSPELLED in the raw data:
    #   'product_name_lenght' and 'product_description_lenght' ("lenght").
    # We rename them to correct English so future code isn't confusing.
    df = df.rename(
        columns={
            "product_name_lenght": "product_name_length",
            "product_description_lenght": "product_description_length",
        }
    )
    step("Fixed misspelled columns: 'lenght' -> 'length'.")

    # PROBLEM 2: 610 products have no category (Week 0). A missing category
    # would break grouping later. We fill it with a clear label instead of
    # deleting the products (they still exist and were ordered).
    df["product_category_name"] = df["product_category_name"].fillna("unknown")
    step("Filled 610 missing product categories with 'unknown'.")

    # PROBLEM 3: 2 products miss weight/dimensions. Weight/size matter for
    # logistics (packing, freight). We report them; we keep the rows but note
    # the gap for later (a later week can estimate from the category average).
    dim_cols = ["product_weight_g", "product_length_cm",
                "product_height_cm", "product_width_cm"]
    miss_dims = df[dim_cols].isna().any(axis=1).sum()
    step(f"Products missing weight/dimensions: {miss_dims} (kept, flagged for later).")

    # ADD ENGLISH CATEGORY: join the small translation file so categories are
    # readable. This is a LEFT join (keep every product, add English name if
    # available). Categories with no translation become 'unknown' English too.
    trans = load_raw("product_category_name_translation.csv")
    df = df.merge(trans, on="product_category_name", how="left")
    df["product_category_name_english"] = (
        df["product_category_name_english"].fillna("unknown")
    )
    step("Added English category names via translation file (left join).")

    save_clean(df, "products_clean.csv")
    return df


# ===========================================================================
# 8) SELLERS  (treated as WAREHOUSES / fulfillment origins)
# ===========================================================================
def clean_sellers():
    banner("8) SELLERS  (origins / 'warehouses' in our logistics model)")
    df = load_raw("olist_sellers_dataset.csv")
    print(f"  Loaded {len(df):,} rows.")

    # Clean in Week 0. Standardize the text columns for consistent joins.
    df["seller_city"] = df["seller_city"].str.strip().str.lower()
    df["seller_state"] = df["seller_state"].str.strip().str.upper()
    step("Standardized seller_city (lowercase) and seller_state (uppercase).")

    save_clean(df, "sellers_clean.csv")
    return df


# ===========================================================================
# MAIN: run every cleaning step in order and print a final summary.
# ===========================================================================
def main():
    banner("WEEK 1 DATA CLEANING - Supply Chain & Logistics Optimizer")
    print("Reading raw CSVs from data/ (never modified).")
    print(f"Writing cleaned CSVs to: {PROCESSED_DIR}")

    clean_customers()
    clean_geolocation()
    clean_order_items()
    clean_payments()
    clean_reviews()
    clean_orders()
    clean_products()
    clean_sellers()

    banner("DONE - cleaning complete")
    print("  Cleaned files now live in the processed/ folder.")
    print("  Next: run notebooks/week1_dataset_joins.py to connect them all.")
    print("  Remember: the original data/ files were NOT changed.")


if __name__ == "__main__":
    main()
