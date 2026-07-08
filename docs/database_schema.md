# Database Schema Reference (Week 3)

The exact tables, columns, keys, and indexes created by the Week 3 models. For
the reasoning behind these choices, see [`database_design.md`](database_design.md).

- **PK** = primary key · **FK** = foreign key · **IDX** = indexed column.
- Types are the logical types the SQLAlchemy models declare (PostgreSQL stores
  them as `VARCHAR`, `INTEGER`, `DOUBLE PRECISION`, `DATE`, `TIMESTAMP`, `TEXT`).
- **Source** notes whether the data is real Olist data, simulated (Week 2), or
  computed.

There are **9 tables**. They are created by `database/init_db.py` from the
models in `models/`, and loaded from CSV by `notebooks/week3_load_database.py`.

---

## Table overview

| Table | Rows (approx.) | Source | Loaded from |
|-------|---------------:|--------|-------------|
| `customers` | 99,441 | Real | `processed/customers_clean.csv` |
| `sellers` | 3,095 | Real | `processed/sellers_clean.csv` |
| `products` | 32,951 | Real | `processed/products_clean.csv` |
| `orders` | 99,441 | Real | `processed/orders_clean.csv` |
| `warehouses` | 150 | Real location + simulated ops | `simulation/warehouses.csv` |
| `inventory` | 12,362 | Simulated (real demand signal) | `simulation/inventory.csv` |
| `vehicles` | 209 | Simulated | `simulation/vehicles.csv` |
| `delivery_routes` | 10,000 | Real ids + computed estimates | `simulation/delivery_routes.csv` |
| `disruptions` | 80 | Simulated | `simulation/disruptions.csv` |

---

## `customers` — delivery destinations (real)

| Column | Type | Key / Index | Notes |
|--------|------|-------------|-------|
| `customer_id` | String | **PK** | one record per order in Olist |
| `customer_unique_id` | String | IDX | links the same real person across orders |
| `customer_zip_code_prefix` | Integer | IDX | destination location |
| `customer_city` | String | | |
| `customer_state` | String | IDX | filtered by region |

**Relationships:** one customer → many `orders`, many `delivery_routes`.

## `sellers` — original fulfillment sources (real)

| Column | Type | Key / Index | Notes |
|--------|------|-------------|-------|
| `seller_id` | String | **PK** | real Olist seller id |
| `seller_zip_code_prefix` | Integer | IDX | |
| `seller_city` | String | | |
| `seller_state` | String | IDX | |

**Relationships:** one seller → zero or one `warehouse` (the top 150 sellers
were promoted to warehouses in Week 2).

## `products` — inventory item catalog (real)

| Column | Type | Key / Index | Notes |
|--------|------|-------------|-------|
| `product_id` | String | **PK** | |
| `product_category_name` | String | IDX | Portuguese (original) |
| `product_category_name_english` | String | IDX | added in Week 1 |
| `product_name_length` | Integer | nullable | |
| `product_description_length` | Integer | nullable | |
| `product_photos_qty` | Integer | nullable | |
| `product_weight_g` | Float | nullable | freight / capacity later |
| `product_length_cm` | Float | nullable | |
| `product_height_cm` | Float | nullable | |
| `product_width_cm` | Float | nullable | |

**Relationships:** one product → many `inventory` rows (one per warehouse).

## `orders` — shipment requests (real)

| Column | Type | Key / Index | Notes |
|--------|------|-------------|-------|
| `order_id` | String | **PK** | |
| `customer_id` | String | **FK → customers**, IDX | |
| `order_status` | String | IDX | delivered / shipped / canceled / … |
| `order_purchase_timestamp` | DateTime | nullable | delivery-timeline fields |
| `order_approved_at` | DateTime | nullable | |
| `order_delivered_carrier_date` | DateTime | nullable | |
| `order_delivered_customer_date` | DateTime | nullable | |
| `order_estimated_delivery_date` | DateTime | nullable | |

**Relationships:** one order → one `customer`, many `delivery_routes`.
NULL timestamps are meaningful (e.g. never delivered).

## `warehouses` — fulfillment origins (real location + simulated ops)

| Column | Type | Key / Index | Notes |
|--------|------|-------------|-------|
| `warehouse_id` | String | **PK** | e.g. `WH-0001` |
| `seller_id` | String | **FK → sellers**, IDX | the seller it maps from (real) |
| `warehouse_city` | String | | real |
| `warehouse_state` | String | IDX | real |
| `warehouse_zip_code_prefix` | Integer | | real |
| `latitude` | Float | | real (route origin) |
| `longitude` | Float | | real |
| `capacity` | Integer | | **simulated** — package-slot capacity |
| `current_utilization` | Float | | **simulated** — 0..1 fraction in use |
| `operating_status` | String | IDX | **simulated** — active / overloaded / inactive |

**Relationships:** one warehouse → many `inventory`, `vehicles`,
`delivery_routes`, `disruptions`; belongs to one `seller`.

## `inventory` — stock per (warehouse, product) (simulated)

