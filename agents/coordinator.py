"""
============================================================================
AGENT COORDINATOR  (Week 7)   -- the orchestrator that runs the whole crew
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THE COORDINATOR IS
-----------------------
  The single entry point of the Week 7 orchestration layer. Give it a user
  request and it drives the five agents, in order, to turn that request into a
  complete, recorded decision:

      request
        -> PlannerAgent       decide WHAT to run          (ExecutionPlan)
        -> ScenarioAgent      choose the operating scenario (ScenarioDecision)
        -> OptimizationAgent  run it via the execution service (OptimizationOutcome)
        -> EvaluationAgent    judge the KPIs + evaluation  (EvaluationSummary)
        -> ReportingAgent     write the report             (AgentReport)
        -> OrchestrationResult (everything + the execution trace)

  This IS the "CrewAI Agent Orchestrator" box in the Week 7 architecture. It
  sits below FastAPI and above the Week 6 execution service, exactly as the
  goals require:  User -> FastAPI -> Execution Service -> Coordinator -> agents
  -> Execution Service -> engine -> database.

THE TWO MODES (see agents/config.py)
------------------------------------
  The coordinator ALWAYS runs the deterministic five-agent pipeline. It is the
  authoritative path: tested, reproducible, offline, and it fully realises the
  Planner -> Scenario -> Optimization -> Evaluation -> Reporting architecture in
  plain code. The numbers it reports always come from the Week 6 execution
  service through the tools.

  When the richer "crewai" mode is active (crewai installed + an LLM key +
  enabled), the coordinator ADDITIONALLY runs a real CrewAI crew to produce a
  natural-language narrative of the decision (see crew.py). That narrative is
  attached as `crew_narrative`; it never replaces the deterministic numbers.
  This keeps correctness and offline testability while genuinely integrating
  CrewAI as the orchestration framework - the LLM adds reasoning and voice, the
  tested platform still does the maths. If the crew errors for any reason, the
  coordinator logs it and returns the deterministic result unchanged.

WHY THE PIPELINE IS RESILIENT
-----------------------------
  Each agent records a step in the shared ExecutionTrace (success or failure).
  If an agent raises, the coordinator captures it, marks the result
  unsuccessful, and still returns the trace and whatever was produced so far -
  an autonomous system should fail loudly and legibly, never silently.
============================================================================
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from agents.base_agent import AgentError
from agents.config import AgentSettings, get_agent_settings, mode_explanation, orchestration_mode
from agents.evaluation_agent import EvaluationAgent
from agents.optimization_agent import OptimizationAgent
from agents.planner_agent import PlannerAgent
from agents.reporting_agent import ReportingAgent
from agents.scenario_agent import ScenarioAgent
from agents.tools import ToolContext
from agents.utils import ExecutionTrace, OrchestrationResult, get_logger


class AgentCoordinator:
    """
    Orchestrates the five agents end to end and returns one OrchestrationResult.

    Holds no per-request state beyond the agent instances and the settings, so a
    single coordinator is safe to reuse across requests (each run gets its own
    ToolContext and ExecutionTrace).
    """

    def __init__(self, settings: AgentSettings | None = None) -> None:
        self.settings = settings or get_agent_settings()
        self.logger = get_logger("agents.Coordinator")
        # The five agents, instantiated once and reused (like the Week 4/5/6
        # service singletons).
        self.planner = PlannerAgent(self.settings)
        self.scenario = ScenarioAgent(self.settings)
        self.optimizer = OptimizationAgent(self.settings)
        self.evaluator = EvaluationAgent(self.settings)
        self.reporter = ReportingAgent(self.settings)

    # =======================================================================
    # PUBLIC: run one autonomous decision
    # =======================================================================
    def run(
        self,
        request: dict[str, Any] | None = None,
        *,
        db: Session | None = None,
        persist: bool = True,
        benchmark: bool = True,
    ) -> OrchestrationResult:
        """
        Drive the whole crew for one request and return the full result.

        `db` is the SQLAlchemy session to use (passed straight through by the
        API); when None, the tools open and close their own short-lived session.
        `persist` stores the optimization run (False = a throwaway what-if).
        `benchmark` lets the Evaluation agent compare a stressed scenario to
        "normal" operations.
        """
        request = request or {}
        mode = orchestration_mode(self.settings)
        detail = mode_explanation(self.settings)
        ctx = ToolContext(db=db, settings=self.settings)
        trace = ExecutionTrace()

        result = OrchestrationResult(request=request, mode=mode, mode_detail=detail)
        self.logger.info("orchestration starting in %s mode", mode)

        try:
            # ---- the authoritative deterministic pipeline --------------------
            plan = self.planner.execute(trace, request=request)
            scenario = self.scenario.execute(trace, ctx=ctx, request=request, plan=plan)
            outcome = self.optimizer.execute(
                trace, ctx=ctx, plan=plan, scenario=scenario, persist=persist
            )
            evaluation = self.evaluator.execute(
                trace, ctx=ctx, outcome=outcome, benchmark=benchmark
            )
            report = self.reporter.execute(
                trace,
                request=request,
                plan=plan,
                scenario=scenario,
                evaluation=evaluation,
                outcome=outcome,
                mode=mode,
                mode_detail=detail,
            )

            result.plan = plan.as_dict()
            result.scenario = scenario.as_dict()
            result.optimization = outcome.as_dict()
            result.evaluation = evaluation.as_dict()
            result.report = report.as_dict()
            result.success = outcome.success
            result.message = evaluation.headline

            # ---- optional LLM narration (crewai mode only) -------------------
            if mode == "crewai":
                result.crew_narrative = self._maybe_narrate(ctx, request, result)

        except AgentError as exc:
            # An agent failed. The trace already holds the failed step; surface a
            # clean, honest message rather than a stack trace.
            result.success = False
            result.message = f"Orchestration stopped: {exc}"
            self.logger.error("orchestration failed: %s", exc)
        finally:
            result.trace = trace.as_dict()

        return result

    def simulate(self, request: dict[str, Any] | None = None, **kwargs) -> OrchestrationResult:
        """A what-if: run exactly like run() but do NOT store the optimization."""
        kwargs["persist"] = False
        return self.run(request, **kwargs)

    # =======================================================================
    # CREWAI NARRATION  (best-effort; never breaks the deterministic result)
    # =======================================================================
    def _maybe_narrate(
        self, ctx: ToolContext, request: dict, result: OrchestrationResult
    ) -> str | None:
        """
        Ask the real CrewAI crew to narrate the decision. Imported lazily so the
        deterministic path never touches CrewAI, and wrapped so ANY failure
        (missing package, LLM/network error, timeout) degrades gracefully to no
        narrative - the deterministic result is always returned intact.
        """
        try:
            from agents.crew import run_crew  # lazy import - see crew.py header.

            return run_crew(ctx, request=request, decision=result.as_dict(), settings=self.settings)
        except Exception as exc:  # noqa: BLE001 - narration is strictly optional.
            self.logger.warning("CrewAI narration unavailable, continuing without it: %s", exc)
            return None


# A ready-to-use singleton, mirroring the Week 4/5/6 service singletons.
coordinator = AgentCoordinator()
