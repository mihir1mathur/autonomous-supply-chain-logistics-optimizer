"""
============================================================================
DATABASE CONFIG  (Week 3)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  It reads the database connection settings (host, port, name, user,
  password) from ENVIRONMENT VARIABLES and builds the single "database URL"
  that SQLAlchemy needs to talk to PostgreSQL.

WHY ENVIRONMENT VARIABLES (and not hard-coded values)?
------------------------------------------------------
  A password written directly in code would end up on GitHub for everyone to
  see. Instead we keep secrets in a local file called `.env` (which is NOT
  committed) and read them at runtime. `.env.example` shows which variables
  to set, without any real password.

HOW IT WORKS
------------
  1. python-dotenv loads a local `.env` file (if present) into the
     environment.
  2. We read each setting with os.getenv(name, default). The defaults are
     safe local-development values - never a real password.
  3. We assemble DATABASE_URL in the form SQLAlchemy expects:
         postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME
     ("psycopg" = the psycopg 3 driver we use to reach PostgreSQL.)
============================================================================
"""

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Load variables from a local .env file (if it exists) into the environment.
# If there is no .env file, this does nothing and the defaults below are used.
load_dotenv()


# ---------------------------------------------------------------------------
# Individual settings. Each can be overridden by an environment variable.
# The defaults are safe for local development (NO real password here).
# ---------------------------------------------------------------------------
DATABASE_HOST = os.getenv("DATABASE_HOST", "localhost")
DATABASE_PORT = os.getenv("DATABASE_PORT", "5432")
DATABASE_NAME = os.getenv("DATABASE_NAME", "supply_chain_optimizer")
DATABASE_USER = os.getenv("DATABASE_USER", "postgres")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "")


def build_database_url() -> str:
    """
    Assemble the full SQLAlchemy database URL from the settings above.

    We URL-encode the user and password with quote_plus so that special
    characters (like '@' or ':') in a password do not break the URL.
    """
    user = quote_plus(DATABASE_USER)
    password = quote_plus(DATABASE_PASSWORD)
    return (
        f"postgresql+psycopg://{user}:{password}"
        f"@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
    )


def safe_database_url() -> str:
    """
    The same URL but with the password hidden, so it is safe to PRINT in
    terminal output or logs (we never want to print a real password).
    """
    return (
        f"postgresql+psycopg://{DATABASE_USER}:****"
        f"@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
    )


# The URL the rest of the project imports.
DATABASE_URL = build_database_url()
