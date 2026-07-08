"""
============================================================================
DATABASE INITIALIZATION  (Week 3)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SCRIPT DOES
---------------------
  1. Tests the connection to PostgreSQL (clear error if it fails).
  2. Creates ALL tables defined by our SQLAlchemy models.
  3. Prints the names of the tables that now exist.

It NEVER deletes data by default. create_all() only creates tables that do
not already exist - it leaves existing tables and their rows untouched.

RESET (DESTRUCTIVE - opt in only)
---------------------------------
  Running with the explicit flag  --reset  will DROP every table (deleting
  all data) and recreate them empty. The script warns clearly before doing
  this. Without the flag, nothing is ever dropped.

HOW TO RUN (from the project root)
----------------------------------
    # one-time: create the database itself (outside this script)
    createdb supply_chain_optimizer

    # create the tables
    python database/init_db.py

    # DESTRUCTIVE: drop everything and recreate empty tables
    python database/init_db.py --reset
============================================================================
"""

import os
import sys

# Make sure the project root is importable when run as `python database/init_db.py`.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import inspect

# Importing `models` registers every table on Base.metadata.
import models  # noqa: F401  (imported for its side effect of registering tables)
from database.connection import Base, engine, test_connection


def list_tables():
    """Ask the live database which tables currently exist."""
    inspector = inspect(engine)
    return sorted(inspector.get_table_names())


def create_all_tables():
    """Create any tables that do not exist yet. Existing tables are untouched."""
    Base.metadata.create_all(bind=engine)


def reset_all_tables():
    """DROP every table (deletes all data) then recreate them empty."""
    print("\n  !!! RESET REQUESTED - this will DROP ALL TABLES and DELETE ALL DATA !!!")
    print("  Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("  Recreating empty tables...")
    Base.metadata.create_all(bind=engine)


def main():
    reset = "--reset" in sys.argv[1:]

    print("=" * 70)
    print("WEEK 3 - DATABASE INITIALIZATION")
    print("=" * 70)

    # STEP 1: never touch the schema if we cannot even connect.
    if not test_connection():
        print("\nAborting: fix the connection above, then run this script again.")
        sys.exit(1)

    # STEP 2: create (or, only if asked, reset) the tables.
    if reset:
        reset_all_tables()
    else:
        print("\nCreating tables (existing tables are left untouched)...")
        create_all_tables()

    # STEP 3: report what exists now.
    tables = list_tables()
    print(f"\nTables now in the database ({len(tables)}):")
    for name in tables:
        print(f"  - {name}")

    print("\nDone. Next: python notebooks/week3_load_database.py")


if __name__ == "__main__":
    main()
