# Logistics Data Model

This document explains how the **Olist e-commerce dataset** is reinterpreted
as a **logistics dataset** for the Supply Chain & Logistics Optimizer.

It builds directly on the dataset described in
[`dataset_overview.md`](dataset_overview.md). Where that document explains
*what the data is*, this one explains *what each part means for logistics* and,
importantly, **where we are making modeling assumptions** — because Olist was
built to record online sales, not to run a logistics operation.

---

## Why a "data model"?

A **data model** is simply a clear statement of *what each thing in our system
represents and how the things relate*. Before we simulate inventory (Week 2) or
optimize routes (Week 3), we must agree on what a "warehouse", a "shipment", or
a "destination" actually maps to in the raw data. This document is that
agreement.

---

## The core mapping

| Olist concept | Logistics role | Source columns (after Week 1 cleaning) |
|---------------|----------------|----------------------------------------|
| Customer | **Delivery destination** | `customer_city`, `customer_state`, `customer_zip_code_prefix`, `customer_lat`, `customer_lng` |
| Seller | **Warehouse / fulfillment origin** | `seller_city`, `seller_state`, `seller_zip_code_prefix`, `seller_lat`, `seller_lng` |
| Product | **Inventory item** | `product_id`, `product_category_name_english`, `product_weight_g`, dimensions |
| Order | **Shipment request** | `order_id`, `order_status`, `order_purchase_timestamp` |
| Delivery dates | **Delay analysis** | `order_delivered_customer_date` vs `order_estimated_delivery_date` |
| Geolocation | **Routing input** | `*_lat`, `*_lng` derived from the zip → coordinate lookup |

```
   OLIST (sales data)            LOGISTICS MODEL (this project)
   ------------------            ------------------------------
        customer        =====>   delivery DESTINATION
        seller          =====>   WAREHOUSE / origin
        product         =====>   INVENTORY ITEM
        order           =====>   SHIPMENT REQUEST
        delivery dates  =====>   DELAY analysis
        geolocation     =====>   DISTANCE & ROUTE
```

---

## Each mapping, and why it is reasonable

### Customer → Delivery Destination
**Why reasonable:** every order has exactly one customer, and that customer has
a location (city, state, zip prefix → coordinates). In logistics, the point a
package must reach is the destination. This is a near-perfect, low-assumption
mapping.

**Assumption made:** we use the **zip-code prefix** (an area), not a precise
street address (Olist anonymizes the full address). So a "destination" is an
*area centroid*, not an exact doorstep. Good enough for distance and routing at
city scale; not for literal last-meter navigation.

### Seller → Warehouse / Fulfillment Origin
**Why reasonable:** the product physically ships *from* the seller's location,
which is exactly what a warehouse/fulfillment center is — the origin of a
shipment.

**Assumption made (largest one):** Olist has **no real warehouse data** — no
buildings, no capacity, no stock. We *treat each seller as a single-location
warehouse*. This is a modeling choice. Real fulfillment networks have multiple
warehouses, cross-docking, and capacity limits; we approximate each seller as
one origin point. Inventory and capacity for these "warehouses" are
**simulated** later (Week 2 / Week 7), not taken from the data.

### Product → Inventory Item
**Why reasonable:** a product has a category, a weight, and dimensions — exactly
the attributes a warehouse tracks for an item it stores and ships.

**Assumption made:** the dataset records product *attributes* but **not stock
levels** (how many units are on hand). "Inventory item" therefore means "a thing
that *can* be stocked"; the actual quantity-on-hand is **simulated** in Week 2.
Also, 2 products lack weight/dimensions and 610 lacked a category (filled as
`unknown` during cleaning) — minor gaps to keep in mind.

### Order → Shipment Request
**Why reasonable:** an order says "this customer wants these items" — which, in
logistics terms, is a request to move goods from origin(s) to a destination.

**Assumption made:** one Olist order can contain items from **multiple sellers**,
which really means multiple origin points for a single order. In a strict
logistics sense that is several shipments. For modeling we treat each
**order-item line** as the unit of movement (origin = its seller, destination =
the order's customer). This is why the Week 1 master table is at *item* grain,
not *order* grain.

### Delivery Dates → Delay Analysis
**Why reasonable:** the dataset records both the **promised** date
(`order_estimated_delivery_date`) and the **actual** delivery date
(`order_delivered_customer_date`). Comparing them gives a real, ground-truth
measure of lateness — the single most valuable logistics signal in the data.

**Assumption made:** delivery dates are **missing** for orders that were never
delivered (≈3% — canceled/unavailable). Delay analysis applies only to delivered
orders; the missing ones are themselves a useful signal (non-completion), not an
error to delete.

### Geolocation → Routing
**Why reasonable:** routing needs coordinates, not city names. The geolocation
file converts a zip prefix into latitude/longitude, giving us origin and
destination points to measure distance between.

**Assumption made:** one zip prefix maps to **many** raw coordinate rows, so we
reduce each prefix to a **single representative point** (median lat/lng during
cleaning). A "location" is therefore an approximate area center. Straight-line
(haversine) distance — used from Week 3 — is also an approximation of true road
distance.

---

## Grain of the combined table

After the Week 1 joins (`week1_dataset_joins.py`), the master table is at the
**order-item grain**: one row = *one product line within one order*, enriched
with its origin (seller), destination (customer), product attributes, costs, and
delivery timestamps.

> This matters: an order with three items becomes three rows. Any per-*order*
> metric (e.g. "number of orders delivered late") must aggregate back up by
> `order_id` to avoid double-counting.

---

## What is real vs. modeled (summary)

| Element | Real (in Olist) | Modeled / assumed | Simulated later |
|---------|:--------------:|:-----------------:|:---------------:|
| Destinations (customers) | ✅ | zip-prefix centroid | — |
| Origins (sellers) | ✅ (location only) | "seller = warehouse" | capacity, count |
| Product attributes | ✅ | — | — |
| Inventory / stock levels | — | — | ✅ Week 2 |
| Shipment requests (orders) | ✅ | item-grain movement | — |
| Delivery delays | ✅ | — | — |
| Coordinates / distance | ✅ (zip lookup) | area centroid, straight-line | road distance later |
| Traffic / weather / congestion | — | — | ✅ Week 7 |

---

## Where this leads

This model is the contract the rest of the project is built on:

- **Week 2** — simulate inventory for the "warehouse" sellers.
- **Week 3** — use origin/destination coordinates for route optimization.
- **Week 4** — turn these mapped entities into database tables
  (see [`future_database_design.md`](future_database_design.md)).
- **Week 7** — layer simulated disruptions onto routes.
- **Week 8** — visualize destinations, origins, routes, and delays.

Being explicit about the assumptions now means later weeks can trust — and, where
needed, improve — the foundation rather than rediscovering its limits.
