"""
============================================================================
CUSTOMER SERVICE  (Week 4)   entity: customers
Project: Supply Chain & Logistics Optimizer
============================================================================

Business logic for customers (delivery DESTINATIONS). It subclasses BaseService
for the generic create/read/update/delete + pagination, and only declares what
is SPECIFIC to customers:
  - which columns may be filtered  (state, city, zip)
  - which columns are searched by ?search=
  - which columns may be sorted by

Customers are REAL Olist data and mostly read-heavy, so there is no special
write rule here; the base CRUD is enough. The router calls the single shared
instance `customer_service` at the bottom.
============================================================================
"""

from models import Customer

from api.services.base_service import BaseService


class CustomerService(BaseService):
    model = Customer
    pk_name = "customer_id"
    entity_name = "Customer"

    # ?customer_state=SP  or  ?customer_city=franca  or  ?customer_zip_code_prefix=14409
    filterable_fields = {
        "customer_state",
        "customer_city",
        "customer_zip_code_prefix",
        "customer_unique_id",
    }
    # ?search=sao  -> matches city, id, or unique id (case-insensitive, partial).
    searchable_fields = {
        "customer_city",
        "customer_id",
        "customer_unique_id",
    }
    # ?sort_by=customer_city&sort_dir=asc
    sortable_fields = {
        "customer_id",
        "customer_city",
        "customer_state",
        "customer_zip_code_prefix",
    }


# ONE shared instance the router imports. Stateless, so sharing it is safe.
customer_service = CustomerService()
