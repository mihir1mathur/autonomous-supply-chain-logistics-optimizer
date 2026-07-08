"""
============================================================================
BASE SERVICE  (Week 4)   -- shared CRUD logic every service reuses
Project: Supply Chain & Logistics Optimizer
============================================================================

WHY THIS FILE EXISTS
--------------------
  All seven entities need the SAME basic operations: get one by id, list many
  (with filters + search + pagination), create, update, delete. Writing those
  five operations seven times would be repetitive and easy to get subtly
  inconsistent. So the common shape lives here ONCE, and each entity's service
  (customer_service.py, etc.) subclasses it and only adds what is specific to
  that entity (which columns you may filter/search/sort by, and any special
  business rules).

  This is normal backend design: a generic base for the boring 90%, and small
  focused subclasses for the interesting 10%.

WHAT EACH OPERATION GUARANTEES
------------------------------
  get()     - returns the row, or raises NotFoundError (-> 404) if missing.
  list()    - applies equality filters + optional text search, then returns a
              standard paginated envelope (see utils/pagination.py).
  create()  - refuses to overwrite an existing id (-> 409 DuplicateError), then
              inserts and commits.
  update()  - partial update: only the fields the caller sent are changed;
              missing id -> 404.
  delete()  - removes the row; missing id -> 404.

  Only this layer (and the entity services) commit. Routers never do.
============================================================================
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.utils.exceptions import DuplicateError, NotFoundError
from api.utils.pagination import Page, PageParams, paginate


class BaseService:
    """
    Generic create/read/update/delete for one SQLAlchemy model.

    Subclasses set the class attributes below. Everything else is inherited.
    """

    # ---- Subclasses MUST set these ----------------------------------------
    model = None                 # the SQLAlchemy model class (e.g. Customer).
    pk_name: str = "id"          # the primary-key attribute name (e.g. "customer_id").
    entity_name: str = "record"  # human name used in error messages.

    # ---- Subclasses SHOULD set these (safelists) --------------------------
    # Columns the caller may filter by exactly (?customer_state=SP).
    filterable_fields: set[str] = set()
    # Text columns searched by ?search= (case-insensitive, partial match).
    searchable_fields: set[str] = set()
    # Columns the caller may sort by (?sort_by=...).
    sortable_fields: set[str] = set()

    # ---- READ: one by id --------------------------------------------------
    def get_or_none(self, db: Session, item_id: str):
        """Return the row with this primary key, or None if it does not exist."""
        return db.get(self.model, item_id)

    def get(self, db: Session, item_id: str):
        """Return the row, or raise NotFoundError (-> 404) if it is missing."""
        item = self.get_or_none(db, item_id)
        if item is None:
            raise NotFoundError(
                f"{self.entity_name} '{item_id}' was not found."
            )
        return item

    # ---- READ: many (filter + search + paginate) --------------------------
    def _base_select(self):
        """The starting SELECT. Subclasses can override to add joins/defaults."""
        return select(self.model)

    def _apply_filters(self, stmt, filters: dict):
        """
        Add a WHERE <column> = <value> for each allowed, provided filter.
        Unknown or None filters are ignored, so only safelisted columns match.
        """
        for field, value in filters.items():
            if value is None:
                continue
            if field in self.filterable_fields:
                stmt = stmt.where(getattr(self.model, field) == value)
        return stmt

    def _apply_search(self, stmt, search: str | None):
        """
        Add a case-insensitive partial-match search across searchable_fields.
        Matching ANY of them counts (OR), e.g. search 'sao' hits city OR state.
        """
        if not search or not self.searchable_fields:
            return stmt
        pattern = f"%{search}%"
        conditions = [
            getattr(self.model, field).ilike(pattern)
            for field in self.searchable_fields
        ]
        from sqlalchemy import or_

        return stmt.where(or_(*conditions))

    def list(
        self,
        db: Session,
        params: PageParams,
        *,
        filters: dict | None = None,
        search: str | None = None,
    ) -> Page:
        """
        Build the SELECT (filters + search), then hand it to paginate() which
        counts totals, sorts (safelisted), slices the page, and returns the
        standard {"items": [...], "pagination": {...}} envelope.
        """
        stmt = self._base_select()
        stmt = self._apply_filters(stmt, filters or {})
        stmt = self._apply_search(stmt, search)
        return paginate(db, stmt, self.model, params, sortable=self.sortable_fields)

    # ---- CREATE -----------------------------------------------------------
    def create(self, db: Session, data: dict):
        """
        Insert a new row. Refuses to overwrite an existing primary key (raises
        DuplicateError -> 409). Subclasses can override to add business rules
        (e.g. derive inventory_status) by preparing `data` first.
        """
        item_id = data.get(self.pk_name)
        if item_id is not None and self.get_or_none(db, item_id) is not None:
            raise DuplicateError(
                f"{self.entity_name} '{item_id}' already exists."
            )
        item = self.model(**data)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    # ---- UPDATE (partial) -------------------------------------------------
    def update(self, db: Session, item_id: str, data: dict):
        """
        Change only the fields present in `data`. Missing id -> NotFoundError.
        `data` should already exclude unset fields (the router uses
        model_dump(exclude_unset=True) so PATCH/PUT only touch sent fields).
        """
        item = self.get(db, item_id)
        for field, value in data.items():
            setattr(item, field, value)
        db.commit()
        db.refresh(item)
        return item

    # ---- DELETE -----------------------------------------------------------
    def delete(self, db: Session, item_id: str) -> None:
        """Remove the row. Missing id -> NotFoundError (-> 404)."""
        item = self.get(db, item_id)
        db.delete(item)
        db.commit()
