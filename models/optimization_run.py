"""
OPTIMIZATION RUN MODEL  (table: optimization_runs)  -- a STORED optimization run.

New in Week 6 (the "optimization execution layer"). Weeks 3-5 stored the supply
chain DATA and computed optimization plans on demand, but never KEPT a record of
a run. Week 6 does: every time the execution layer runs an optimization (or a
scenario), it saves one row here - what was run, how it went, and the resulting
KPIs - so the project can show a HISTORY, look a run up by id, and aggregate
metrics across runs.

WHY THIS IS ADDITIVE (no migration, no change to earlier tables)
  This is a brand-new table. database/init_db.py's create_all() creates only
  tables that do not yet exist, so running it once after Week 6 adds this table
  and leaves every Week 3 table and its rows untouched. Nothing about Weeks 0-5
  changes.

WHAT A ROW HOLDS
  - identity + context: run_id, created_at, scenario, optimizer, warehouse_id.
  - the twelve KPIs (Week 6, Part 5) promoted to real columns so history and
    the /optimization/metrics aggregate can query/sort them directly.
  - three JSON blobs for the full detail: the complete metrics, the before/after
    evaluation, and a compact result/context snapshot (scenario changes, sizes).
"""

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.sql import func

from database.connection import Base


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"

    # PRIMARY KEY - a generated id, e.g. "RUN-3f9a1c2b4d5e" (see execution_service).
    run_id = Column(String, primary_key=True)

    # When the run happened. Indexed because history is ordered by it (newest
    # first). Defaults to the database's current timestamp if not set explicitly.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # WHICH scenario and WHICH optimizer produced this run. Indexed: we filter
    # history and aggregate metrics by these.
    scenario = Column(String, index=True)     # normal / high_demand / ...
    optimizer = Column(String, index=True)    # assignment / warehouse / fleet / routes

    # The target warehouse where a single warehouse applies (assignment / fleet /
    # routes). Plain string (not a foreign key): warehouse selection spans many
    # warehouses, so this is nullable and purely descriptive.
    warehouse_id = Column(String, nullable=True, index=True)

    # Did the run succeed, and what did the solver report.
    success = Column(Boolean, default=True)
    solver_status = Column(String)            # OPTIMAL / FEASIBLE / OK / ...

    # ---- The twelve KPIs (Week 6, Part 5), promoted to columns ------------
    total_cost = Column(Float, default=0.0)
    travel_distance_km = Column(Float, default=0.0)
    vehicle_utilization = Column(Float, default=0.0)      # 0..1
    warehouse_utilization = Column(Float, default=0.0)    # 0..1
    inventory_holding_cost = Column(Float, default=0.0)
    stockouts = Column(Integer, default=0)
    late_deliveries = Column(Integer, default=0)
    orders_fulfilled = Column(Integer, default=0)
    runtime_ms = Column(Float, default=0.0)               # optimization runtime
    num_constraints = Column(Integer, default=0)
    num_variables = Column(Integer, default=0)
    vehicles_used = Column(Integer, default=0)

    # ---- Full detail as JSON (Postgres JSON column) -----------------------
    # metrics    : the complete RunMetrics dict (superset of the columns above).
    # evaluation : the before-vs-after EvaluationResult dict (may be null).
    # details    : a compact snapshot - scenario changes applied, problem sizes,
    #              and the request that produced the run.
    metrics = Column(JSON, nullable=True)
    evaluation = Column(JSON, nullable=True)
    details = Column(JSON, nullable=True)

    def __repr__(self):
        return (
            f"<OptimizationRun {self.run_id} {self.optimizer}/{self.scenario} "
            f"cost={self.total_cost} status={self.solver_status}>"
        )
