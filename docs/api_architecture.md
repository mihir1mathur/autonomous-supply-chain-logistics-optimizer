# API Architecture (Week 4)

This document explains the **backend API layer** introduced in Week 4: why it
exists, how it is organised into layers, how a request flows through it, and how
it is designed so the later parts of the project (route optimization, caching,
agents, a dashboard, authentication, and cloud deployment) can plug in with
minimal changes.

Companion documents:

- [`fastapi_design.md`](fastapi_design.md) — why FastAPI, dependency injection,
  and the request/response lifecycle in detail.
- [`rest_api_design.md`](rest_api_design.md) — the REST conventions every
  endpoint follows (resources, HTTP methods, status codes, pagination).
- [`database_design.md`](database_design.md) — the Week 3 database this API sits
  on top of and reuses.

---

## Why introduce an API now?

Week 3 put the data into **PostgreSQL** behind a clean **SQLAlchemy** layer.
That is reachable from Python, but a real platform needs the data reachable by
*other programs* — a dashboard, background agents, another service, or a
teammate's script — ideally over the network and in a language-neutral format.

An **API (Application Programming Interface)** is exactly that: a defined set of
operations one program exposes for others to call. A **REST API** exposes those
operations over **HTTP** (the web's protocol) using **JSON** (plain-text data).
So instead of importing our database code, any program can simply send:

```
GET http://localhost:8000/warehouses/WH-0001
```

and receive JSON describing that warehouse. Week 4 builds that API on top of the
Week 3 database **without duplicating any database logic** — it reuses the same
engine, models, and CRUD helpers.

---

## Why FastAPI

- **Automatic, interactive documentation.** FastAPI generates a live Swagger UI
  and an OpenAPI specification from the code itself, so the docs can never drift
  from the implementation.
- **Validation built in.** Request and response shapes are declared with
  **Pydantic**; bad input is rejected with a clear error before it reaches our
  code.
- **Modern and fast.** It is built on ASGI (asynchronous) foundations and is one
  of the fastest Python frameworks, with room to grow into async endpoints.
- **Dependency injection.** A clean, first-class way to share the database
  session, pagination parameters, and (later) authentication across endpoints.
- **Small, readable code.** Endpoints are plain Python functions with type
  hints, which keeps the beginner-friendly style of the project.

See [`fastapi_design.md`](fastapi_design.md) for the deeper reasoning.

---

## The layered architecture

The single rule that keeps the backend clean is that each layer only talks to
the next one down:

```
        Client  (browser, dashboard, agent, script, curl)
          |   HTTP request (GET/POST/PUT/PATCH/DELETE) + JSON
          v
   +-------------------+
   |   API Router      |   api/routers/*.py
   |   (THIN)          |   - reads the request + query params
   |                   |   - calls a service, returns the result
   +-------------------+   - NO database access, NO business logic
          |
          v
   +-------------------+
   |   Service Layer   |   api/services/*.py
   |   (business logic)|   - all rules live here (e.g. stock->status)
   |                   |   - reuses the Week 3 CRUD helpers
   +-------------------+
          |
          v
   +-------------------+
   |   SQLAlchemy      |   models/*.py + database/ (Week 3, REUSED)
   |   (ORM)           |   - Python objects mapped to tables
   +-------------------+
          |
          v
   +-------------------+
   |   PostgreSQL      |   the Week 3 database (unchanged)
   +-------------------+
          |
          v
        JSON Response  (Pydantic response schema -> JSON) back to the client
```

**Why the separation matters:** the router only speaks HTTP, the service only
holds logic, and only the service touches the database. That is what lets later
weeks change one layer without disturbing the others — for example, adding a
Redis cache inside a service, or an authentication check as a router dependency,
touches nothing else.

### What lives in each folder

```
api/
├── main.py           # creates the FastAPI app, wires routers + error handlers
├── config.py         # API settings (title, version, page sizes, CORS) from .env
├── database.py       # REUSES the Week 3 engine/session; get_db() per request
├── dependencies.py   # shared injectables: get_db, pagination_params, search
├── schemas/          # Pydantic models = the JSON shape in/out (one per entity)
├── routers/          # the URL endpoints (thin) — one per entity
├── services/         # the business logic — one per entity (+ base_service.py)
└── utils/            # exceptions (+ handlers), pagination, validation/enums
```

Seven entities are exposed, matching the Week 3 tables: **customers,
warehouses, inventory, vehicles, routes (delivery_routes), orders,
disruptions**.

---

## The request/response lifecycle

Walking through `GET /warehouses/WH-0001` step by step:

1. **Client** sends an HTTP GET request to the URL.
2. **Uvicorn** (the server) receives it and hands it to the FastAPI app.
3. **CORS + routing.** FastAPI matches the path to the `get_warehouse` endpoint
   in `api/routers/warehouses.py`.
4. **Dependency injection.** FastAPI sees `db: Session = Depends(get_db)`, opens
   one database session for this request, and injects it.
5. **Router (thin).** The endpoint calls `warehouse_service.get(db, "WH-0001")`.
6. **Service.** Looks the row up via SQLAlchemy. If missing, it raises
   `NotFoundError`; otherwise it returns the `Warehouse` object.
7. **SQLAlchemy + PostgreSQL.** The query runs against the Week 3 database.
8. **Response shaping.** The `WarehouseResponse` Pydantic schema converts the
   SQLAlchemy object into JSON (only the exposed fields).
9. **Session cleanup.** `get_db` closes the session (always, even on error).
10. **Client** receives `200 OK` with the JSON body — or a clean error envelope
    if something went wrong.

For a write (`POST`/`PUT`/`PATCH`/`DELETE`), step 5 also validates the request
body against the `Create`/`Update` schema first, and the service commits the
transaction.

---

## Validation and error handling

- **Input validation** happens at the boundary via Pydantic schemas. A wrong
  type, a missing required field, or an invalid enum value (e.g. a vehicle type
  that is not one of the allowed values) is rejected with **422** before any of
  our logic runs.
- **Business errors** are raised by services as typed exceptions
  (`NotFoundError` → 404, `DuplicateError`/`ConflictError` → 409,
  `BadRequestError` → 400) and turned into a consistent JSON envelope by handlers
  registered in `main.py`.
- **Database errors** are caught centrally: the raw detail is **logged
  server-side** and a **generic, safe** message is returned to the caller, so
  the API never leaks SQL or internal structure.

Every error, whatever its source, comes back in the **same shape**:

```json
{ "error": { "code": "not_found", "message": "Warehouse 'WH-9999' was not found." } }
```

Status codes used: `400` bad request, `401`/`403` reserved for future
authentication, `404` not found, `409` conflict/duplicate, `422` validation,
`500` internal error.

---

## Automatic documentation (OpenAPI / Swagger)

Once the server is running, three URLs are available for free:

- `GET /docs` — **Swagger UI**, an interactive page to try every endpoint.
- `GET /redoc` — **ReDoc**, a clean reading view of the same spec.
- `GET /openapi.json` — the **OpenAPI** specification (machine-readable), which
  tools can use to generate clients, tests, or dashboards.

Because the spec is generated from the code, the documentation always matches
what the API actually does.

---

## Future-ready design

The layering is deliberately chosen so the remaining roadmap plugs in with
minimal code change:

| Future capability | Where it plugs in | Why nothing else changes |
|-------------------|-------------------|--------------------------|
| **OR-Tools** route optimization (Week 5) | a new service that writes optimized `vehicle_id`/estimates into the reserved route columns | routers and schemas already expose routes; the DB columns are already reserved (Week 3) |
| **Redis** caching (Week 6) | wrap hot reads inside services / a cache dependency | routers and the DB are untouched |
| **CrewAI** agents (Week 7) | agents call the same service functions | services are the shared, reusable logic |
| **Authentication** | a `current_user` router dependency + 401/403 (already reserved) | endpoints only *declare* the dependency |
| **Dashboard** (Week 8) | reads the existing JSON endpoints | the API is already language-neutral |
| **AWS** deployment (Week 9) | point the DB URL at a managed PostgreSQL via `.env` | the engine URL is the only change |

The key design decisions that make this possible: **routers independent from
business logic**, **business logic independent from the database
implementation**, **the Week 3 database layer reused unchanged**, **dependency
injection throughout**, and **stable JSON response shapes**.

---

## Project architecture evolution

Week 4 is one step in an incremental build. Each week builds directly on the
outputs of the previous one:

```
Week 0   Understand the dataset          (real Olist e-commerce data)
   |
Week 1   Clean + join the data           (processed/ master table)
   |
Week 2   Logistics simulation            (warehouses, inventory, vehicles,
   |                                       routes, disruptions)
Week 3   PostgreSQL database             (SQLAlchemy models + CRUD)
   |
Week 4   FastAPI backend  <-- THIS WEEK  (REST API reusing Week 3)
   |
Week 5   Route optimization (OR-Tools)   (writes back into reserved columns)
   |
Week 6   Redis caching                   (in front of hot API reads)
   |
Week 7   CrewAI multi-agent system       (agents call the services)
   |
Week 8   Monitoring & evaluation metrics (measure the system)
   |
Week 9   AWS deployment                  (managed PostgreSQL + hosting)
   |
Week 10  Production system               (the full platform)
```

Week 4 turns the stored data of Week 3 into a shared, documented, network-
reachable service — the surface every later week reads from and writes to.
