# REST API Design (Week 4)

This document describes the **REST conventions** every endpoint in the Week 4
backend follows: how resources map to URLs, which HTTP methods do what, the
status codes returned, and the shared conventions for filtering, sorting,
searching, and pagination.

For the framework choices see [`fastapi_design.md`](fastapi_design.md); for the
overall layering see [`api_architecture.md`](api_architecture.md).

---

## What REST means here

**REST** treats data as **resources** (nouns) addressed by **URLs**, acted on
with standard **HTTP methods** (verbs). The design is intentionally predictable:
once you know the pattern for one entity, you know it for all seven.

The seven resources map one-to-one to the Week 3 tables:

| Resource | URL prefix | Week 3 table |
|----------|------------|--------------|
| Customers | `/customers` | `customers` |
| Warehouses | `/warehouses` | `warehouses` |
| Inventory | `/inventory` | `inventory` |
| Vehicles | `/vehicles` | `vehicles` |
| Delivery routes | `/routes` | `delivery_routes` |
| Orders | `/orders` | `orders` |
| Disruptions | `/disruptions` | `disruptions` |

---

## HTTP methods (the verbs)

Every entity supports the same set of operations:

| Method | URL | Meaning | Success code |
|--------|-----|---------|--------------|
| `GET` | `/things` | list (filter/search/sort/paginate) | 200 |
| `GET` | `/things/{id}` | fetch one by id | 200 |
| `POST` | `/things` | create a new one | 201 Created |
| `PUT` | `/things/{id}` | replace an existing one | 200 |
| `PATCH` | `/things/{id}` | partially update an existing one | 200 |
| `DELETE` | `/things/{id}` | delete one | 204 No Content |

- `GET` never changes data (it is "safe").
- `PUT` is intended as a full replacement; `PATCH` changes only the fields sent.
  Because our update schemas make every field optional, both accept partial
  bodies, but they express different intent and are documented separately.
- `DELETE` returns `204 No Content` — success with an empty body.

There is one small extra convenience endpoint,
`GET /disruptions/active`, which returns all currently-active disruptions by
reusing the Week 3 `crud.get_active_disruptions()` query.

---

## Status codes

| Code | Meaning in this API |
|------|---------------------|
| 200 OK | successful read or update |
| 201 Created | a POST created a new resource |
| 204 No Content | a DELETE succeeded |
| 400 Bad Request | a malformed request (e.g. sorting by a disallowed column) |
| 401 Unauthorized | reserved for future authentication (not logged in) |
| 403 Forbidden | reserved for future authorization (not allowed) |
| 404 Not Found | the resource id does not exist |
| 409 Conflict | a duplicate id, or a reference to something missing |
| 422 Unprocessable | the request body/query failed validation |
| 500 Internal Error | an unexpected server-side failure (details logged) |

`401` and `403` are documented now but not enforced — authentication arrives in
a later week, and the design already reserves their place.

---

## The consistent error shape

Every error, from any layer, is returned in one envelope so callers learn it
once:

```json
{
  "error": {
    "code": "not_found",
    "message": "Warehouse 'WH-9999' was not found.",
    "details": [ { "field": "customer_state", "problem": "..." } ]
  }
}
```

`code` is a short, stable string a program can branch on; `message` is a
human-readable sentence; `details` is optional structured context (e.g. which
fields failed validation). Raw SQL and stack traces are **never** included — they
are logged server-side instead.

---

## List conventions (filtering, searching, sorting, pagination)

All list endpoints (`GET /things`) share the same query parameters.

### Pagination

Large tables are returned in **pages**, never all at once.

| Parameter | Meaning | Default |
|-----------|---------|---------|
| `page` | which page (starts at 1) | 1 |
| `page_size` | rows per page | 20 (max 100) |

The response is always the same envelope:

```json
{
  "items": [ { "...": "one row" } ],
  "pagination": {
    "total": 150, "page": 1, "page_size": 20,
    "total_pages": 8, "has_next": true, "has_prev": false
  }
}
```

Example: `GET /warehouses?page=2&page_size=50`.

### Filtering

Each endpoint documents the exact columns it can filter by (a safelist). Filters
are exact matches, combined with AND.

Example: `GET /warehouses?operating_status=active&warehouse_state=SP`.

### Searching

`?search=<term>` does a case-insensitive, partial-text match across the text
columns that endpoint documents (matching any of them).

Example: `GET /customers?search=sao` matches the city, id, or unique id.

### Sorting

`?sort_by=<column>&sort_dir=asc|desc`. Only safelisted columns may be sorted by;
an unknown column returns `400` with a clear message listing the allowed ones.

Example: `GET /warehouses?sort_by=capacity&sort_dir=desc`.

All four can be combined:

```
GET /inventory?inventory_status=low_stock&sort_by=stock_level&sort_dir=asc&page=1&page_size=25
```

---

## Design principles

- **Uniformity.** Every entity behaves identically, so the API is easy to learn
  and to consume.
- **Safelisted inputs.** Filtering and sorting are restricted to declared
  columns, preventing invalid or unsafe queries.
- **Stable shapes.** The list envelope and error envelope never change form, so
  clients (including the future dashboard) can rely on them.
- **Thin routers, logic in services.** Endpoints only translate HTTP to service
  calls; the rules live in the service layer and reuse the Week 3 CRUD helpers.

These conventions give the project a consistent, predictable surface that the
optimization engine, agents, and dashboard in later weeks all build on.
