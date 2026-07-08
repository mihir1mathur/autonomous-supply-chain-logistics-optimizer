# Supply Chain & Logistics Optimizer — Dataset Overview

## Project

**Supply Chain & Logistics Optimizer** is a project that uses real e-commerce
order data to study and improve how products move from sellers to customers —
analyzing delivery performance, estimating routes and distances, and (in later
stages) simulating disruptions and optimizing logistics decisions.

This document explains the dataset we build on, what each file contains, how
the files connect to one another, and how each piece maps to supply chain and
logistics concepts.

## Dataset Source

**Brazilian E-Commerce Public Dataset by Olist**

Olist is a Brazilian e-commerce platform that connects small sellers to large
marketplaces. This public dataset contains roughly 100,000 real orders placed
between 2016 and 2018, including the customers, sellers, products, payments,
reviews, delivery timestamps, and geographic locations involved.

The dataset is anonymized: all real names and identifiers have been replaced
with random codes.

## Dataset Files

| # | File | What it holds |
|---|------|---------------|
| 1 | `olist_customers_dataset.csv` | Who placed each order and where they are |
| 2 | `olist_geolocation_dataset.csv` | Map coordinates (latitude/longitude) for zip codes |
| 3 | `olist_order_items_dataset.csv` | The individual products inside each order |
| 4 | `olist_order_payments_dataset.csv` | How each order was paid for |
| 5 | `olist_order_reviews_dataset.csv` | Customer ratings and review comments |
| 6 | `olist_orders_dataset.csv` | The orders themselves, with status and dates |
| 7 | `olist_products_dataset.csv` | Product details (category, size, weight) |
| 8 | `olist_sellers_dataset.csv` | Who sold the products and where they are |
| 9 | `product_category_name_translation.csv` | Portuguese → English category names |

---

## File-by-File Explanation

### 1. `olist_customers_dataset.csv`
The people who place orders, and roughly where they live.

| Column | Meaning |
|--------|---------|
| `customer_id` | A code unique to one order's customer record (links to orders) |
| `customer_unique_id` | A code that identifies the same real person across orders |
| `customer_zip_code_prefix` | First digits of the customer's zip code (their area) |
| `customer_city` | City the customer is in |
| `customer_state` | State the customer is in (e.g. `SP` = São Paulo) |

> Note: `customer_id` is per-order, while `customer_unique_id` is per-person.
> A single person can appear with several `customer_id`s if they ordered more
> than once.

### 2. `olist_geolocation_dataset.csv`
A lookup table that turns a zip-code area into actual map coordinates.

| Column | Meaning |
|--------|---------|
| `geolocation_zip_code_prefix` | First digits of a zip code |
| `geolocation_lat` | Latitude (how far north/south on the map) |
| `geolocation_lng` | Longitude (how far east/west on the map) |
| `geolocation_city` | City for that zip prefix |
| `geolocation_state` | State for that zip prefix |

> This file lets us estimate **distance** between a seller and a customer,
> which is the foundation of route and delivery analysis.

### 3. `olist_order_items_dataset.csv`
One row per product inside an order. An order with 3 products has 3 rows here.

| Column | Meaning |
|--------|---------|
| `order_id` | Which order this item belongs to |
| `order_item_id` | Item number within the order (1, 2, 3, ...) |
| `product_id` | Which product was bought |
| `seller_id` | Which seller is shipping this product |
| `shipping_limit_date` | Deadline by which the seller must hand the item to the carrier |
| `price` | Price of the item |
| `freight_value` | Shipping/delivery cost charged for the item |

### 4. `olist_order_payments_dataset.csv`
How each order was paid.

| Column | Meaning |
|--------|---------|
| `order_id` | Which order this payment is for |
| `payment_sequential` | Order of payments if more than one method was used |
| `payment_type` | Method (e.g. `credit_card`, `boleto`, `voucher`) |
| `payment_installments` | Number of installments the buyer chose |
| `payment_value` | Amount paid |

### 5. `olist_order_reviews_dataset.csv`
Customer feedback after delivery.

| Column | Meaning |
|--------|---------|
| `review_id` | Code for the review |
| `order_id` | Which order is being reviewed |
| `review_score` | Rating from 1 (worst) to 5 (best) |
| `review_comment_title` | Optional short title |
| `review_comment_message` | Optional written feedback |
| `review_creation_date` | When the review survey was sent |
| `review_answer_timestamp` | When the customer answered it |

> Reviews often correlate with delivery experience: late deliveries tend to
> receive lower scores. This connects logistics performance to satisfaction.

### 6. `olist_orders_dataset.csv`
The heart of the dataset — one row per order, with its status and key dates.

| Column | Meaning |
|--------|---------|
| `order_id` | Unique code for the order |
| `customer_id` | Which customer placed it |
| `order_status` | Current state (e.g. `delivered`, `shipped`, `canceled`) |
| `order_purchase_timestamp` | When the order was placed |
| `order_approved_at` | When payment was approved |
| `order_delivered_carrier_date` | When the seller handed it to the carrier |
| `order_delivered_customer_date` | When the customer actually received it |
| `order_estimated_delivery_date` | The date the customer was promised |

