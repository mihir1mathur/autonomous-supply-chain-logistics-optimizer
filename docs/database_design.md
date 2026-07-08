# Database Design (Week 3)

This document explains the **database layer** introduced in Week 3: why it
exists, the technology choices behind it, how the schema is organised, and how
it is designed so the later parts of the project (optimization, agents, API,
caching, cloud) can plug in with minimal changes.

For the exact tables, columns, keys, and indexes, see the companion reference
[`database_schema.md`](database_schema.md).

---

## Why introduce a database now?

Weeks 0–2 produced data as CSV files:

- `processed/` — cleaned, joined real Olist data (Week 1).
- `simulation/` — the simulated logistics layer: warehouses, inventory,
  vehicles, disruptions, and estimated routes (Week 2).

CSV files are perfect for building and inspecting that data, but they are a
weak foundation for an actual platform:

- **No shared, concurrent access.** An API, a dashboard, and background agents
  cannot all read and write the same CSV safely at the same time.
- **No enforced relationships.** Nothing stops a route from referencing an
  order or warehouse that does not exist.
- **No fast lookups.** Answering "which items at warehouse `WH-0007` are low on
  stock?" means re-reading and scanning an entire file every time.
- **No transactions.** A multi-step update (reduce stock, then assign a
  vehicle) cannot be made all-or-nothing.

A database solves all four. Week 3 moves the CSV data into **PostgreSQL** and
puts a clean Python layer in front of it, without changing any of the source
CSVs (they remain the reproducible inputs).

---

## Why PostgreSQL

- **Relational fit.** The data is naturally relational — orders belong to
  customers, inventory links products to warehouses, routes connect orders,
  warehouses, and customers. A relational database models this directly with
  primary keys and foreign keys.
- **Strong integrity.** PostgreSQL enforces foreign keys, uniqueness, and
  types, so the data cannot drift into an inconsistent state.
- **Scales with the project.** It handles the ~100k-row tables here comfortably
  and has plenty of headroom as the project grows.
- **Rich feature set.** Advanced indexing, JSON columns, window functions, and
  (via PostGIS, later) geospatial queries for routing.
- **Free, open-source, and ubiquitous.** It runs locally for development and is
  available as a managed service on every major cloud (relevant for the planned
  AWS deployment).

## Why SQLAlchemy (ORM)

- **Python classes map to tables.** Each table is a Python class in `models/`.
  We work with objects (`warehouse.capacity`) instead of writing raw SQL
  strings everywhere.
- **Relationships in code.** `order.customer` or `warehouse.inventory_items`
  navigate foreign keys automatically.
- **One schema, one source of truth.** The models define the schema; the same
  models create the tables and drive every query.
- **Safety.** Parameterised queries avoid SQL-injection and quoting bugs.
- **Portability.** The engine URL is the only thing that changes to point at a
  different PostgreSQL server (local vs. cloud).

Supporting choices: **psycopg (v3)** is the PostgreSQL driver SQLAlchemy talks
through, and **python-dotenv** loads the database credentials from a local
`.env` file so no password is ever committed. **Alembic** is installed as a
dependency for future schema migrations but is intentionally **not** initialised
yet — this week the schema is created once.

---

## Architecture

The database layer is split into a small, readable set of files:

```
database/
├── config.py       # reads settings from .env, builds the database URL
├── connection.py   # SQLAlchemy engine, Session factory, Base class
├── init_db.py      # creates all tables (and, opt-in, resets them)
└── crud.py         # reusable read/write helper functions

models/
├── customer.py     # customers        (real)
├── seller.py       # sellers          (real)
├── product.py      # products         (real)
├── order.py        # orders           (real)
├── warehouse.py    # warehouses       (real location + simulated ops)
├── inventory.py    # inventory        (simulated)
├── vehicle.py      # vehicles         (simulated)
├── route.py        # delivery_routes  (real ids + computed estimates)
└── disruption.py   # disruptions      (simulated)

notebooks/
├── week3_load_database.py   # loads processed/ + simulation/ CSVs into the DB
└── week3_test_crud.py       # exercises every CRUD function end-to-end
```

**Data flow:**

```
 processed/*.csv  (Week 1, real)          models/*.py define the schema
 simulation/*.csv (Week 2, simulated)             │
             │                                    ▼
             │                       database/init_db.py -> CREATE TABLE ...
             └──> week3_load_database.py ─────────────────┐
                  (read-only import, never edits CSVs)    ▼
                                                    PostgreSQL tables
                                                          │
                                            database/crud.py (query/update)
                                                          │
                                    (future) FastAPI · CrewAI · Streamlit
```

Two deliberate properties:

- **Importing the database package never opens a connection.** Creating the
  engine is lazy, so importing `models` or `database` is always safe even when
  PostgreSQL is not running. A real connection happens only when a query runs.
- **Loading is read-only on the CSVs.** The loader reads `processed/` and
  `simulation/` and writes only to the database. The raw `data/` files and the
  generated CSVs are never modified.

---

## Entity-relationship diagram

