# Simulation Assumptions

This document lists **every modeling assumption** behind the Week 2 simulated
logistics datasets. It is the companion to
[`logistics_simulation.md`](logistics_simulation.md) (which explains *how* the
data is generated) and extends the assumptions already recorded in
[`logistics_data_model.md`](logistics_data_model.md).

The guiding principle: **be explicit about the boundary between real Olist data
and invented values**, so later weeks can trust the solid parts and improve the
approximate ones.

---

## Global assumptions

- **Reproducibility.** Every script uses a fixed random seed (`42`). Re-running
  produces identical files.
- **Fixed "present".** The Olist data ends on `2018-10-17`. All simulated dates
  are anchored to `2018-11-01` (a fixed point just after that window). We never
  use the real system clock, so results stay reproducible.
- **Read-only raw data.** Scripts only read from `data/` and `processed/`, and
  only write to `simulation/`. Raw Olist files are never modified.
- **Generated values are flagged.** In every script, each output column is
  commented as REAL (from Olist), SIMULATED (invented), or COMPUTED (derived
  from real values).

---

## 1. Warehouses (`simulation/warehouses.csv`)

| Assumption | Detail |
|------------|--------|
| Sellers are warehouses | Each Olist **seller** is treated as a single-location warehouse / fulfillment origin (carried over from the logistics data model — the project's biggest modeling assumption). |
| Subset of sellers | Only the **top 150 sellers by real shipped volume** become warehouses (≈53% of all shipped items). Real networks have a handful of busy hubs, not thousands. |
| Coordinates required | A seller with no matching zip → coordinate point is excluded (a warehouse with no location is useless for routing). |
| `capacity` is simulated | Olist has no warehouse size. Capacity (in package slots) is sized from the warehouse's **real** shipped volume × a headroom factor of 1.4–2.2, floored at 500. |
| `current_utilization` is simulated | Drawn from a normal distribution centred at ~0.65, clipped to 0.25–0.99. |
| `operating_status` is simulated | `overloaded` if utilization ≥ 0.90; ~5% randomly `inactive`; otherwise `active`. |

---

## 2. Inventory (`simulation/inventory.csv`)

| Assumption | Detail |
|------------|--------|
| Inventory must be simulated | Olist records **sales**, not **stock on hand**. There is no stock column anywhere in the data. |
| One row per (warehouse, product) | A warehouse stocks the products its seller actually shipped; each such pairing is one inventory record. |
| Stock scales with demand | The target "full shelf" level = real units sold × a random 2.0–6.0 multiplier (floored at 10 units), so best-sellers carry deeper stock. |
| `reorder_threshold` < stock target | Set to ~20–40% of the target shelf (floored at 5) — the low-water mark that triggers a reorder. |
| `reorder_quantity` | ~0.8–1.2× the target shelf (floored at 10) — how much is brought in per restock. |
| Current `stock_level` snapshot | Drawn as a random 0–1.1× fraction of target, so the snapshot contains healthy, low, and out-of-stock items. |
| `inventory_status` is derived | `out_of_stock` if stock is 0; `low_stock` if stock ≤ reorder threshold; else `healthy`. This rule is reused later for stockout detection. |
| `last_restock_date` is simulated | A random 0–90 days before the fixed "present" date. |

---

## 3. Vehicles (`simulation/vehicles.csv`)

| Assumption | Detail |
|------------|--------|
| Entire fleet is simulated | Olist has **no carrier or vehicle data at all**. Every vehicle field is invented. |
| Fleet size by capacity | Each warehouse gets 1–5 vehicles, tiered by its (simulated) capacity. |
| Vehicle types | `van`, `small_truck`, `medium_truck`, `large_truck`, with documented capacity (kg + packages), cost per km, and average speed. Bigger warehouses skew toward bigger vehicles. |
| Per-vehicle jitter | Capacities, cost, and speed get a small ±5–10% random jitter so same-type vehicles are not identical clones. |
| Vehicles start at home | Each vehicle's current location is its home warehouse's city/state. |
| `availability_status` is simulated | `available` (60%), `on_delivery` (32%), or `maintenance` (8%) — a hard constraint on what can be scheduled. |

---

## 4. Disruptions (`simulation/disruptions.csv`)

| Assumption | Detail |
|------------|--------|
| Disruptions must be simulated | Olist is **historical**; it has no live traffic, weather, or road conditions. |
| Count | ~80 events — enough for interesting scenarios without overwhelming the later planner. |
| Types | `heavy_traffic`, `severe_weather`, `warehouse_overload`, `inventory_shortage`, `road_closure`. |
| Location is real | Each event is placed in a real warehouse's city/state. `warehouse_overload` and `inventory_shortage` name a specific `affected_warehouse_id`; area events (traffic/weather/road) leave it blank. |
| `severity` | `low`/`medium`/`high`/`critical`, weighted toward minor events (few critical). |
| `estimated_delay_minutes` | Sampled from a severity-based range (low: 10–45, medium: 45–120, high: 120–300, critical: 300–720). |
| Timing | Start time within ±30 days of the fixed "present"; duration ~1.0–2.5× the delay impact. |
| `status` | `active` (45%), `resolved` (40%), or `scheduled` (15%). |

---

## 5. Delivery routes (`simulation/delivery_routes.csv`)

| Assumption | Detail |
|------------|--------|
| Route grain | One row per **(order, warehouse) shipment leg**; multiple items from the same seller in one order are a single journey. |
| Coordinates required | Legs missing either endpoint's coordinates are dropped. |
| Distance is approximate | `estimated_distance_km` = **haversine** (straight-line) distance × a **road-winding factor of 1.30** to approximate real road distance. |
| Time estimate | `estimated_time_minutes` = distance ÷ a representative blended speed of **50 km/h**. |
| Cost estimate | `estimated_cost` = distance × a representative freight rate of **1.20** generic cost units/km. |
| `route_status` is derived | From the real order status: `delivered` → `completed`, `shipped` → `in_transit`, else `planned`. |
| Sample, not full set | A reproducible sample of **10,000** legs (of ~52k) is kept to keep the file light; set `MAX_ROUTES = None` to generate all. |
| No optimization | These are **simple estimates**. No vehicle assignment, multi-stop combining, or disruption avoidance — that is OR-Tools' job in a later week. |

---

## Known limitations (to improve later)

- Locations are **zip-prefix centroids**, not exact addresses (Olist anonymizes
  addresses) — so distances are area-to-area, not door-to-door.
- Straight-line distance (even with the winding factor) is **not** real road
  distance; a routing engine will improve this in Week 3.
- Inventory, capacity, fleet, and disruptions are **plausible inventions**, not
  measured facts — they exist to make the system testable, not to predict
  Olist's real operations.
- The route estimate ignores vehicle assignment and current disruptions; both
  are deliberately deferred to later weeks.

Being explicit now means later weeks can rely on the real foundation and
sharpen the approximations with intent rather than rediscovering their limits.