> Comparing `order_delivered_customer_date` with
> `order_estimated_delivery_date` tells us whether a delivery was **on time or
> late** — the core of delay analysis.

### 7. `olist_products_dataset.csv`
Details about each product.

| Column | Meaning |
|--------|---------|
| `product_id` | Unique code for the product |
| `product_category_name` | Category in Portuguese |
| `product_name_lenght` | Number of characters in the product name |
| `product_description_lenght` | Number of characters in the description |
| `product_photos_qty` | Number of photos in the listing |
| `product_weight_g` | Weight in grams |
| `product_length_cm` | Length in centimeters |
| `product_height_cm` | Height in centimeters |
| `product_width_cm` | Width in centimeters |

> Weight and dimensions matter for logistics: they affect shipping cost,
> packing, and how much fits on a vehicle.

### 8. `olist_sellers_dataset.csv`
The businesses that fulfill and ship products.

| Column | Meaning |
|--------|---------|
| `seller_id` | Unique code for the seller |
| `seller_zip_code_prefix` | First digits of the seller's zip code |
| `seller_city` | City the seller ships from |
| `seller_state` | State the seller ships from |

### 9. `product_category_name_translation.csv`
A small lookup that translates category names.

| Column | Meaning |
|--------|---------|
| `product_category_name` | Category name in Portuguese |
| `product_category_name_english` | Same category in English |

---

## How the Files Connect (Relationships)

Each file is a table. Tables connect through shared **ID columns** (a value in
one table that points to a row in another table). The diagram below shows how
a single order ties everything together.

```
                    olist_customers_dataset
                              ▲
                              | customer_id
                              |
   olist_orders_dataset  ─────┘
        |  order_id
        |
        ├──────────────► olist_order_payments_dataset   (order_id)
        |
        ├──────────────► olist_order_reviews_dataset    (order_id)
        |
        └──────────────► olist_order_items_dataset      (order_id)
                                |          |
                      product_id|          | seller_id
                                ▼          ▼
                  olist_products      olist_sellers
                       |
       product_category_name
                       ▼
        product_category_name_translation

   olist_geolocation_dataset connects to BOTH customers and sellers
   through the zip code prefix (links a location to lat/long coordinates).
```

In plain words:

- **Orders connect to customers** — every order has a `customer_id`.
- **Orders connect to order items** — every order has one or more items
  (linked by `order_id`).
- **Order items connect to sellers** — each item has a `seller_id`.
- **Order items connect to products** — each item has a `product_id`.
- **Products connect to product categories** — via
  `product_category_name`, translated to English in the translation file.
- **Customers connect to customer locations** — the customer's zip prefix
  maps to coordinates in the geolocation file.
- **Sellers connect to seller locations** — the seller's zip prefix maps to
  coordinates in the geolocation file.

---

## Supply Chain Mapping

This is an e-commerce dataset, but it contains everything we need to treat it
as a **logistics** dataset. Here is how each part maps to supply chain ideas:

| Dataset concept | Supply chain / logistics role |
|-----------------|-------------------------------|
| Customer | **Delivery destination** — where a package must arrive |
| Seller | **Warehouse / fulfillment location** — where goods ship from |
| Order | **Customer purchase / shipment request** |
| Product | **Inventory item** — a thing that is stored and shipped |
| Delivery timestamps & estimated date | **Delay analysis** — on time vs. late |
| Geolocation (lat/long) | **Distance & route estimation** between origin and destination |
| Freight value | **Shipping cost** to move the item |
| Product weight & dimensions | **Capacity & packing** constraints |
| Review score | **Customer impact** of logistics performance |

---

## Real Data vs. Simulated Data

The Olist dataset is real and rich, but it does not contain *everything* a
full logistics optimization system needs. We will clearly separate what is
**real** from what we will **simulate** in later stages.

### Real (already in the dataset)
- Orders and their status
- Customers and their locations
- Sellers and their locations
- Products (category, weight, dimensions)
- Payments
- Reviews
- Delivery timestamps (purchase, carrier handoff, delivery, estimate)
- Geolocation coordinates

### Simulated later (not in the dataset)
- Warehouse inventory levels (how much stock is on hand)
- Stock shortages / out-of-stock events
- Traffic disruptions
- Weather disruptions
- Route congestion
- Warehouse overload
- Replanning / rerouting decisions

> We simulate these because the historical dataset records *what happened*, not
> the live operational conditions (inventory, traffic, weather) that a real
> logistics system would react to. Simulation lets us model those conditions
> on top of the real data so the optimizer has something realistic to plan
> against.

---

## Status

This document reflects **Week 0** — business and dataset understanding. The
original CSV files are kept unchanged; this project only reads from them.
