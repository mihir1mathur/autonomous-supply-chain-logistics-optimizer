"""
database/ package - the persistence layer for the Supply Chain & Logistics
Optimizer (introduced in Week 3).

It contains:
  - config.py      : reads database settings from environment variables.
  - connection.py  : the SQLAlchemy engine, session factory, and Base class.
  - init_db.py      : creates all tables in PostgreSQL.
  - crud.py         : simple read/write helper functions used by later weeks.

Nothing here connects to the database at import time - importing this package
is always safe even if PostgreSQL is not running.
"""
