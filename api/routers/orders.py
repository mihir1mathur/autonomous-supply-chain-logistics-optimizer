"""
============================================================================
ORDERS ROUTER  (Week 4)   URL prefix: /orders
Project: Supply Chain & Logistics Optimizer
============================================================================

REST endpoints for orders (SHIPMENT REQUESTS). Thin: calls order_service.
============================================================================
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.dependencies import get_db, pagination_params, search_query
from api.schemas.base import PaginatedResponse
from api.schemas.order import OrderCreate, OrderResponse, OrderUpdate
from api.services.order_service import order_service
from api.utils.pagination import PageParams

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get(
    "",
    response_model=PaginatedResponse[OrderResponse],
    summary="List orders (filter, search, sort, paginate)",
)
def list_orders(
    db: Session = Depends(get_db),
    params: PageParams = Depends(pagination_params),
    search: str | None = Depends(search_query),
    customer_id: str | None = Query(None, description="Filter by customer."),
    order_status: str | None = Query(None, description="Filter by order status."),
):
    """Return a page of orders with optional filters, search, and sorting."""
    return order_service.list(
        db,
        params,
        filters={"customer_id": customer_id, "order_status": order_status},
        search=search,
    )


@router.get("/{order_id}", response_model=OrderResponse, summary="Get one order by id")
def get_order(order_id: str, db: Session = Depends(get_db)):
    return order_service.get(db, order_id)


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order",
)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    return order_service.create(db, payload.model_dump())


@router.put("/{order_id}", response_model=OrderResponse, summary="Replace an order")
def replace_order(order_id: str, payload: OrderUpdate, db: Session = Depends(get_db)):
    return order_service.update(db, order_id, payload.model_dump(exclude_unset=True))


@router.patch("/{order_id}", response_model=OrderResponse, summary="Partially update an order")
def update_order(order_id: str, payload: OrderUpdate, db: Session = Depends(get_db)):
    return order_service.update(db, order_id, payload.model_dump(exclude_unset=True))


@router.delete(
    "/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an order",
)
def delete_order(order_id: str, db: Session = Depends(get_db)):
    order_service.delete(db, order_id)
