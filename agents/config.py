"""
============================================================================
AGENT CONFIG  (Week 7)   -- tunable settings for the AI ORCHESTRATION layer
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  Week 6 gave the project a full optimization EXECUTION LAYER (run a scenario,
  measure twelve KPIs, evaluate before-vs-after, store the run). Week 7 puts an
  AI MULTI-AGENT ORCHESTRATION LAYER on TOP of it: five specialised agents
  (Planner, Scenario, Optimization, Evaluation, Reporting) that decide WHAT
  should happen and drive the existing Week 6 execution service to make it
  happen. This file holds that layer's own handful of tunable settings.

  The settings live HERE, in one typed object, exactly like the Week 4 API
  config (api/config.py), the Week 5 optimization config (optimization/
  config.py) and the Week 6 execution config (optimization/execution_config.py).
  Keeping Week 7's knobs in their OWN file means none of the earlier configs is
  touched - this file is purely additive.

TWO WAYS THE ORCHESTRATOR CAN RUN (the key design decision of Week 7)
---------------------------------------------------------------------
  Every earlier week runs OFFLINE and DETERMINISTICALLY - the API starts with no
  .env, the solvers are pure, and the validation scripts pass with no external
  service. CrewAI, by contrast, needs a Large Language Model (an API key + a
  network call), which is neither offline nor deterministic. So Week 7 supports
  TWO orchestration modes and picks between them automatically:

    * "deterministic"  - the DEFAULT and always-available mode. The five agents
                         run as a plain, rule-based pipeline (no LLM, no network).
                         This is what the demo and the validation script exercise,
                         so the whole project keeps running out of the box.
    * "crewai"         - the OPTIONAL, richer mode. When the `crewai` package is
                         installed AND an LLM API key is present AND the layer is
                         enabled, the SAME five agents are assembled into a real
                         CrewAI crew that reasons in natural language over the
                         SAME execution-service-backed tools.

  Crucially, BOTH modes drive the platform through the identical Week 6 tools
  (see tools.py), so the numeric optimization work is always deterministic and
  correct - the LLM only adds reasoning and narration, it never touches OR-Tools.

WHY DETECTION, NOT A HARD DEPENDENCY
------------------------------------
  We DETECT whether CrewAI + a key are available (without importing the heavy
  package at module load) and choose the mode. That mirrors the project's
  established "runs with no .env" pattern: the feature is there when configured,
  and the project still works perfectly when it is not.
============================================================================
"""

from __future__ import annotations

import importlib.util
import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


# The environment variable that holds the API key for each supported provider.
# CrewAI talks to models through LiteLLM, so any provider LiteLLM supports works;
# these are the two this project documents (OpenAI is the default).
_PROVIDER_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


class AgentSettings(BaseSettings):
    """
    Week 7 orchestration-layer settings (LLM provider/model + behaviour switches).

    Pydantic reads each field from an environment variable with the AGENT_
    prefix (e.g. AGENT_LLM_PROVIDER, AGENT_LLM_MODEL). If a variable is absent,
    the default written here is used, so the orchestrator runs with no .env at
    all - it simply runs in the deterministic mode.
    """

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        extra="ignore",  # ignore unrelated variables (DATABASE_*, API_*, OPT_*).
    )

    # ---- Master switch -----------------------------------------------------
    # When False, the orchestrator ALWAYS uses the deterministic pipeline, even
    # if CrewAI and a key are available. Handy for reproducible demos and tests.
    enabled: bool = True

    # ---- LLM provider / model (only used in the "crewai" mode) -------------
    # The default provider is OpenAI (CrewAI's out-of-the-box default). Switch to
    # "anthropic" by setting AGENT_LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY.
    llm_provider: str = "openai"
    # A small, inexpensive default model - the orchestration prompts are short.
    # Override with AGENT_LLM_MODEL (e.g. "gpt-4o", or "claude-sonnet-5").
    llm_model: str = "gpt-4o-mini"
    # Low temperature: an operations planner should be steady, not creative.
    llm_temperature: float = 0.2

    # ---- CrewAI behaviour --------------------------------------------------
    # Print CrewAI's step-by-step reasoning to the console when the crew runs.
    verbose: bool = False
    # A hard ceiling on how long (seconds) we let a single crew kickoff run, so a
    # misbehaving LLM can never hang an API request forever.
    crew_timeout_seconds: int = 120

    # ---- Convenience helpers ----------------------------------------------
    def api_key_env(self) -> str:
        """The environment-variable name that holds this provider's API key."""
        return _PROVIDER_KEY_ENV.get(self.llm_provider.lower(), "OPENAI_API_KEY")

    def has_api_key(self) -> bool:
        """True if the configured provider's API key is set (and non-empty)."""
        return bool(os.getenv(self.api_key_env(), "").strip())

    def litellm_model(self) -> str:
        """
        The model string CrewAI/LiteLLM expects: "<provider>/<model>" so the
        right backend is chosen (e.g. "openai/gpt-4o-mini",
        "anthropic/claude-sonnet-5"). If the caller already wrote a provider
        prefix into AGENT_LLM_MODEL, we respect it as-is.
        """
        if "/" in self.llm_model:
            return self.llm_model
        return f"{self.llm_provider.lower()}/{self.llm_model}"


@lru_cache
def get_agent_settings() -> AgentSettings:
    """
    Return the ONE shared orchestration-layer settings object.

    @lru_cache means the environment is read once and reused, mirroring
    get_settings() (Week 4), get_optimization_settings() (Week 5) and
    get_execution_settings() (Week 6).
    """
    return AgentSettings()


# ===========================================================================
# ORCHESTRATION-MODE DETECTION  (does NOT import the heavy crewai package)
# ===========================================================================
def crewai_installed() -> bool:
    """
    True if the `crewai` package can be imported, WITHOUT importing it.

    importlib.util.find_spec only LOOKS for the module on the import path; it
    does not execute it. That keeps this cheap and side-effect-free, so simply
    asking "which mode are we in?" never drags in CrewAI's large dependency tree.
    """
    try:
        return importlib.util.find_spec("crewai") is not None
    except (ImportError, ValueError):
        return False


def orchestration_mode(settings: AgentSettings | None = None) -> str:
    """
    Decide which orchestration mode to use RIGHT NOW: "crewai" or "deterministic".

    We use the richer CrewAI mode only when ALL THREE are true:
      1. the layer is enabled (AGENT_ENABLED, default True),
      2. the crewai package is installed, and
      3. the configured provider's LLM API key is present.
    Otherwise we fall back to the deterministic pipeline, which is always
    available. This is the exact "use it if configured, else still work" pattern
    the rest of the project follows.
    """
    s = settings or get_agent_settings()
    if s.enabled and crewai_installed() and s.has_api_key():
        return "crewai"
    return "deterministic"


def mode_explanation(settings: AgentSettings | None = None) -> str:
    """A short, human-readable reason for the current mode (handy in reports/logs)."""
    s = settings or get_agent_settings()
    if not s.enabled:
        return "deterministic (AI orchestration disabled via AGENT_ENABLED=false)"
    if not crewai_installed():
        return "deterministic (the 'crewai' package is not installed)"
    if not s.has_api_key():
        return f"deterministic (no LLM API key found in {s.api_key_env()})"
    return f"crewai (LLM: {s.litellm_model()})"


# A module-level instance for code that just wants to read a value directly.
agent_settings = get_agent_settings()
