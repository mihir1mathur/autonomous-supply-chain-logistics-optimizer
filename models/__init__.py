"""
models/ package  (Week 3)
Project: Supply Chain & Logistics Optimizer

This file imports EVERY model class so that simply doing `import models`
registers all tables on the shared Base.metadata. database/init_db.py relies
on that: once the models are imported, Base.metadata.create_all() knows about
every table.

Tables (and their source data):
    customers        <- processed/customers_clean.csv   (REAL)
    sellers          <- processed/sellers_clean.csv     (REAL)
    products         <- processed/products_clean.csv    (REAL)
    orders           <- processed/orders_clean.csv       (REAL)
    warehouses       <- simulation/warehouses.csv        (REAL location + SIM ops)
    inventory        <- simulation/inventory.csv         (SIM, real demand signal)
    vehicles         <- simulation/vehicles.csv          (SIM)
    delivery_routes  <- simulation/delivery_routes.csv   (REAL ids + COMPUTED)
    disruptions      <- simulation/disruptions.csv       (SIM)

WEEK 6 TABLE (added by the optimization execution layer):
    optimization_runs -- one row per stored optimization / scenario run, with
    its KPIs. Brand-new and additive: init_db.py's create_all() creates it
    without touching any Week 3 table. See models/optimization_run.py.

FUTURE TABLE (not created yet, planned for a later week):
    agent_decisions  -- an audit log of what the CrewAI agents decide and why.
    See docs/database_schema.md for its planned design.
"""

from database.connection import Base

from models.customer import Customer
from models.seller import Seller
from models.product import Product
from models.order import Order
from models.warehouse import Warehouse
from models.inventory import Inventory
from models.vehicle import Vehicle
from models.route import DeliveryRoute
from models.disruption import Disruption
from models.optimization_run import OptimizationRun

# Everything importable as `from models import X`.
__all__ = [
    "Base",
    "Customer",
    "Seller",
    "Product",
    "Order",
    "Warehouse",
    "Inventory",
    "Vehicle",
    "DeliveryRoute",
    "Disruption",
    "OptimizationRun",
]
