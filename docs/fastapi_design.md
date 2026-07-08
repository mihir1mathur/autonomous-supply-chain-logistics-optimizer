# FastAPI Design (Week 4)

This document explains the **FastAPI-specific** design choices behind the Week 4
backend: why FastAPI, how dependency injection is used, the request/response
lifecycle, and how Pydantic schemas relate to the Week 3 SQLAlchemy models.

For the overall layering and the project roadmap see
[`api_architecture.md`](api_architecture.md); for the REST conventions see
[`rest_api_design.md`](rest_api_design.md).

---

## Why FastAPI (in depth)

- **The framework writes the docs.** From the type hints and Pydantic schemas,
  FastAPI produces an OpenAPI specification and a live Swagger UI. Documentation
  cannot fall out of sync with the code because it *is* the code.
- **Validation is declarative.** You describe the shape of the data once (a
  Pydantic schema); FastAPI enforces it on every request and reply. Invalid
  input is rejected with a precise 422 before a single line of business logic
  runs.
- **Dependency injection is first-class.** Shared needs (a database session,
  pagination parameters, later authentication) are declared, not hand-wired.
- **Performance and future async.** FastAPI runs on ASGI via Uvicorn. Endpoints
  are synchronous today for clarity, but the door is open to async I/O (useful
  when Redis and external calls arrive) with no structural change.
- **Type-hinted Python.** Endpoints are ordinary functions, keeping the
  project's beginner-friendly, well-commented style.

---

## Application structure

`api/main.py` builds the app with a small factory function, `create_app()`:

1. Creates the `FastAPI` instance with the title/version/description from
   `api/config.py`.
2. Adds **CORS** middleware (which browser origins may call the API).
3. Registers the **exception handlers** (clean JSON errors; no SQL leaks).
4. Adds tiny non-database endpoints: `/` (welcome + docs pointer) and `/health`
   (liveness).
5. **Includes every entity router** from `api/routers/`.

The module exposes `app` for the server:

```bash
uvicorn api.main:app --reload
```

`--reload` restarts on file changes during development. The app does **not**
connect to the database at import time — it only opens a session per request —
so importing or starting the app is always safe even if PostgreSQL is down.

---

## Configuration

`api/config.py` uses **pydantic-settings**. Each setting is read from an
environment variable (prefixed `API_`) with a safe default, so the API runs with
no `.env` at all:

| Setting | Env var | Default | Purpose |
|---------|---------|---------|---------|
| title | `API_TITLE` | Supply Chain & Logistics Optimizer API | shown in the docs |
| version | `API_VERSION` | 0.4.0 | 0.4 = Week 4 |
| default_page_size | `API_DEFAULT_PAGE_SIZE` | 20 | list page size |
| max_page_size | `API_MAX_PAGE_SIZE` | 100 | hard cap per page |
| cors_origins | `API_CORS_ORIGINS` | `*` | allowed browser origins |

Database connection settings are **not** duplicated here — they remain in the
Week 3 `database/config.py`, which the API reuses.

---

## Dependency injection

**Dependency injection** means an endpoint *declares* what it needs and FastAPI
*provides* it. Instead of each endpoint building a database session or parsing
pagination parameters itself, it writes:

```python
@router.get("/warehouses/{warehouse_id}", response_model=WarehouseResponse)
def get_warehouse(warehouse_id: str, db: Session = Depends(get_db)):
    return warehouse_service.get(db, warehouse_id)
```

FastAPI sees `Depends(get_db)`, runs `get_db()`, injects the yielded session,
and cleans it up when the request ends.

Three shared dependencies (in `api/dependencies.py`):

- **`get_db`** — opens **one database session per HTTP request** and guarantees
  it is closed afterwards (with rollback on error). This is the web equivalent
  of the Week 3 `get_session()` context manager.
- **`pagination_params`** — reads `?page`, `?page_size`, `?sort_by`, `?sort_dir`
  from the URL and returns a validated `PageParams` object, clamping the page
  size to `API_MAX_PAGE_SIZE`.
- **`search_query`** — reads an optional `?search=` free-text term.

Why this matters for the roadmap: because endpoints only *declare* their needs,
a need can be satisfied differently later without touching endpoints. A Redis
cache (Week 6) or an authentication check can be introduced as a dependency, and
every endpoint benefits automatically.

---

## The request/response lifecycle

For a read (`GET /warehouses/WH-0001`):

```
client -> uvicorn -> FastAPI routing -> get_db (session opened)
       -> router endpoint (thin) -> service.get() -> SQLAlchemy -> PostgreSQL
       -> WarehouseResponse schema serialises to JSON
       -> get_db closes the session -> client receives 200 + JSON
```

For a write (`POST /customers`):

```
client sends JSON body -> Pydantic CustomerCreate validates it (422 if bad)
       -> router calls customer_service.create()
       -> service checks for duplicate id (409 if exists), inserts, COMMITS
       -> CustomerResponse serialises the new row -> 201 Created + JSON
```

The session lifecycle is tied to the request: opened by `get_db`, used by the
service, committed by the service on writes, and always closed at the end.

---

## Pydantic schemas vs. SQLAlchemy models

This is the central distinction in the API layer:

- A **SQLAlchemy model** (`models/*.py`, Week 3) describes a **database table** —
  what is stored on disk: columns, keys, relationships.
- A **Pydantic schema** (`api/schemas/*.py`, Week 4) describes the **JSON at the
  API boundary** — what a caller may send and what they receive. It validates
  incoming data and controls exactly which fields are exposed.

They are kept separate so the database shape and the public API shape can evolve
independently. The bridge between them is `from_attributes=True` on the response
schemas: it lets Pydantic build a response by reading attributes straight off a
SQLAlchemy row.

Each entity has **four** schemas:

| Schema | Role |
|--------|------|
| `<Entity>Base` | shared fields + validation rules (the "validation schema") |
| `<Entity>Create` | the POST request body (required fields, e.g. the id) |
| `<Entity>Update` | the PUT/PATCH body — every field optional (partial change) |
| `<Entity>Response` | the reply body — includes the id, reads from the ORM row |

Validation rules live in `Base` (and in shared enums in
`api/utils/validation.py`), so `Create` and `Update` share one source of truth,
and the allowed status values mirror the Week 2/Week 3 rules exactly.

---

## Error handling design

Handlers registered in `main.py` turn every failure into one JSON envelope:

```json
{ "error": { "code": "conflict", "message": "Customer '...' already exists." } }
```

- Our own typed exceptions (`NotFoundError`, `DuplicateError`, ...) carry the
  HTTP status they should become.
- Pydantic `RequestValidationError` → 422 with a trimmed list of the offending
  fields.
- Database `IntegrityError` → 409; any other `SQLAlchemyError` → 500 with the
  **raw detail logged, not returned**.
- A final catch-all → 500 so nothing ever escapes as a stack trace.

This is why a production API never exposes raw SQL: the real detail is useful
only to the maintainers (and is a security risk if leaked), so it is logged
server-side while the caller gets a safe, generic message.

---

## Testing the API

Two Week 4 scripts exercise the running API over real HTTP using `httpx`:

- `notebooks/week4_api_demo.py` — happy-path demo: list, get, create, update,
  patch, delete, filtering, sorting, searching, pagination.
- `notebooks/week4_api_validation.py` — the error paths: 404, 409 duplicate,
  422 validation, 400 bad sort column, and pagination guardrails.

Both print clean, explained output and clean up any test rows they create.
