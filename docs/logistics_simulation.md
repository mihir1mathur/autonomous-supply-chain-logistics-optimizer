# Logistics Simulation

This document explains the **simulated logistics layer** built in Week 2 of the
Supply Chain & Logistics Optimizer.

It builds directly on:

- [`dataset_overview.md`](dataset_overview.md) — what the raw Olist data is.
- [`logistics_data_model.md`](logistics_data_model.md) — how the e-commerce data
  is reinterpreted as a logistics dataset (the mapping this layer extends).
- [`future_database_design.md`](future_database_design.md) — the planned tables
  (`warehouses`, `inventory`, `vehicles`, `disruptions`, `routes`) that these
  simulation files populate.

For the precise list of every modeling assumption, see
[`simulation_assumptions.md`](simulation_assumptions.md).

---

## Why simulation is needed

The Olist dataset is a **historical record of online sales**: orders, customers,
sellers, products, payments, reviews, delivery timestamps, and locations. It was
never meant to run a logistics operation, so several things a real fulfillment
system depends on are simply **not in the data**:

- no **warehouse capacity** (how much a location can hold);
- no **inventory / stock levels** (how many units are on the shelf);
- no **delivery vehicles** (Olist never recorded carrier fleets);
- no **live disruptions** (traffic, weather, road closures);
- no **route plans** (just origin and destination points).

To build optimization (Week 3), agents (Week 5), and disruption-driven
re-planning (Week 7) later, we need these operational pieces now. Week 2
**generates them as realistic simulated datasets layered on top of the cleaned,
real Week 1 data** — keeping the real foundation untouched and clearly labelling
what is invented.

---

## Real vs. generated (at a glance)

| Dataset | File | Real, generated, or computed? |
|---------|------|-------------------------------|
| Warehouses | `simulation/warehouses.csv` | **Real** locations (Olist sellers) + **generated** capacity/utilization/status |
| Inventory | `simulation/inventory.csv` | **Generated** stock, scaled from **real** sales volume |
| Vehicles | `simulation/vehicles.csv` | **Generated** (Olist has no vehicle data at all) |
| Disruptions | `simulation/disruptions.csv` | **Generated** (anchored to **real** places/warehouses) |
| Delivery routes | `simulation/delivery_routes.csv` | **Computed** from **real** coordinates (distance/time/cost) |

> The real Olist data in `data/` and the cleaned data in `processed/` are the
> trusted foundation. Everything in `simulation/` is the operational layer we
> add on top, and every generated field is flagged in code comments.

---

## Data flow: from Olist to the simulation files

```
   data/ (raw Olist, READ-ONLY)
        │  Week 1 cleaning + joins
        ▼
   processed/ (cleaned CSVs + orders_master_table.csv)
        │
        │  Week 2 generation scripts (notebooks/week2_*.py)
        ▼
   simulation/
     warehouses.csv      ← sellers_clean + geolocation_zip_lookup + real volume
        │
        ├── inventory.csv       ← warehouses + order_items (demand) + products
        ├── vehicles.csv        ← warehouses (one fleet per warehouse)
        ├── disruptions.csv     ← warehouses (real cities/states to anchor events)
        └── delivery_routes.csv ← warehouses + orders_master_table (coordinates)
```

`warehouses.csv` is generated **first** because every other Week 2 file
references `warehouse_id`.

---

## How each dataset is generated

### Warehouses — `notebooks/week2_generate_warehouses.py`

Olist **sellers** are treated as **warehouses / fulfillment origins** (the core
assumption from the logistics data model). Not every seller becomes a warehouse:
we keep the **top 150 sellers by real shipped volume**, which together cover
~53% of all shipped items — a realistic "main network" of busy hubs rather than
3,000 tiny ones.

- **Real fields:** `seller_id`, `warehouse_city`, `warehouse_state`,
  `warehouse_zip_code_prefix`, `latitude`, `longitude` (from the Week 1 zip →
  coordinate lookup).
- **Generated fields:**
  - `capacity` — package-slot capacity, sized from the warehouse's real shipped
    volume plus headroom (real warehouses are rarely 100% full).
  - `current_utilization` — fraction of capacity in use (0–1), drawn around ~65%.
  - `operating_status` — `active` (normal), `overloaded` (≥90% full), or
    `inactive` (a small random set temporarily offline).

