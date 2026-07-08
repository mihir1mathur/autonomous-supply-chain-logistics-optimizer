"""
api/ package  (Week 4)
Project: Supply Chain & Logistics Optimizer

This package is the BACKEND: it turns the Week 3 database into a REST API that
other programs (a dashboard, agents, another service) can call over HTTP.

WHAT IS AN API? (zero-knowledge version)
  API = Application Programming Interface. It is a "menu" of things one program
  can ask another program to do. A REST API is an API you talk to over the web
  using plain HTTP (the same protocol your browser uses), sending and receiving
  JSON (plain text data). So instead of writing Python that imports our database
  code, another program just sends an HTTP request like
      GET http://localhost:8000/warehouses/WH-0001
  and gets back JSON describing that warehouse.

HOW THIS PACKAGE IS ORGANISED (each file explained where it lives)
  main.py         - creates the FastAPI app, wires everything together, runs it.
  config.py       - reads API settings (title, version, page sizes) from .env.
  database.py     - REUSES the Week 3 database connection; gives FastAPI a
                    per-request database session.
  dependencies.py - small reusable pieces FastAPI injects into endpoints
                    (the DB session, the pagination query parameters).
  schemas/        - Pydantic models: the SHAPE of the JSON going in and out.
  routers/        - the URL endpoints (one file per entity). THIN: they only
                    receive requests and call services.
  services/       - the business logic (one file per entity). This is where the
                    real work happens; routers never touch the database directly.
  utils/          - shared helpers: custom errors, pagination, query building.

THE ONE RULE THAT KEEPS THIS CLEAN (layered architecture)
      Client -> Router -> Service -> SQLAlchemy -> PostgreSQL -> JSON response
  Each layer only talks to the next one down. That separation is what lets
  later weeks (OR-Tools, Redis, CrewAI, a dashboard, AWS) plug in without a
  rewrite. See docs/api_architecture.md for the full explanation.

NOTHING here connects to the database at import time - importing api/ is always
safe even if PostgreSQL is not running (the Week 3 engine is lazy).
"""