```
        sellers                          customers
           │ 1                               │ 1
           │ (top 150 promoted)              │
           ▼ 0..1                            ▼ *
       warehouses                          orders ──────────┐
           │ 1                               │ 1            │
   ┌───────┼───────────┬───────────┐         │             │
   │ *     │ *         │ *         │ *       │ *           │
inventory vehicles delivery_routes disruptions             │
   │ *                 │ * │ *                              │
   ▼ 1                 │   └───────────────► customers *────┘
 products              │ (route -> order, warehouse, customer)
                       ▼ 0..1
                    vehicles   (assigned later by the optimizer)

  1  = "one"        *    = "many"       0..1 = "optional one"
```

In words:

- **sellers → warehouses** — one seller backs zero or one warehouse. The busiest
  150 Olist sellers were promoted to warehouses in Week 2; every warehouse's
  location comes from its seller.
- **customers → orders** — one customer places many orders (in Olist a
  `customer_id` is one record per order; `customer_unique_id` links a real
  person across orders).
- **orders → delivery_routes** — an order can be fulfilled by one or more
  routes.
- **warehouses → inventory** and **products → inventory** — inventory is the
  bridge table: one row means "this warehouse holds this many units of this
  product".
- **warehouses → vehicles** — each vehicle is based at a home warehouse.
- **delivery_routes → order / warehouse / customer** — a route ties those three
  real things together, and has an optional **vehicle** (assigned later by the
  optimizer, `NULL` for now).
- **disruptions → warehouse / route** — a disruption may point at a warehouse
  and/or a specific route; area-wide events leave both `NULL`.

---

## Relationships, keys, and indexes

- **Primary keys** are the natural string ids already present in the data
  (`customer_id`, `warehouse_id`, `route_id`, …). Reusing the real ids keeps
  the database aligned with the CSVs and makes loading idempotent.
- **Foreign keys** enforce integrity: an order cannot reference a missing
  customer, inventory cannot reference a missing product or warehouse, and a
  route cannot reference a missing order/warehouse/customer.
- **Indexes** are placed on every foreign key and on the columns we filter by
  most (`order_status`, `inventory_status`, `availability_status`,
  `operating_status`, `disruption` type/severity/status, and state columns).
  These are exactly the lookups the future API, dashboard, and agents will run
  repeatedly, so they are fast from day one.

See [`database_schema.md`](database_schema.md) for the per-column detail.

---

## Normalization

The schema is normalised to third normal form (3NF) where it matters:

- **Sellers are their own table** rather than copied into every warehouse row.
  A warehouse's location is defined once, by its seller.
- **Inventory is a proper bridge table** between products and warehouses — the
  many-to-many relationship is not flattened into either parent.
- **Facts live with the entity they describe** — vehicle capacity on vehicles,
  stock on inventory, timestamps on orders.

A few fields are **intentionally denormalised** for convenience and read speed,
and this is documented rather than accidental: `delivery_routes` copies the
source/destination city, state, and coordinates so a route can be displayed or
mapped without four joins, and `inventory` keeps a `product_category_name` copy
for quick filtering. These copies are derived from the parent rows at load time
and are never the source of truth.

---

## Why this schema scales

- **Indexed foreign keys** keep joins and filtered lookups fast as tables grow.
- **Bridge tables** (inventory, and later order-level fulfillment) model
  many-to-many relationships without duplicating data.
- **Reserved, nullable columns** (`delivery_routes.vehicle_id`,
  `disruptions.affected_route_id`) let future features attach data **without a
  schema migration** — the relationships already exist, they are simply unused
  today.
- **A centralised CRUD layer** means every consumer (API, agents, dashboard)
  shares the same tested query functions instead of re-implementing SQL.
- **Batch, idempotent loading** (`INSERT ... ON CONFLICT DO NOTHING`) means the
  loader can be re-run safely and scales to the largest table (~99k customers)
  without holding everything in memory at once.

---

## How the future stack plugs in

The database is the integration point for every planned technology. None of
these are implemented yet — the schema is simply designed so they can attach
cleanly.

- **OR-Tools (route optimization).** Reads warehouses, vehicles (with their
  capacity limits), inventory, and the order/route legs; writes optimized
  assignments back by filling in `delivery_routes.vehicle_id` and improving the
  distance/time/cost estimates. No new tables are required — the columns are
  already reserved.
- **CrewAI (autonomous planning).** Reads live state (low stock, active
  disruptions, available vehicles) through the same CRUD functions and records
  what it decides. A planned `agent_decisions` audit table (Week 5) will hang
  off orders/routes/inventory; the design leaves room for it.
- **Redis (caching / queues).** Sits in front of the database to cache hot
  read-only queries (e.g. active disruptions, available vehicles) and to queue
  optimization jobs. Because reads already go through `crud.py`, adding a cache
  is a localised change.
- **FastAPI (backend API).** Reuses `crud.py` directly and reuses the
  `get_session()` context manager as a request-scoped dependency, so HTTP
  endpoints are thin wrappers over already-tested functions.
- **AWS (deployment).** PostgreSQL runs as a managed service (e.g. RDS);
  only the connection settings in `.env` change. Because credentials are read
  from the environment, the same code runs locally and in the cloud unchanged.

---

## Summary

Week 3 turns the Week 1 + Week 2 CSV data into a real, relational PostgreSQL
database with enforced relationships, useful indexes, a clean model layer, and a
reusable CRUD API — designed from the start so optimization, agents, an API,
caching, and cloud deployment can be added later with minimal schema change.
