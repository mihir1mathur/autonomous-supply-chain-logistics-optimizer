"""
api/schemas/ package  (Week 4)
Project: Supply Chain & Logistics Optimizer

WHAT LIVES HERE: the PYDANTIC SCHEMAS - the "shape" of the JSON that goes into
and comes out of the API. One file per entity, matching the Week 3 models:

  customer.py   warehouse.py   inventory.py   vehicle.py
  route.py      disruption.py  order.py

SQLAlchemy MODEL vs. PYDANTIC SCHEMA (the key beginner distinction)
------------------------------------------------------------------
  - A SQLAlchemy MODEL (models/*.py, Week 3) describes a DATABASE TABLE: what
    is stored on disk, the columns, keys, and relationships.
  - A PYDANTIC SCHEMA (here) describes the JSON at the API BOUNDARY: what a
    caller may SEND and what they RECEIVE. It validates incoming data and
    controls exactly which fields are exposed on the way out.
  They are deliberately separate: the database shape and the public API shape
  can evolve independently, and the schema can hide/rename/validate fields
  without touching the table.

FOUR SCHEMAS PER ENTITY (the pattern every file follows)
--------------------------------------------------------
  <Entity>Base     - the shared fields + validation rules (the "validation
                     schema"). Create and Update reuse it.
  <Entity>Create   - the REQUEST body for POST (create). Required fields.
  <Entity>Update   - the REQUEST body for PUT/PATCH. Every field optional, so a
                     caller can send only what they want to change.
  <Entity>Response - the RESPONSE body. Includes the id and reads straight from
                     a SQLAlchemy model instance (from_attributes=True).
"""

from api.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from api.schemas.warehouse import WarehouseCreate, WarehouseResponse, WarehouseUpdate
from api.schemas.inventory import InventoryCreate, InventoryResponse, InventoryUpdate
from api.schemas.vehicle import VehicleCreate, VehicleResponse, VehicleUpdate
from api.schemas.route import RouteCreate, RouteResponse, RouteUpdate
from api.schemas.disruption import DisruptionCreate, DisruptionResponse, DisruptionUpdate
from api.schemas.order import OrderCreate, OrderResponse, OrderUpdate

__all__ = [
    "CustomerCreate", "CustomerResponse", "CustomerUpdate",
    "WarehouseCreate", "WarehouseResponse", "WarehouseUpdate",
    "InventoryCreate", "InventoryResponse", "InventoryUpdate",
    "VehicleCreate", "VehicleResponse", "VehicleUpdate",
    "RouteCreate", "RouteResponse", "RouteUpdate",
    "DisruptionCreate", "DisruptionResponse", "DisruptionUpdate",
    "OrderCreate", "OrderResponse", "OrderUpdate",
]
