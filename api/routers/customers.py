"""
============================================================================
CUSTOMERS ROUTER  (Week 4)   URL prefix: /customers
Project: Supply Chain & Logistics Optimizer
============================================================================

REST endpoints for customers (delivery DESTINATIONS). This file is the REFERENCE
router - the other six follow the exact same shape.

Every endpoint is THIN: it reads the request, calls customer_service, and
returns the result. No database access, no business logic here.

ENDPOINTS
  GET    /customers            list: filter + search + sort + pagination
  GET    /customers/{id}       one customer by id (404 if missing)
  POST   /customers            create (409 if the id already exists)
  PUT    /customers/{id}       full update
  PATCH  /customers/{id}       partial update
  DELETE /customers/{id}       delete (204 No Content)
============================================================================
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.dependencies import get_db, pagination_params, search_query
from api.schemas.base import PaginatedResponse
from api.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from api.services.customer_service import customer_service
from api.utils.pagination import PageParams

# tags= groups these endpoints together in the Swagger UI docs.
router = APIRouter(prefix="/customers", tags=["Customers"])


# ---------------------------------------------------------------------------
# LIST  -  GET /customers
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=PaginatedResponse[CustomerResponse],
    summary="List customers (filter, search, sort, paginate)",
)
def list_customers(
    db: Session = Depends(get_db),
    params: PageParams = Depends(pagination_params),
    search: str | None = Depends(search_query),
    # Explicit filter parameters (shown in the docs). Each is optional.
    customer_state: str | None = Query(None, description="Filter by 2-letter state code."),
    customer_city: str | None = Query(None, description="Filter by city."),
    customer_zip_code_prefix: int | None = Query(None, description="Filter by zip prefix."),
):
    """
    Return a page of customers. Combine any of:
      - filters:   ?customer_state=SP&customer_city=franca
      - search:    ?search=sao   (matches city / id / unique id)
      - sorting:   ?sort_by=customer_city&sort_dir=asc
      - paging:    ?page=2&page_size=50
    """
    return customer_service.list(
        db,
        params,
        filters={
            "customer_state": customer_state.upper() if customer_state else None,
            "customer_city": customer_city,
            "customer_zip_code_prefix": customer_zip_code_prefix,
        },
        search=search,
    )


# ---------------------------------------------------------------------------
# GET ONE  -  GET /customers/{customer_id}
# ---------------------------------------------------------------------------
@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get one customer by id",
)
def get_customer(customer_id: str, db: Session = Depends(get_db)):
    """Return a single customer, or 404 if no customer has that id."""
    return customer_service.get(db, customer_id)


# ---------------------------------------------------------------------------
# CREATE  -  POST /customers
# ---------------------------------------------------------------------------
@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer",
)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    """
    Create a customer. Returns 201 Created with the new row, or 409 Conflict if
    a customer with that id already exists.
    """
    return customer_service.create(db, payload.model_dump())


# ---------------------------------------------------------------------------
# FULL UPDATE  -  PUT /customers/{customer_id}
# ---------------------------------------------------------------------------
@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Replace an existing customer",
)
def replace_customer(
    customer_id: str, payload: CustomerUpdate, db: Session = Depends(get_db)
):
    """Update a customer with the full set of fields provided. 404 if missing."""
    return customer_service.update(db, customer_id, payload.model_dump(exclude_unset=True))


# ---------------------------------------------------------------------------
# PARTIAL UPDATE  -  PATCH /customers/{customer_id}
# ---------------------------------------------------------------------------
@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Partially update a customer",
)
def update_customer(
    customer_id: str, payload: CustomerUpdate, db: Session = Depends(get_db)
):
    """Change only the fields sent. 404 if the customer does not exist."""
    return customer_service.update(db, customer_id, payload.model_dump(exclude_unset=True))


# ---------------------------------------------------------------------------
# DELETE  -  DELETE /customers/{customer_id}
# ---------------------------------------------------------------------------
@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a customer",
)
def delete_customer(customer_id: str, db: Session = Depends(get_db)):
    """Delete a customer. Returns 204 No Content, or 404 if it does not exist."""
    customer_service.delete(db, customer_id)
