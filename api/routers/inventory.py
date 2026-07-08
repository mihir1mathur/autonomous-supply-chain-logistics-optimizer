"""
============================================================================
INVENTORY ROUTER  (Week 4)   URL prefix: /inventory
Project: Supply Chain & Logistics Optimizer
============================================================================

REST endpoints for inventory (the product<->warehouse stock bridge). Thin: it
calls inventory_service, which enforces the stock/status rule.
============================================================================
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.dependencies import get_db, pagination_params, search_query
from api.schemas.base import PaginatedResponse
from api.schemas.inventory import InventoryCreate, InventoryResponse, InventoryUpdate
from api.services.inventory_service import inventory_service
from api.utils.pagination import PageParams

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get(
    "",
    response_model=PaginatedResponse[InventoryResponse],
    summary="List inventory (filter, search, sort, paginate)",
)
def list_inventory(
    db: Session = Depends(get_db),
    params: PageParams = Depends(pagination_params),
    search: str | None = Depends(search_query),
    warehouse_id: str | None = Query(None, description="Filter by warehouse."),
    product_id: str | None = Query(None, description="Filter by product."),
    inventory_status: str | None = Query(
        None, description="Filter by healthy / low_stock / out_of_stock."
    ),
    product_category_name: str | None = Query(None, description="Filter by category."),
):
    """Return a page of inventory rows with optional filters, search, sorting."""
    return inventory_service.list(
        db,
        params,
        filters={
            "warehouse_id": warehouse_id,
            "product_id": product_id,
            "inventory_status": inventory_status,
            "product_category_name": product_category_name,
        },
        search=search,
    )


@router.get("/{inventory_id}", response_model=InventoryResponse, summary="Get one inventory item by id")
def get_inventory_item(inventory_id: str, db: Session = Depends(get_db)):
    return inventory_service.get(db, inventory_id)


@router.post(
    "",
    response_model=InventoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new inventory item (status is derived from stock)",
)
def create_inventory_item(payload: InventoryCreate, db: Session = Depends(get_db)):
    return inventory_service.create(db, payload.model_dump())


@router.put("/{inventory_id}", response_model=InventoryResponse, summary="Replace an inventory item")
def replace_inventory_item(inventory_id: str, payload: InventoryUpdate, db: Session = Depends(get_db)):
    return inventory_service.update(db, inventory_id, payload.model_dump(exclude_unset=True))


@router.patch("/{inventory_id}", response_model=InventoryResponse, summary="Partially update an inventory item")
def update_inventory_item(inventory_id: str, payload: InventoryUpdate, db: Session = Depends(get_db)):
    return inventory_service.update(db, inventory_id, payload.model_dump(exclude_unset=True))


@router.delete(
    "/{inventory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an inventory item",
)
def delete_inventory_item(inventory_id: str, db: Session = Depends(get_db)):
    inventory_service.delete(db, inventory_id)
