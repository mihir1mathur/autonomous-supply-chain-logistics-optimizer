"""
============================================================================
CREWAI CREW  (Week 7)   -- the real CrewAI assembly (optional LLM layer)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE IS
-----------------
  This is where the project actually MEETS CrewAI. It assembles the five agents
  into a genuine CrewAI Crew - five crewai.Agent objects (built from the
  role/goal/backstory in prompts.py), each given the execution-service-backed
  tools from tools.py, wired to an LLM, and run as a sequential process.

  It is used ONLY in the optional "crewai" orchestration mode (see config.py):
  when the crewai package is installed, an LLM API key is present, and the layer
  is enabled. In the default deterministic mode this file is never imported, so
  the whole project keeps running with no CrewAI and no LLM.

WHY EVERY IMPORT OF CREWAI IS LAZY
----------------------------------
  `crewai` is a heavy dependency with its own large tree, and it is optional.
  So we NEVER import it at module top - every crewai import lives INSIDE a
  function, guarded, and raises a clear error if the package is missing. That is
  why coordinator.py imports THIS module lazily too: nothing about CrewAI is
  pulled in unless the crew genuinely runs.

HOW IT RELATES TO THE DETERMINISTIC RESULT
------------------------------------------
  The coordinator has ALREADY produced the authoritative, deterministic decision
  (the real numbers, from the Week 6 execution service) before this crew runs.
  The crew's job here is to add the LLM REASONING/NARRATION layer: it receives
  that decision as context, can call the same tools to run additional what-if
  checks if it wishes, and returns a natural-language narrative. The crew never
  overrides the trusted numbers - it explains and enriches them. This is how
  CrewAI is integrated as the orchestration framework without letting a
  non-deterministic LLM become a correctness dependency.
============================================================================
"""

from __future__ import annotations

import json
from typing import Any

from agents.base_agent import AgentError
from agents.config import AgentSettings, get_agent_settings
from agents import prompts
from agents.tools import ToolContext, build_crew_tools
from agents.utils import get_logger

_logger = get_logger("agents.crew")


# ===========================================================================
# LLM WIRING  (provider/model from the Week 7 settings)
# ===========================================================================
def _make_llm(settings: AgentSettings):
    """
    Build a CrewAI LLM from the configured provider/model. CrewAI talks to
    models through LiteLLM, so the model string is "<provider>/<model>" (see
    AgentSettings.litellm_model). Imported lazily; raises a clear AgentError if
    CrewAI is not installed.
    """
    try:
        from crewai import LLM  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - exercised only without crewai.
        raise AgentError("CrewAI is not installed; cannot build the LLM.") from exc
    return LLM(model=settings.litellm_model(), temperature=settings.llm_temperature)


# ===========================================================================
# BUILD THE FIVE CREWAI AGENTS  (from prompts.py + the shared tools)
# ===========================================================================
def build_agents(ctx: ToolContext, settings: AgentSettings) -> dict:
    """
    Create the five crewai.Agent objects, each with its role/goal/backstory and
    the execution-service-backed tools. Returns them keyed by short name so the
    task builder can wire tasks to the right agent.
    """
    from crewai import Agent  # noqa: PLC0415

    llm = _make_llm(settings)
    tools = build_crew_tools(ctx)  # the SAME tools the deterministic path uses.

    def make(spec: dict, agent_tools: list) -> Any:
        return Agent(
            role=spec["role"],
            goal=spec["goal"],
            backstory=spec["backstory"],
            tools=agent_tools,
            llm=llm,
            verbose=settings.verbose,
            allow_delegation=False,          # a clean, sequential crew.
            max_execution_time=settings.crew_timeout_seconds,
        )

    # The Planner and Reporting agents reason/write and need no tools; the
    # Scenario, Optimization and Evaluation agents drive the platform.
    return {
        "planner": make(prompts.PLANNER, []),
        "scenario": make(prompts.SCENARIO, tools),
        "optimization": make(prompts.OPTIMIZATION, tools),
        "evaluation": make(prompts.EVALUATION, tools),
        "reporting": make(prompts.REPORTING, []),
    }


# ===========================================================================
# BUILD THE TASKS  (fed the already-computed decision as context)
# ===========================================================================
def build_tasks(agents: dict, request: dict, decision: dict) -> list:
    """
    Create the five sequential CrewAI Tasks. Each task's description is filled in
    from prompts.py with this run's request/plan/scenario. The tasks are told the
    platform has already produced `decision` (the deterministic result), so the
    crew reviews and narrates rather than blindly re-running everything.
    """
    from crewai import Task  # noqa: PLC0415

    plan = decision.get("plan", {})
    scenario = decision.get("scenario", {})
    context_note = (
        "\n\nCONTEXT - the platform has already executed this decision "
        "deterministically; here is the authoritative result to review and "
        "explain (do not contradict these numbers):\n"
        + json.dumps(decision, indent=2)[:6000]
    )

    planner_task = Task(
        description=prompts.PLANNER_TASK.format(request=request),
        expected_output=prompts.PLANNER_OUTPUT,
        agent=agents["planner"],
    )
    scenario_task = Task(
        description=prompts.SCENARIO_TASK.format(request=request, plan=plan),
        expected_output=prompts.SCENARIO_OUTPUT,
        agent=agents["scenario"],
    )
    optimization_task = Task(
        description=prompts.OPTIMIZATION_TASK.format(
            optimizer=plan.get("optimizer"),
            scenario=scenario.get("key"),
            warehouse_id=plan.get("warehouse_id"),
            constraints=plan.get("constraints"),
        )
        + context_note,
        expected_output=prompts.OPTIMIZATION_OUTPUT,
        agent=agents["optimization"],
    )
    evaluation_task = Task(
        description=prompts.EVALUATION_TASK + context_note,
        expected_output=prompts.EVALUATION_OUTPUT,
        agent=agents["evaluation"],
    )
    reporting_task = Task(
        description=prompts.REPORTING_TASK,
        expected_output=prompts.REPORTING_OUTPUT,
        agent=agents["reporting"],
    )
    return [planner_task, scenario_task, optimization_task, evaluation_task, reporting_task]


# ===========================================================================
# BUILD + RUN THE FULL CREW
# ===========================================================================
def build_full_crew(ctx: ToolContext, request: dict, decision: dict, settings: AgentSettings):
    """
    Assemble the genuine five-agent CrewAI Crew (sequential process). This is the
    "CrewAI Agent Orchestrator" of the Week 7 architecture, expressed in CrewAI's
    own objects. Returns a Crew ready to kickoff().
    """
    from crewai import Crew, Process  # noqa: PLC0415

    agents = build_agents(ctx, settings)
    tasks = build_tasks(agents, request, decision)
    return Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=settings.verbose,
    )


def run_crew(
    ctx: ToolContext,
    *,
    request: dict,
    decision: dict,
    settings: AgentSettings | None = None,
) -> str:
    """
    Run the full CrewAI crew and return its final natural-language output as the
    decision narrative.

    Called only by the coordinator in "crewai" mode, inside a try/except - so if
    the LLM or network fails, the coordinator simply returns the deterministic
    result with no narrative. The crew shares this run's ToolContext, so any
    tool calls it makes go through the same execution service and session.
    """
    settings = settings or get_agent_settings()
    _logger.info("running CrewAI crew (model=%s)", settings.litellm_model())
    crew = build_full_crew(ctx, request, decision, settings)
    output = crew.kickoff()
    # CrewAI returns a CrewOutput object; str() gives the final task's text.
    return str(output)
