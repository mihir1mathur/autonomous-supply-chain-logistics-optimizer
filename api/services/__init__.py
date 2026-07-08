"""
api/services/ package  (Week 4)
Project: Supply Chain & Logistics Optimizer

WHAT LIVES HERE: the SERVICE LAYER - the business logic, one file per entity:

  customer_service.py   warehouse_service.py   inventory_service.py
  vehicle_service.py    route_service.py       order_service.py
  disruption_service.py

WHY A SERVICE LAYER EXISTS (and why routers must never skip it)
--------------------------------------------------------------
  A router's only job is to speak HTTP: read the request, hand off, return the
  answer. The actual WORK - looking things up, checking rules, writing to the
  database - lives here, in services. Two big payoffs:

    1. One place for each rule. e.g. "when stock changes, recompute
       inventory_status" lives ONLY in inventory_service. Every caller gets the
       rule for free and it can never be half-applied.
    2. The logic is reusable and swappable. Week 5 agents and a future
       dashboard can call these SAME service functions. Week 6 can add a Redis
       cache in front of a read here without touching a single router.

  Rule of thumb: routers are THIN (HTTP only), services are where thinking
  happens, and ONLY services talk to the database.

REUSE OF WEEK 3
---------------
  Services build on the Week 3 SQLAlchemy models and, where a suitable helper
  already exists, call database/crud.py directly (e.g. the inventory stock rule,
  active-disruption queries) instead of re-writing it.
"""
