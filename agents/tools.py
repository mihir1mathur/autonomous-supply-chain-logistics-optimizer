"""
============================================================================
AGENT TOOLS  (Week 7)   -- the ONLY seam through which agents touch the platform
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT A "TOOL" IS HERE (zero-knowledge version)
----------------------------------------------
  The agents are decision-makers; they must never poke at OR-Tools or the
  database directly. Instead, every capability they are allowed to use is
  exposed as a small, named TOOL that calls the EXISTING Week 6 execution
  service (api/services/execution_service.py). The agents only ever act through
  these tools. This is exactly the architecture the Week 7 goals require:

      agents  ->  tools  ->  Week 6 execution service  ->  Week 5 engine  ->  DB

  Because the platform capabilities live behind ONE thin module, both
  orchestration modes use the identical tools: the deterministic pipeline calls
  these functions directly, and the CrewAI crew wraps the very same functions as
  LLM-callable tools (build_crew_tools). So the numeric work is always done by
  the trusted, tested execution service - never re-implemented, never bypassed.

THE BLACKBOARD (ToolContext)
----------------------------
  One orchestration run shares a small ToolContext ("blackboard"): the database
  session to use, the settings, and a place for a tool to stash its structured
  result (e.g. the last optimization outcome). In CrewAI mode the LLM decides
  WHEN to call a tool, but the tool still records its real, structured result on
  the blackboard - so after the crew finishes we harvest trustworthy data from
  the blackboard rather than trying to parse it back out of the LLM's prose.

DATABASE SESSIONS (reusing Week 3/4 wiring, never re-creating it)
-----------------------------------------------------------------
  The execution service needs a SQLAlchemy Session. When the API calls the
  orchestrator it passes the request's session straight through (ToolContext.db).
  When a script or the crew runs a tool with no session supplied, the tool opens
  ONE short-lived session from the Week 3 SessionLocal and always closes it -
  the same open/use/close discipline as api/database.get_db.

WHY NO CREWAI IMPORT AT THE TOP
-------------------------------
  This module must import cleanly whether or not CrewAI is installed (the whole
  deterministic path depends on it). So `crewai` is imported LAZILY, only inside
  build_crew_tools(), which the crew calls only when it actually runs.
============================================================================
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from sqlalchemy.orm import Session

# Reuse the Week 3 session factory (lazy engine - importing does NOT connect).
from database.connection import SessionLocal
# The single Week 6 service the agents are allowed to drive. Importing it does
# NOT touch the database or pull in CrewAI/OR-Tools eagerly beyond Week 5/6.
from api.services.execution_service import execution_service

from agents.config import AgentSettings, get_agent_settings
from agents.utils import get_logger

_logger = get_logger("agents.tools")

# The constraint keys the run-optimization tool forwards to the execution
# service (everything else in a plan's `constraints` dict is ignored safely).
_CONSTRAINT_KEYS = (
    "max_shipments",
    "max_stops",
    "sample_size",
    "strategy",
    "reserve_inventory",
    "evaluate_run",
)


# ===========================================================================
# THE BLACKBOARD  -- state shared by every tool call in one run
# ===========================================================================
@dataclass
class ToolContext:
    """
    Shared state for one orchestration run.

    * db        - the SQLAlchemy session to use (from the API request). If None,
                  each tool opens and closes its own short-lived session.
    * settings  - the Week 7 agent settings.
    * last_outcome    - where run_optimization stashes its structured result, so
                        the evaluation agent (and the CrewAI harvester) can read
                        the real numbers regardless of orchestration mode.
    * scenario_catalog - cached scenario catalog (fetched once per run).
    """

    db: Session | None = None
    settings: AgentSettings = field(default_factory=get_agent_settings)
    last_outcome: dict | None = None
    scenario_catalog: list[dict] | None = None


@contextmanager
def _session(ctx: ToolContext) -> Iterator[Session]:
    """
    Yield a database session: the one on the blackboard if present, otherwise a
    fresh SessionLocal that we open here and ALWAYS close. This mirrors the
    open/use/close rule of api/database.get_db without duplicating any Week 3
    connection logic.
    """
    if ctx.db is not None:
        yield ctx.db
        return
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ===========================================================================
# TOOL 1: the scenario catalog  (reuses the Week 6 scenario engine)
# ===========================================================================
def get_scenario_catalog(ctx: ToolContext) -> list[dict]:
    """
    Return the catalog of scenarios the platform knows about (key / name /
    category / description). Delegates to execution_service.list_scenarios(),
    which reads the Week 6 scenario engine - the agents never redefine scenarios.
    Cached on the blackboard so repeated calls in one run are free.
    """
    if ctx.scenario_catalog is None:
        ctx.scenario_catalog = execution_service.list_scenarios()
    return ctx.scenario_catalog


# ===========================================================================
# TOOL 2: run one optimization  (the heart of the orchestration)
# ===========================================================================
def run_optimization(
    ctx: ToolContext,
    *,
    optimizer: str,
    scenario: str,
    warehouse_id: str | None = None,
    persist: bool = True,
    constraints: dict | None = None,
) -> dict:
    """
    Run ONE optimization under a scenario by calling the Week 6 execution
    service, and record the result on the blackboard.

    This is the tool that actually makes the platform do work. It does NOT touch
    OR-Tools or the database directly - it calls execution_service.run() (persist
    True) or .simulate() (persist False), which owns the entire
    load -> scenario -> solve -> measure -> evaluate -> store pipeline. The
    result dict (run_id, KPIs, evaluation, scenario_changes, ...) is returned
    unchanged and also stashed in ctx.last_outcome.
    """
    kwargs: dict[str, Any] = {
        "optimizer": optimizer,
        "scenario": scenario,
        "warehouse_id": warehouse_id,
    }
    # Forward only the recognised constraint keys, ignoring anything unexpected.
    for key in _CONSTRAINT_KEYS:
        if constraints and key in constraints and constraints[key] is not None:
            kwargs[key] = constraints[key]

    with _session(ctx) as db:
        if persist:
            outcome = execution_service.run(db, persist=True, **kwargs)
        else:
            outcome = execution_service.simulate(db, **kwargs)

    ctx.last_outcome = outcome
    _logger.info(
        "run_optimization: %s / %s -> success=%s run_id=%s",
        optimizer, scenario, outcome.get("success"), outcome.get("run_id"),
    )
    return outcome


# ===========================================================================
# TOOL 3: benchmark one optimizer across several scenarios
# ===========================================================================
def run_benchmark(
    ctx: ToolContext,
    *,
    optimizer: str,
    scenarios: list[str],
    warehouse_id: str | None = None,
    persist: bool = False,
) -> dict:
    """
    Run the SAME optimizer under several scenarios and return one comparison
    report. Delegates to execution_service.run_benchmark() (Week 6, Part 7).
    Defaults to persist=False so a benchmark comparison does not clutter the
    stored history unless the caller asks for it.
    """
    with _session(ctx) as db:
        return execution_service.run_benchmark(
            db,
            optimizer=optimizer,
            scenarios=scenarios,
            warehouse_id=warehouse_id,
            persist=persist,
        )


# ===========================================================================
# CREWAI TOOL WRAPPERS  (built lazily, only when the crew actually runs)
# ===========================================================================
def build_crew_tools(ctx: ToolContext) -> list:
    """
    Wrap the plain tool functions above as CrewAI tools bound to THIS run's
    blackboard, and return them for the crew to hand to its agents.

    CrewAI is imported HERE, lazily, so this module still imports fine when
    CrewAI is absent (the deterministic path never calls this function). Each
    wrapper closes over `ctx`, so an LLM tool call runs against the correct
    session and records its result on the correct blackboard - which is how we
    recover trustworthy structured data after an LLM-driven run.
    """
    # Imported lazily on purpose - see the module header.
    from crewai.tools import tool  # noqa: PLC0415

    @tool("scenario_catalog")
    def scenario_catalog_tool() -> list[dict]:
        """List the available optimization scenarios (key, name, category, description)."""
        return get_scenario_catalog(ctx)

    @tool("run_optimization")
    def run_optimization_tool(
        optimizer: str,
        scenario: str = "normal",
        warehouse_id: str | None = None,
        max_shipments: int | None = None,
    ) -> dict:
        """
        Run one optimization under a scenario and return its KPIs and evaluation.
        optimizer must be one of: assignment, fleet, routes, warehouse.
        """
        return run_optimization(
            ctx,
            optimizer=optimizer,
            scenario=scenario,
            warehouse_id=warehouse_id,
            persist=True,
            constraints={"max_shipments": max_shipments},
        )

    @tool("run_benchmark")
    def run_benchmark_tool(optimizer: str, scenarios: list[str]) -> dict:
        """Benchmark one optimizer across several scenarios and return a comparison."""
        return run_benchmark(ctx, optimizer=optimizer, scenarios=scenarios)

    return [scenario_catalog_tool, run_optimization_tool, run_benchmark_tool]