| Column | Type | Key / Index | Notes |
|--------|------|-------------|-------|
| `inventory_id` | String | **PK** | e.g. `INV-000001` |
| `warehouse_id` | String | **FK → warehouses**, IDX | |
| `product_id` | String | **FK → products**, IDX | |
| `product_category_name` | String | | denormalized copy for quick filtering |
| `stock_level` | Integer | | units on hand |
| `reorder_threshold` | Integer | | reorder at/below this |
| `reorder_quantity` | Integer | | units per restock |
| `last_restock_date` | Date | nullable | |
| `inventory_status` | String | IDX | healthy / low_stock / out_of_stock |

**Bridge table** between products and warehouses.
**Status rule:** `out_of_stock` if `stock_level == 0`; `low_stock` if
`stock_level <= reorder_threshold`; otherwise `healthy`.

## `vehicles` — delivery fleet (simulated)

| Column | Type | Key / Index | Notes |
|--------|------|-------------|-------|
| `vehicle_id` | String | **PK** | e.g. `VEH-00001` |
| `warehouse_id` | String | **FK → warehouses**, IDX | home warehouse |
| `vehicle_type` | String | IDX | van / small_truck / medium_truck / large_truck |
| `capacity_kg` | Integer | | hard limit for planning |
| `capacity_packages` | Integer | | |
| `current_location_city` | String | | starts at home warehouse |
| `current_location_state` | String | | |
| `availability_status` | String | IDX | available / on_delivery / maintenance |
| `cost_per_km` | Float | | feeds route cost |
| `average_speed_kmph` | Integer | | feeds route time |

**Relationships:** belongs to one `warehouse`; one vehicle → many
`delivery_routes` (assigned later by the optimizer).

## `delivery_routes` — warehouse → customer trips (real ids + computed)

| Column | Type | Key / Index | Notes |
|--------|------|-------------|-------|
| `route_id` | String | **PK** | e.g. `RT-000001` |
| `order_id` | String | **FK → orders**, IDX | |
| `warehouse_id` | String | **FK → warehouses**, IDX | |
| `customer_id` | String | **FK → customers**, IDX | |
| `vehicle_id` | String | **FK → vehicles**, IDX, nullable | reserved for OR-Tools; NULL now |
| `source_city` / `source_state` | String | | denormalized origin |
| `destination_city` / `destination_state` | String | | denormalized destination |
| `source_latitude` / `source_longitude` | Float | | |
| `destination_latitude` / `destination_longitude` | Float | | |
| `estimated_distance_km` | Float | | **computed** (haversine × 1.30) |
| `estimated_time_minutes` | Float | | **computed** |
| `estimated_cost` | Float | | **computed** |
| `route_status` | String | IDX | planned / in_transit / completed |

**Relationships:** ties one `order`, one `warehouse`, one `customer`, and an
optional `vehicle`; can be pointed at by `disruptions`.

## `disruptions` — delaying events (simulated)

| Column | Type | Key / Index | Notes |
|--------|------|-------------|-------|
| `disruption_id` | String | **PK** | e.g. `DIS-0001` |
| `disruption_type` | String | IDX | heavy_traffic / severe_weather / warehouse_overload / inventory_shortage / road_closure |
| `severity` | String | IDX | low / medium / high / critical |
| `location_city` | String | | real place name |
| `location_state` | String | IDX | |
| `affected_warehouse_id` | String | **FK → warehouses**, IDX, nullable | NULL for area-wide events |
| `affected_route_id` | String | **FK → delivery_routes**, IDX, nullable | reserved for Week 7 replanning; NULL now |
| `start_time` | DateTime | nullable | |
| `end_time` | DateTime | nullable | |
| `impact_description` | Text | | |
| `estimated_delay_minutes` | Integer | | |
| `status` | String | IDX | active / resolved / scheduled |

**Relationships:** may reference a `warehouse` and/or a `delivery_route`.

---

## Reserved for the future (not built this week)

- **`delivery_routes.vehicle_id`** and **`disruptions.affected_route_id`** exist
  and are indexed but stay `NULL` — they let OR-Tools (vehicle assignment) and
  Week 7 (disruption-driven replanning) attach data with no schema change.
- **`agent_decisions`** — a planned audit table (Week 5, CrewAI) recording what
  each agent decided and why, referencing the order/route/inventory it acted on.
  It is documented here so its future foreign keys are anticipated, but it is
  **not** created yet.

---

## How the schema is created and loaded

```
# 1. one-time: create the database
createdb supply_chain_optimizer

# 2. create all tables, indexes, and foreign keys from the models
python database/init_db.py

# 3. load the Week 1 + Week 2 CSVs into the tables (read-only on the CSVs)
python notebooks/week3_load_database.py

# 4. verify every CRUD function against the loaded data
python notebooks/week3_test_crud.py
```

The loader inserts in batches with `INSERT ... ON CONFLICT DO NOTHING`, so it is
safe to re-run, reports CSV-vs-database row counts, and checks for orphan
foreign keys before loading each child table.
