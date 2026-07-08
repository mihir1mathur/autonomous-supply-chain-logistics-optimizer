"""
============================================================================
BASE AGENT  (Week 7)   -- the shared machinery every agent inherits
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT A "BASE AGENT" IS (zero-knowledge version)
-----------------------------------------------
  The five Week 7 agents (Planner, Scenario, Optimization, Evaluation,
  Reporting) all do very different jobs, but they share the SAME surrounding
  chores every time they run:

      * log that they started and finished,
      * time how long they took,
      * catch and record any error (instead of crashing the whole crew),
      * validate the structured object they produced, and
      * write one tidy entry into the run's execution trace.

  Rather than repeat that in five places, we put it ONCE here in BaseAgent, and
  every agent inherits it - exactly the same idea as the Week 4 BaseService,
  which gave every entity service its shared CRUD. Each agent then only has to
  implement its own real work in `_run(...)`; BaseAgent wraps that work in the
  logging / timing / error-handling / tracing shell.

THE TEMPLATE-METHOD PATTERN
---------------------------
  `execute()` is a TEMPLATE METHOD: it defines the fixed sequence (time -> run
  -> validate -> record) and calls the subclass's `_run()` for the variable
  part. This is the same shape as BaseService.list()/create() calling per-entity
  hooks. Subclasses never re-implement the shell; they fill in the hole.

WHAT EACH SUBCLASS MUST PROVIDE
-------------------------------
  * name / action  - class attributes naming the agent and what it does (for
                     logs and the trace).
  * _run(**kwargs) -> (result, summary)  - the real work: return the structured
                     dataclass this agent produces PLUS a one-line human summary.
  Optionally:
  * _validate(result) - extra checks on the produced object (raise
                     AgentValidationError to reject it). The base performs a
                     sensible default check.
============================================================================
"""

from __future__ import annotations

from typing import Any

from agents.config import AgentSettings, get_agent_settings
from agents.utils import AgentStep, ExecutionTrace, Timer, get_logger


# ===========================================================================
# ERRORS  -- clear, typed failures the coordinator can reason about
# ===========================================================================
class AgentError(Exception):
    """Base class for any failure raised by an agent."""


class AgentValidationError(AgentError):
    """The structured object an agent produced failed its validation checks."""


# ===========================================================================
# THE BASE AGENT
# ===========================================================================
class BaseAgent:
    """
    Common base for every Week 7 agent: logging, timing, error handling,
    structured-output validation, and execution tracing.

    Subclasses set `name` and `action` and implement `_run(**kwargs)`; they get
    the surrounding behaviour for free from `execute()`.
    """

    # Subclasses OVERRIDE these two (used in logs and the trace).
    name: str = "BaseAgent"
    action: str = "run"

    def __init__(self, settings: AgentSettings | None = None) -> None:
        # Shared configuration (LLM provider/model, switches). Every agent reads
        # the same settings object, mirroring the Week 4/5/6 services.
        self.settings = settings or get_agent_settings()
        # A logger namespaced under this agent, e.g. "agents.PlannerAgent".
        self.logger = get_logger(f"agents.{self.name}")

    # -----------------------------------------------------------------------
    # THE TEMPLATE METHOD  -- the fixed shell around every agent's work
    # -----------------------------------------------------------------------
    def execute(self, trace: ExecutionTrace, **kwargs: Any) -> Any:
        """
        Run this agent's work with the shared shell and record ONE trace step.

        Steps:
          1. log the start,
          2. time and run the subclass's `_run(**kwargs)`,
          3. validate the produced object,
          4. record a successful AgentStep and return the object.
        On any exception it records a FAILED AgentStep (so the trace still tells
        the full story), logs it, and re-raises as an AgentError with context so
        the coordinator can decide whether to continue or stop.
        """
        self.logger.info("%s -> %s starting", self.name, self.action)
        timer = Timer()
        try:
            with timer:
                result, summary = self._run(**kwargs)
                self._validate(result)
        except Exception as exc:  # noqa: BLE001 - we deliberately catch everything
            # Record the failure in the trace before re-raising, so a partial run
            # is still fully auditable.
            trace.record(
                AgentStep(
                    agent=self.name,
                    action=self.action,
                    success=False,
                    duration_ms=timer.elapsed_ms,
                    summary=f"{self.name} failed during '{self.action}'.",
                    error=str(exc),
                )
            )
            self.logger.error("%s failed: %s", self.name, exc)
            if isinstance(exc, AgentError):
                raise
            raise AgentError(f"{self.name} failed during '{self.action}': {exc}") from exc

        trace.record(
            AgentStep(
                agent=self.name,
                action=self.action,
                success=True,
                duration_ms=timer.elapsed_ms,
                summary=summary,
            )
        )
        self.logger.info("%s -> %s done in %.2fms: %s", self.name, self.action, timer.elapsed_ms, summary)
        return result

    # -----------------------------------------------------------------------
    # HOOKS  -- subclasses fill these in
    # -----------------------------------------------------------------------
    def _run(self, **kwargs: Any) -> tuple[Any, str]:
        """
        Do this agent's real work and return (structured_result, one_line_summary).

        MUST be overridden. The result should be one of the structured dataclasses
        from agents.utils (ExecutionPlan, ScenarioDecision, ...); the summary is a
        short human-readable line for the log and the trace.
        """
        raise NotImplementedError("Each agent must implement _run().")

    def _validate(self, result: Any) -> None:
        """
        Validate the produced object. The default rejects a None result; agents
        override to add their own rules (e.g. the Planner checks the optimizer is
        one of the four allowed values). Raise AgentValidationError to reject.
        """
        if result is None:
            raise AgentValidationError(f"{self.name} produced no result.")
