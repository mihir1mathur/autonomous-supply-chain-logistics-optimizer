"""
============================================================================
AGENT UTILITIES  (Week 7)   -- shared plumbing for the orchestration layer
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT LIVES HERE
---------------
  The small, boring-but-essential helpers every agent shares, so no agent
  re-invents them:

    * LOGGING      - one project logger, one consistent line format.
    * TIMING       - a Timer (the same idea as optimization/utils.py's Timer)
                     so every agent step reports how long it took.
    * TRACING      - AgentStep / ExecutionTrace records that capture, step by
                     step, what each agent did, how long it took, and whether it
                     succeeded. This is the "execution tracing" the base agent
                     requires, and it is what makes an autonomous run auditable.
    * SERIALIZATION- to_jsonable(), which turns dataclasses / nested structures
                     into plain JSON-friendly dicts for the API and the reports.

  It ALSO defines the STRUCTURED DATA CONTRACTS the agents pass down the
  pipeline. Each agent produces one typed object and the next agent consumes it:

      user request
          -> Planner   produces  ExecutionPlan
          -> Scenario  produces  ScenarioDecision
          -> Optimization produces OptimizationOutcome   (drives Week 6)
          -> Evaluation   produces EvaluationSummary
          -> Reporting    produces AgentReport
      all gathered into one OrchestrationResult.

WHY DATACLASSES (and not dicts everywhere)
------------------------------------------
  Exactly like the Week 5 solution_models and the Week 6 RunMetrics/
  EvaluationResult: a typed dataclass documents the shape once, is trivial to
  build and test, and turns into clean JSON with as_dict(). Passing typed
  objects between agents (rather than loose dicts) is what keeps the pipeline
  legible and hard to get subtly wrong.

WHY THIS FILE IS DEPENDENCY-LIGHT
---------------------------------
  Nothing here imports CrewAI, FastAPI, the database, or OR-Tools. These are
  pure Python helpers and plain data, so every agent can import them freely and
  they can be unit-tested in isolation.
============================================================================
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any


# ===========================================================================
# LOGGING  -- one logger, one format, for the whole orchestration layer
# ===========================================================================
_LOG_FORMAT = "[%(asctime)s] %(name)s %(levelname)s: %(message)s"


def get_logger(name: str = "agents") -> logging.Logger:
    """
    Return a project logger under the "agents" namespace with a consistent
    format. Adding a handler only once (guarded by `logger.handlers`) avoids the
    classic "every log line prints twice" bug when a module is imported more
    than once.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        # Do not also bubble up to the root logger (prevents duplicate lines when
        # some other library has configured the root handler).
        logger.propagate = False
    return logger


# ===========================================================================
# TIMING  -- how long did a step take? (same idea as optimization/utils.Timer)
# ===========================================================================
class Timer:
    """
    A tiny stopwatch used as a context manager:

        with Timer() as t:
            ... do work ...
        print(t.elapsed_ms)

    Uses time.perf_counter (a monotonic, high-resolution clock) so it measures
    real elapsed time accurately and is never thrown off by the wall clock
    changing. Mirrors the Timer the Week 5 engine already uses.
    """

    def __init__(self) -> None:
        self._start = 0.0
        self._end = 0.0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self._end = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        """Elapsed milliseconds (rounded), whether or not the block has ended."""
        end = self._end or time.perf_counter()
        return round((end - self._start) * 1000.0, 2)


def utc_now_iso() -> str:
    """A timezone-aware UTC timestamp as an ISO string (for trace records)."""
    return datetime.now(timezone.utc).isoformat()


