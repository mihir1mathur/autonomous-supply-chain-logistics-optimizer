"""
============================================================================
DISRUPTIONS ROUTER  (Week 4)   URL prefix: /disruptions
Project: Supply Chain & Logistics Optimizer
============================================================================

REST endpoints for disruptions (events that delay deliveries). Thin: calls
disruption_service. It also exposes a small convenience endpoint,
GET /disruptions/active, that reuses the Week 3 "active disruptions" query.
============================================================================
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.dependencies import get_db, pagination_params, search_query
from api.schemas.base import PaginatedResponse
from api.schemas.disruption import DisruptionCreate, DisruptionResponse, DisruptionUpdate
from api.services.disruption_service import disruption_service
from api.utils.pagination import PageParams

router = APIRouter(prefix="/disruptions", tags=["Disruptions"])


@router.get(
    "",
    response_model=PaginatedResponse[DisruptionResponse],
    summary="List disruptions (filter, search, sort, paginate)",
)
def list_disruptions(
    db: Session = Depends(get_db),
    params: PageParams = Depends(pagination_params),
    search: str | None = Depends(search_query),
    disruption_type: str | None = Query(None, description="Filter by disruption type."),
    severity: str | None = Query(None, description="Filter by low / medium / high / critical."),
    status_filter: str | None = Query(
        None, alias="status", description="Filter by active / resolved / scheduled."
    ),
    location_state: str | None = Query(None, description="Filter by state code."),
    affected_warehouse_id: str | None = Query(None, description="Filter by affected warehouse."),
):
    """Return a page of disruptions with optional filters, search, and sorting."""
    return disruption_service.list(
        db,
        params,
        filters={
            "disruption_type": disruption_type,
            "severity": severity,
            "status": status_filter,
            "location_state": location_state.upper() if location_state else None,
            "affected_warehouse_id": affected_warehouse_id,
        },
        search=search,
    )


# NOTE: declared BEFORE "/{disruption_id}" so the literal path "active" is not
# mistaken for a disruption id.
@router.get(
    "/active",
    response_model=list[DisruptionResponse],
    summary="List all currently-active disruptions (reuses the Week 3 query)",
)
def list_active_disruptions(db: Session = Depends(get_db)):
    """Return every disruption whose status is 'active' (not paginated)."""
    return disruption_service.list_active(db)


@router.get("/{disruption_id}", response_model=DisruptionResponse, summary="Get one disruption by id")
def get_disruption(disruption_id: str, db: Session = Depends(get_db)):
    return disruption_service.get(db, disruption_id)


@router.post(
    "",
    response_model=DisruptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new disruption",
)
def create_disruption(payload: DisruptionCreate, db: Session = Depends(get_db)):
    return disruption_service.create(db, payload.model_dump())


@router.put("/{disruption_id}", response_model=DisruptionResponse, summary="Replace a disruption")
def replace_disruption(disruption_id: str, payload: DisruptionUpdate, db: Session = Depends(get_db)):
    return disruption_service.update(db, disruption_id, payload.model_dump(exclude_unset=True))


@router.patch("/{disruption_id}", response_model=DisruptionResponse, summary="Partially update a disruption")
def update_disruption(disruption_id: str, payload: DisruptionUpdate, db: Session = Depends(get_db)):
    return disruption_service.update(db, disruption_id, payload.model_dump(exclude_unset=True))


@router.delete(
    "/{disruption_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a disruption",
)
def delete_disruption(disruption_id: str, db: Session = Depends(get_db)):
    disruption_service.delete(db, disruption_id)
