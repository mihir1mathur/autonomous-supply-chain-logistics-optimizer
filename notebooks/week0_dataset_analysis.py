"""
============================================================================
WEEK 0 - DATASET ANALYSIS SCRIPT
Project: Supply Chain & Logistics Optimizer
Dataset: Brazilian E-Commerce Public Dataset by Olist
============================================================================

WHAT IS THIS FILE?
------------------
This is a simple Python script that *reads* every CSV file in the data/
folder and *describes* it for us. It does NOT change anything. It only looks
at the data and prints a friendly report so a complete beginner can
understand what each file contains.

Think of it like this:
    You just received 9 boxes (the 9 CSV files).
    Before you build anything, you open each box and write down:
        - How big is it?
        - What is inside it?
        - Is anything missing or broken?
This script opens all the boxes for you and writes that report.

HOW TO RUN IT
-------------
1. Open a terminal in the project root: "D:\\Supply Chain Logistics Optimizer"
2. Make sure pandas is installed:   pip install pandas
3. Run:                             python notebooks/week0_dataset_analysis.py

============================================================================
"""

# ---------------------------------------------------------------------------
# STEP 1: Import the tools (libraries) we need.
# ---------------------------------------------------------------------------
# A "library" is a box of ready-made code written by other people so we don't
# have to write it ourselves.
#
# "pandas" is THE library for working with tables of data in Python.
#   - A table = rows and columns, just like an Excel spreadsheet.
#   - pandas calls such a table a "DataFrame".
#
# "os" lets us work with the computer's folders and file paths.
# ---------------------------------------------------------------------------
import os
import pandas as pd


# ---------------------------------------------------------------------------
# STEP 2: Tell the script where the data lives.
# ---------------------------------------------------------------------------
# We figure out the folder this script is in, then go "up one level" to the
# project root, then into the "data" folder. This way the script works no
# matter what folder you run it from.
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))   # .../notebooks
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)                # project root
DATA_DIR = os.path.join(PROJECT_ROOT, "data")             # .../data

# These are the 9 CSV files we expect. (We skip archive.zip on purpose.)
CSV_FILES = [
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
]


# ---------------------------------------------------------------------------
# STEP 3: A helper function that describes ONE CSV file.
# ---------------------------------------------------------------------------
# A "function" is a reusable mini-program. We give it a file name, and it
# prints a full report about that file. We call it once for each CSV.
# ---------------------------------------------------------------------------
def describe_csv(file_name):
    """Load one CSV file and print a beginner-friendly report about it."""

    file_path = os.path.join(DATA_DIR, file_name)

    # A clear visual header so each file's report is easy to find.
    print("\n" + "=" * 78)
    print(f"FILE: {file_name}")
    print("=" * 78)

    # Safety check: if the file is missing, say so and stop here.
    if not os.path.exists(file_path):
        print("  !! File not found. Skipping.")
        return

    # ----- Load the CSV into a pandas DataFrame (our table in memory) -----
    # pd.read_csv reads the comma-separated file and turns it into a table.
    df = pd.read_csv(file_path)

    # ----- 1) SHAPE -----------------------------------------------------
    # "shape" tells us the size of the table as (rows, columns).
    #   rows    = how many records / entries there are
    #             (e.g. how many customers, how many orders)
    #   columns = how many pieces of information we store per record
    #             (e.g. customer id, city, state)
    rows, cols = df.shape
    print(f"\n[1] SHAPE (size of the table)")
    print(f"    Rows (records)   : {rows:,}")
    print(f"    Columns (fields) : {cols}")

    # ----- 2) COLUMN NAMES ----------------------------------------------
    # Column names are the labels at the top of each column. They tell us
    # what each piece of information means.
    print(f"\n[2] COLUMN NAMES (what each piece of info is called)")
    for col in df.columns:
        print(f"    - {col}")

    # ----- 3) DATA TYPES -------------------------------------------------
    # The "data type" tells us what KIND of value is in a column:
    #   object  = text (words), e.g. a city name like "sao paulo"
    #   int64   = whole numbers, e.g. 1, 2, 100
    #   float64 = decimal numbers, e.g. 58.90 (a price)
    # Knowing the type matters: you can add up prices, but not city names.
    print(f"\n[3] DATA TYPES (what KIND of value each column holds)")
    for col, dtype in df.dtypes.items():
        print(f"    - {col}: {dtype}")

    # ----- 4) MISSING VALUES --------------------------------------------
    # A "missing value" is an empty cell - information that was not recorded.
    # Example: an order that was never delivered has an empty delivery date.
    # We count empty cells per column so we know where data is incomplete.
    print(f"\n[4] MISSING VALUES (empty cells per column)")
    missing = df.isnull().sum()           # count of empty cells per column
    any_missing = False
    for col, count in missing.items():
        if count > 0:
            pct = (count / rows) * 100 if rows else 0
            print(f"    - {col}: {count:,} missing ({pct:.1f}% of rows)")
            any_missing = True
    if not any_missing:
        print("    - No missing values. Every cell is filled. ")

    # ----- 5) DUPLICATE ROWS --------------------------------------------
    # A "duplicate row" is a row that is an exact copy of another row.
    # Duplicates can make counts wrong (e.g. counting the same order twice),
    # so it is good to know how many there are.
    duplicate_count = df.duplicated().sum()
    print(f"\n[5] DUPLICATE ROWS (exact copies of other rows)")
    print(f"    - Duplicate rows: {duplicate_count:,}")

    # ----- 6) MEMORY USAGE ----------------------------------------------
    # "Memory" is the computer's short-term workspace (RAM). This tells us
    # how much space the table takes while loaded. Bigger files use more.
    memory_bytes = df.memory_usage(deep=True).sum()
    memory_mb = memory_bytes / (1024 * 1024)   # convert bytes -> megabytes
    print(f"\n[6] MEMORY USAGE (space used while loaded)")
    print(f"    - {memory_mb:.2f} MB")

    # ----- 7) FIRST 5 ROWS ----------------------------------------------
    # ".head()" shows the first few rows so we can SEE real examples of the
    # data instead of only reading descriptions of it.
    print(f"\n[7] FIRST 5 ROWS (a peek at real example data)")
    # to_string() prints the table without cutting columns off.
    print(df.head().to_string())


# ---------------------------------------------------------------------------
# STEP 4: Main entry point - run the report for every file.
# ---------------------------------------------------------------------------
# The "if __name__ == '__main__'" line is standard Python. It means:
# "only run the code below when this file is run directly (not imported)."
# ---------------------------------------------------------------------------
def main():
    print("=" * 78)
    print("WEEK 0 DATASET ANALYSIS - Supply Chain & Logistics Optimizer")
    print("Reading every CSV in the data/ folder and describing it.")
    print(f"Data folder: {DATA_DIR}")
    print("=" * 78)

    # Loop = "do the same thing for each item in a list."
    # Here: run describe_csv() once for every file name in CSV_FILES.
    for file_name in CSV_FILES:
        describe_csv(file_name)

    print("\n" + "=" * 78)
    print("DONE. You have now 'opened every box' and seen what is inside.")
    print("Next: read docs/dataset_overview.md to learn how the files connect.")
    print("=" * 78)


if __name__ == "__main__":
    main()