# ===========================================================================
# SERIALIZATION  -- turn dataclasses / nested data into JSON-friendly dicts
# ===========================================================================
def to_jsonable(value: Any) -> Any:
    """
    Recursively convert dataclasses, dicts, lists and tuples into plain,
    JSON-serialisable Python. Anything already plain (str/int/float/bool/None)
    passes straight through; anything exotic is stringified as a last resort.

    The API returns these structures and the reporting agent embeds them in a
    JSON report, so having ONE reliable converter keeps that safe and simple.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return {k: to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    return str(value)


# ===========================================================================
# EXECUTION TRACING  -- an auditable record of what each agent did
# ===========================================================================
@dataclass
class AgentStep:
    """
    One entry in an orchestration trace: which agent ran, whether it succeeded,
    how long it took, and a short human-readable summary of what it decided.

    Collecting these is what turns "the agents did something" into an auditable
    story a human (or a Week 8 dashboard) can follow after the fact.
    """

    agent: str                       # e.g. "PlannerAgent"
    action: str                      # e.g. "build_execution_plan"
    success: bool = True
    duration_ms: float = 0.0
    summary: str = ""                # a one-line, human-readable outcome
    started_at: str = field(default_factory=utc_now_iso)
    error: str | None = None         # set only when success is False

    def as_dict(self) -> dict:
        return to_jsonable(self)


@dataclass
class ExecutionTrace:
    """The ordered list of AgentSteps for one orchestration run."""

    steps: list[AgentStep] = field(default_factory=list)

    def record(self, step: AgentStep) -> AgentStep:
        """Append a completed step and return it (so callers can keep a handle)."""
        self.steps.append(step)
        return step

    @property
    def total_ms(self) -> float:
        """Total wall-clock time across every recorded step."""
        return round(sum(s.duration_ms for s in self.steps), 2)

    @property
    def all_succeeded(self) -> bool:
        return all(s.success for s in self.steps)

    def as_dict(self) -> dict:
        return {
            "steps": [s.as_dict() for s in self.steps],
            "total_ms": self.total_ms,
            "all_succeeded": self.all_succeeded,
        }


# ===========================================================================
# STRUCTURED CONTRACTS  -- the typed objects agents pass down the pipeline
# ===========================================================================
@dataclass
class ExecutionPlan:
    """
    The Planner Agent's output: WHAT should happen, never HOW to solve it.

    It names the optimizer to run, the target warehouse (or None to auto-pick),
    the priority, and the constraints/limits to pass to the execution service -
    plus a plain-language rationale and the ordered steps it recommends. The
    Planner decides the intent; the later agents carry it out.
    """

    optimizer: str = "assignment"            # assignment / fleet / routes / warehouse
    warehouse_id: str | None = None          # None => execution service auto-selects
    priority: str = "normal"                 # normal / high  (how urgent the request is)
    objective: str = "minimize_cost"         # a short label for the goal
    # Constraints/limits handed straight to the Week 6 execution service.
    constraints: dict = field(default_factory=dict)
    rationale: str = ""                      # why the Planner chose the above
    steps: list[str] = field(default_factory=list)  # the ordered plan of action

    def as_dict(self) -> dict:
        return to_jsonable(self)


@dataclass
class ScenarioDecision:
    """
    The Scenario Agent's output: which Week 6 scenario to run the plan under.

    It carries the scenario's KEY (validated against the existing Week 6 catalog,
    never invented here) plus the catalog's name/category/description and a short
    rationale for the choice. The effects themselves stay in Week 6's
    scenarios.py - this is only the DECISION of which one to use.
    """

    key: str = "normal"
    name: str = "Normal Operations"
    category: str = "baseline"
    description: str = ""
    rationale: str = ""

    def as_dict(self) -> dict:
        return to_jsonable(self)


@dataclass
class OptimizationOutcome:
    """
    The Optimization Agent's output: the result of driving the Week 6 execution
    service, plus a note of exactly which service call was made.

    `result` is the full dict the execution service returns (run_id, metrics,
    evaluation, scenario_changes, ...). We never reshape or recompute it here -
    the agent orchestrates; the execution service owns the numbers.
    """

    optimizer: str = "assignment"
    scenario: str = "normal"
    invoked: str = "execution_service.run"   # the exact call the agent made
    persisted: bool = False
    run_id: str | None = None
    success: bool = False
    result: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return to_jsonable(self)


@dataclass
class EvaluationSummary:
    """
    The Evaluation Agent's output: a structured read of the run's KPIs and its
    before-vs-after evaluation, an overall verdict, and (optionally) a benchmark
    comparison against a reference run. All numbers come from the Week 6 metrics
    and evaluation framework, reused unchanged.
    """

    verdict: str = "unknown"                 # improved / degraded / mixed / neutral
    headline: str = ""                       # one-line summary a human reads first
    kpis: dict = field(default_factory=dict)          # the 12 KPIs of this run
    improvements: dict = field(default_factory=dict)  # the evaluation percentages
    benchmark: dict | None = None            # comparison vs a reference run (if any)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return to_jsonable(self)


@dataclass
class AgentReport:
    """
    The Reporting Agent's output: the SAME report rendered three ways so it can
    feed a human reader (markdown), a program or dashboard (json), or a log
    (plain text). Recommendations and future improvements are included.
    """

    markdown: str = ""
    text: str = ""
    json: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    future_improvements: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return to_jsonable(self)


@dataclass
class OrchestrationResult:
    """
    The whole outcome of one autonomous decision: every agent's structured
    output, the execution trace, and which orchestration mode produced it. This
    is what the coordinator returns and what the /agents API serves.
    """

    request: dict = field(default_factory=dict)
    mode: str = "deterministic"              # deterministic / crewai
    mode_detail: str = ""
    success: bool = False
    plan: dict = field(default_factory=dict)
    scenario: dict = field(default_factory=dict)
    optimization: dict = field(default_factory=dict)
    evaluation: dict = field(default_factory=dict)
    report: dict = field(default_factory=dict)
    trace: dict = field(default_factory=dict)
    crew_narrative: str | None = None        # the LLM's narration (crewai mode only)
    message: str = ""

    def as_dict(self) -> dict:
        return to_jsonable(self)
