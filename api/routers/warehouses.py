"""
============================================================================
WAREHOUSES ROUTER  (Week 4)   URL prefix: /warehouses
Project: Supply Chain & Logistics Optimizer
============================================================================

REST endpoints for warehouses (fulfillment ORIGINS). Same thin shape as the
customers router: receive request -> call warehouse_service -> return result.
============================================================================
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.dependencies import get_db, pagination_params, search_query
from api.schemas.base import PaginatedResponse
from api.schemas.warehouse import WarehouseCreate, WarehouseResponse, WarehouseUpdate
from api.services.warehouse_service import warehouse_service
from api.utils.pagination import PageParams

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


@router.get(
    "",
    response_model=PaginatedResponse[WarehouseResponse],
    summary="List warehouses (filter, search, sort, paginate)",
)
def list_warehouses(
    db: Session = Depends(get_db),
    params: PageParams = Depends(pagination_params),
    search: str | None = Depends(search_query),
    warehouse_state: str | None = Query(None, description="Filter by state code."),
    warehouse_city: str | None = Query(None, description="Filter by city."),
    operating_status: str | None = Query(
        None, description="Filter by active / overloaded / inactive."
    ),
    seller_id: str | None = Query(None, description="Filter by source seller id."),
):
    """Return a page of warehouses with optional filters, search, and sorting."""
    return warehouse_service.list(
        db,
        params,
        filters={
            "warehouse_state": warehouse_state.upper() if warehouse_state else None,
            "warehouse_city": warehouse_city,
            "operating_status": operating_status,
            "seller_id": seller_id,
        },
        search=search,
    )


@router.get("/{warehouse_id}", response_model=WarehouseResponse, summary="Get one warehouse by id")
def get_warehouse(warehouse_id: str, db: Session = Depends(get_db)):
    return warehouse_service.get(db, warehouse_id)


@router.post(
    "",
    response_model=WarehouseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new warehouse",
)
def create_warehouse(payload: WarehouseCreate, db: Session = Depends(get_db)):
    return warehouse_service.create(db, payload.model_dump())


@router.put("/{warehouse_id}", response_model=WarehouseResponse, summary="Replace a warehouse")
def replace_warehouse(warehouse_id: str, payload: WarehouseUpdate, db: Session = Depends(get_db)):
    return warehouse_service.update(db, warehouse_id, payload.model_dump(exclude_unset=True))


@router.patch("/{warehouse_id}", response_model=WarehouseResponse, summary="Partially update a warehouse")
def update_warehouse(warehouse_id: str, payload: WarehouseUpdate, db: Session = Depends(get_db)):
    return warehouse_service.update(db, warehouse_id, payload.model_dump(exclude_unset=True))


@router.delete(
    "/{warehouse_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a warehouse",
)
def delete_warehouse(warehouse_id: str, db: Session = Depends(get_db)):
    warehouse_service.delete(db, warehouse_id)