### Inventory — `notebooks/week2_inventory_simulation.py`

Inventory is the **stock each warehouse holds for each product** — the link that
connects a product to a warehouse with a quantity. A warehouse stocks the
products its seller actually shipped, and **best-sellers get deeper stock**.

- **Real signal:** units actually sold per (warehouse, product) drives the
  numbers; the product category is real.
- **Generated fields:** `stock_level`, `reorder_threshold`, `reorder_quantity`,
  `last_restock_date`, and `inventory_status`.
- **Status rule** (reused later for stockout detection):
  - `out_of_stock` — `stock_level == 0`;
  - `low_stock` — `stock_level <= reorder_threshold` (time to reorder);
  - `healthy` — above the threshold.

### Vehicles — `notebooks/week2_vehicle_generation.py`

Olist has **no vehicle data whatsoever**, so the entire fleet is generated. Each
warehouse gets a small fleet (1–5 vehicles) sized by its capacity. Vehicle types
are `van`, `small_truck`, `medium_truck`, `large_truck`, each with a realistic
weight/package capacity, running cost, and average speed.

Capacity matters because later route planning must not overload a vehicle;
availability (`available` / `on_delivery` / `maintenance`) is a hard constraint
on what can be scheduled right now.

### Disruptions — `notebooks/week2_disruption_generation.py`

Because Olist is historical, it has no live traffic or weather. We generate ~80
disruption events of types `heavy_traffic`, `severe_weather`,
`warehouse_overload`, `inventory_shortage`, and `road_closure`. Each has a
`severity` (low/medium/high/critical), a real city/state (and an affected
warehouse where relevant), a start/end time, an estimated delay in minutes, and
a `status` (active/resolved/scheduled). These become the scenarios the later
optimization and agent layers must re-plan around.

### Delivery routes — `notebooks/week2_route_generation.py`

A route is the journey **warehouse → customer**. We collapse the master table to
one row per **(order, warehouse) shipment leg** and compute, from the real
coordinates:

- `estimated_distance_km` — **haversine** (great-circle) distance, nudged by a
  road-winding factor toward plausible road distance;
- `estimated_time_minutes` — distance ÷ a representative average speed;
- `estimated_cost` — distance × a representative freight rate.

`route_status` is derived from the real order status (`delivered` → `completed`,
`shipped` → `in_transit`, else `planned`). A reproducible sample of 10,000 legs
is kept so the file stays light.

> This is a **simple estimate only**. There is **no OR-Tools optimization** in
> Week 2 — no best-vehicle selection, no multi-stop combining, no disruption
> avoidance. This dataset is the input the optimizer will improve later.

---

## How geolocation is used

Every warehouse and every customer is placed on the map using the Week 1
**zip-prefix → (latitude, longitude)** lookup (one representative median point
per zip prefix). The distance between two such points is the haversine distance.
Both the point (an area centroid) and the straight-line distance are
**approximations**, suitable for city-scale estimation and intentionally
improved by real road-network routing in a later week.

---

## What is real vs. simulated (summary)

- **Real, from Olist:** warehouse locations, which products each warehouse ships
  and how much, order/customer identities, source & destination coordinates,
  order status.
- **Generated / computed in Week 2:** warehouse capacity & utilization & status,
  all inventory numbers, the entire vehicle fleet, all disruptions, and the
  distance/time/cost estimates on routes.

---

## Reproducibility

Every script sets a **fixed random seed (42)** and anchors simulated dates to a
fixed "present" (`2018-11-01`, just after the Olist window ends). Re-running any
script produces the **identical** output. Scripts only **read** from `data/` and
`processed/` and only **write** to `simulation/`; the raw data is never modified.

---

## Where this leads

- **Week 3** — use `warehouses`, `vehicles`, and route coordinates to run real
  route optimization (OR-Tools), replacing the simple distance estimates.
- **Week 4** — load these simulation files into the planned PostgreSQL tables.
- **Week 5** — agents reason over inventory, vehicles, and disruptions.
- **Week 7** — disruptions trigger re-routing and re-stocking decisions.
- **Week 8** — visualize warehouses, routes, and disruptions on a dashboard.
