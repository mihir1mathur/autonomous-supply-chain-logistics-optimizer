"""
============================================================================
DATABASE CONNECTION  (Week 3)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE PROVIDES (the three things every SQLAlchemy app needs)
---------------------------------------------------------------------
  1. engine        - the low-level object that knows HOW to talk to
                     PostgreSQL (it manages a pool of connections).
  2. SessionLocal  - a factory that hands out "sessions". A SESSION is one
                     conversation with the database: you add/query/update
                     through it, then commit (save) or rollback (undo).
  3. Base          - the declarative base class. Every table model
                     (models/*.py) inherits from Base, which is how
                     SQLAlchemy knows about all our tables.

IMPORTANT: creating the engine does NOT open a connection. Importing this
file is always safe, even if PostgreSQL is not running. A real connection is
only attempted when you actually run a query (or call test_connection()).
============================================================================
"""

from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from database.config import DATABASE_URL, safe_database_url


# ---------------------------------------------------------------------------
# 1) ENGINE - the connection manager.
#    - pool_pre_ping=True checks a connection is still alive before using it
#      (avoids "stale connection" errors), which is friendly for beginners.
#    - echo=False keeps the terminal clean. Set to True to see the raw SQL.
# ---------------------------------------------------------------------------
# connect_args sets a short connection timeout (5 seconds) so that, if
# PostgreSQL is not running, the scripts fail FAST with a clear message
# instead of hanging for a long time.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
    future=True,
    connect_args={"connect_timeout": 5},
)

# ---------------------------------------------------------------------------
# 2) SESSION FACTORY - call SessionLocal() to get a new session.
#    autoflush/autocommit are off so YOU decide exactly when to save.
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# ---------------------------------------------------------------------------
# 3) BASE - the parent class for every model. models/*.py do: class X(Base).
# ---------------------------------------------------------------------------
Base = declarative_base()


@contextmanager
def get_session():
    """
    Hand out a database session and ALWAYS close it afterwards.

    Usage:
        with get_session() as db:
            customer = db.get(Customer, "abc123")

    If something goes wrong inside the block we roll back (undo) so the
    database is never left half-changed. (FastAPI in Week 4 will use a very
    similar dependency.)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def test_connection() -> bool:
    """
    Try to actually reach PostgreSQL and run a trivial query (SELECT 1).

    Returns True on success. On failure it prints a CLEAR, beginner-friendly
    explanation of what to check, and returns False (it does not crash).
    """
    print(f"Testing connection to: {safe_database_url()}")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("  OK - connected to PostgreSQL successfully.")
        return True
    except OperationalError as exc:
        # This is the most common error: the server isn't running, the
        # database doesn't exist yet, or the credentials are wrong.
        print("  ERROR - could not connect to PostgreSQL.")
        print("  Most likely one of these:")
        print("    1. PostgreSQL is not installed or not running.")
        print("    2. The database does not exist yet. Create it with:")
        print("         createdb supply_chain_optimizer")
        print("    3. The settings in your .env file are wrong (host, port,")
        print("       user, password, or database name).")
        print("  Copy .env.example to .env and fill in your real password.")
        print(f"  Technical detail: {exc.orig if hasattr(exc, 'orig') else exc}")
        return False
    except SQLAlchemyError as exc:
        print(f"  ERROR - unexpected database error: {exc}")
        return False
