"""
============================================================================
API DATABASE WIRING  (Week 4)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES (and, importantly, what it does NOT do)
-----------------------------------------------------------
  This file connects the API to the database WITHOUT re-building any of the
  database code from Week 3. It re-exports the Week 3 engine / session factory
  / Base, and adds ONE new thing FastAPI needs: a per-request session
  "dependency" called get_db().

  It deliberately duplicates NONE of Week 3's logic. The engine, the
  SessionLocal factory, and the Base class all come straight from
  database/connection.py. If we ever change the database URL or pooling, we
  change it in ONE place (Week 3) and the API follows automatically.

WHY DOES FASTAPI NEED A SPECIAL SESSION FUNCTION?
-------------------------------------------------
  A database SESSION is one short conversation with the database (Week 3
  note 03). The golden rule is: open a fresh session for each unit of work,
  and ALWAYS close it afterwards - even if an error happens - so connections
  are never leaked.

  In a web API, the natural "unit of work" is ONE HTTP REQUEST. So we want:
      request comes in  -> open a session
      endpoint runs     -> use that session
      response goes out -> close the session (always)
  FastAPI does exactly this if we give it a generator dependency that `yield`s
  a session and closes it in a finally block. That is get_db() below.

HOW IT IS USED (dependency injection - explained fully in dependencies.py)
--------------------------------------------------------------------------
  An endpoint or service simply declares that it needs a session:

      from fastapi import Depends
      from api.database import get_db

      @router.get("/warehouses/{warehouse_id}")
      def read_warehouse(warehouse_id: str, db: Session = Depends(get_db)):
          ...

  FastAPI sees Depends(get_db), calls get_db(), hands the yielded session to
  the endpoint, and closes it when the request finishes. The endpoint never
  has to remember to open or close anything.
============================================================================
"""

from collections.abc import Generator

from sqlalchemy.orm import Session

# REUSE Week 3 - do not re-create any of this. Importing database.connection
# does NOT open a connection (the engine is lazy), so this stays safe to import.
from database.connection import Base, SessionLocal, engine  # noqa: F401 (re-exported)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields ONE database session per HTTP request and
    guarantees it is closed afterwards.

    This mirrors the Week 3 get_session() context manager, but in the shape
    FastAPI wants (a generator it can drive). The subtle difference: here we do
    NOT auto-commit on the way out. The service layer commits explicitly when
    it changes data (create/update/delete), which keeps the "who decides to
    save" question answered in exactly one place - the services.

    On an exception we roll back so a half-finished change is never left behind,
    then re-raise so the error handlers in main.py can turn it into a clean JSON
    response.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
