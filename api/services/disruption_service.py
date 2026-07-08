"""
============================================================================
DISRUPTION SERVICE  (Week 4)   entity: disruptions
Project: Supply Chain & Logistics Optimizer
============================================================================

Business logic for disruptions (events that delay deliveries). Subclasses
BaseService for generic CRUD + pagination and declares disruption-specific
safelists.

The Week 3 CRUD layer already has crud.get_active_disruptions() and
crud.insert_disruption(); this service adds a convenience list_active() helper
that reuses that exact query, so the "active disruptions" logic lives in one
place across Week 3 and Week 4 (and the future agents in Week 7).
============================================================================
"""

from sqlalchemy.orm import Session

from database import crud
from models import Disruption

from api.services.base_service import BaseService


class DisruptionService(BaseService):
    model = Disruption
    pk_name = "disruption_id"
    entity_name = "Disruption"

    filterable_fields = {
        "disruption_type",
        "severity",
        "status",
        "location_state",
        "location_city",
        "affected_warehouse_id",
    }
    searchable_fields = {
        "disruption_id",
        "location_city",
        "impact_description",
    }
    sortable_fields = {
        "disruption_id",
        "disruption_type",
        "severity",
        "status",
        "estimated_delay_minutes",
        "start_time",
    }

    def list_active(self, db: Session):
        """
        Return all currently-active disruptions, reusing the Week 3 helper so
        the definition of "active" stays in exactly one place.
        """
        return crud.get_active_disruptions(db)


disruption_service = DisruptionService()
