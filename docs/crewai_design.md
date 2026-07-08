# CrewAI Integration Design (Week 7)
Project: Supply Chain & Logistics Optimizer

The Week 7 orchestration layer runs in two modes (see
[`agent_orchestration.md`](agent_orchestration.md)): a **deterministic** default
that is always available, and an optional **CrewAI** mode that adds a
natural-language reasoning and narration layer on top. This document explains the
CrewAI integration in detail — what CrewAI is, how the crew is assembled, how the
tools seam works, and the one design decision that keeps the whole thing safe:
**the deterministic pipeline is always authoritative; CrewAI never overrides the
trusted numbers.**

---

## What is CrewAI? (zero-knowledge)

A **Large Language Model** (LLM) — think of the model behind a chat assistant —
can read a request in plain English and reason about it, but on its own it cannot
*do* anything: it only produces text. **CrewAI** is a small open-source framework
that turns one or more LLMs into a **crew of agents** that can cooperate and take
actions:

- An **Agent** is an LLM given a persona — a `role`, a `goal`, and a `backstory`
  — plus a set of **tools** it is allowed to call. The persona shapes how it
  behaves; the tools are the only real-world actions it can take.
- A **Task** is one unit of work assigned to an agent, with a `description` (what
  to do now) and an `expected_output` (what the answer should look like).
- A **Crew** runs several agents and tasks together. Ours runs them
  **sequentially** — Planner, then Scenario, then Optimization, then Evaluation,
  then Reporting — passing each task's result forward as context.

The important idea for this project: an LLM agent only affects the outside world
by **calling a tool**. If the only tools we give it call our tested Week 6
execution service, then no matter how the LLM reasons, the actual optimization
is always done by trusted code.

---

## Where the CrewAI code lives

```
agents/prompts.py   the role / goal / backstory of each of the five agents,
                    plus the task description + expected_output templates.
agents/tools.py     the ONLY seam to the platform; build_crew_tools() wraps the
                    same functions the deterministic path uses as CrewAI tools.
agents/crew.py      assembles real crewai.Agent / Task / Crew objects and runs them.
agents/config.py    settings + mode detection (which mode to use right now).
```

`agents/crew.py` is the only file that actually *imports* CrewAI, and it does so
lazily (see below). In the default deterministic mode it is never imported at all.

---

## Assembling the crew from prompts.py

The natural-language identity of each agent lives in `agents/prompts.py`, in
exactly the three pieces CrewAI wants:

- **ROLE** — the agent's title (e.g. *"Supply Chain Planning Strategist"*).
- **GOAL** — the single outcome it owns (e.g. *"turn a request into a structured
  execution plan… decide WHAT should happen — never perform the optimization
  yourself"*).
- **BACKSTORY** — a paragraph of context that shapes how it behaves. Every
  backstory is prefixed with a shared `CREW_CONTEXT` string that states the one
  rule keeping the architecture intact: *"Your job is to ORCHESTRATE that
  platform through the provided tools… You must NEVER try to solve the
  optimization yourself or bypass the tools."*

Keeping the wording in one file is the same discipline as keeping SQL out of
routers or magic numbers out of solvers: the prompt an LLM sees is a tuning
surface, so gathering the whole "crew charter" in one place lets you adjust tone
without touching the orchestration logic. Crucially, the **deterministic agents
follow exactly the same charter in code**, so the two modes are two
implementations of the *same* crew, not two different systems.

`agents/crew.py` reads those specs and builds five `crewai.Agent` objects:

```python
def make(spec, agent_tools):
    return Agent(
        role=spec["role"], goal=spec["goal"], backstory=spec["backstory"],
        tools=agent_tools, llm=llm,
        allow_delegation=False,                 # a clean, sequential crew
        max_execution_time=settings.crew_timeout_seconds,
    )
```

The Planner and Reporting agents reason and write, so they get **no tools**; the
Scenario, Optimization, and Evaluation agents get the platform tools. `build_tasks`
then creates five sequential `Task`s from the templates in `prompts.py`, filled
in with this run's request, plan, and scenario, and `build_full_crew` wires them
into a `Crew(process=Process.sequential)` ready to `kickoff()`.

---

## The tools pattern: the only seam to the platform

`agents/tools.py` is the single doorway through which any agent — deterministic
*or* LLM — touches the platform. It exposes three plain functions, each of which
calls the Week 6 execution service:

| Tool | Calls | Purpose |
|------|-------|---------|
| `get_scenario_catalog(ctx)` | `execution_service.list_scenarios()` | list the valid scenarios (so the Scenario agent can never invent one) |
| `run_optimization(ctx, …)` | `execution_service.run()` / `.simulate()` | run one optimization under a scenario — the heart of the orchestration |
| `run_benchmark(ctx, …)` | `execution_service.run_benchmark()` | run one optimizer across several scenarios and compare |

The deterministic agents call these functions directly. That is the whole seam:

```
agents  ->  tools.py  ->  Week 6 execution service  ->  Week 5 engine  ->  DB
```

### The `ToolContext` blackboard

One orchestration run shares a small `ToolContext` — a **blackboard** every tool
call reads and writes. It holds:

- `db` — the SQLAlchemy session to use. When the API drives the crew it passes
  the request's session straight through; when a script or the crew runs a tool
  with no session, the tool opens one short-lived `SessionLocal` and always
  closes it (the same open/use/close discipline as `api/database.get_db`, reusing
  the Week 3 wiring rather than re-creating it).
- `settings` — the Week 7 agent settings.
- `last_outcome` — where `run_optimization` stashes its **real, structured
  result**.
- `scenario_catalog` — the catalog, fetched once and cached for the run.

The blackboard is what makes the LLM mode trustworthy. In CrewAI mode the LLM
decides *when* to call a tool, and its final answer is prose — but each tool
still records its true structured result on the blackboard. So after the crew
finishes we **harvest trustworthy data from the blackboard** rather than trying
to parse numbers back out of the LLM's text.

### `build_crew_tools`: the same functions, wrapped for the LLM

For CrewAI mode, `build_crew_tools(ctx)` wraps those exact same functions as
LLM-callable tools, each closing over this run's blackboard:

```python
def build_crew_tools(ctx):
    from crewai.tools import tool           # imported lazily on purpose

    @tool("scenario_catalog")
    def scenario_catalog_tool():
        return get_scenario_catalog(ctx)

    @tool("run_optimization")
    def run_optimization_tool(optimizer, scenario="normal", warehouse_id=None, max_shipments=None):
        return run_optimization(ctx, optimizer=optimizer, scenario=scenario,
                                warehouse_id=warehouse_id, persist=True,
                                constraints={"max_shipments": max_shipments})
    ...
```

Because these wrappers delegate to the very same functions the deterministic path
uses, an LLM tool call runs against the correct session and records its result on
the correct blackboard — the numeric work is *identical* in both modes.

---

## Why every CrewAI import is lazy

`crewai` is a heavy, optional dependency with its own large tree. So the project
**never imports it at module top**. Every `crewai` import lives *inside* a
function:

- `agents/tools.py` imports `crewai.tools.tool` only inside `build_crew_tools()`.
- `agents/crew.py` imports `crewai`'s `Agent`, `Task`, `Crew`, `Process`, and
  `LLM` only inside the functions that build them, each guarded to raise a clear
  `AgentError` if the package is missing.
- `agents/coordinator.py` imports `agents.crew` itself lazily, only when it
  actually needs to narrate.

The result: `agents/tools.py`, `agents/config.py`, and the whole deterministic
pipeline **import cleanly whether or not CrewAI is installed**, and nothing about
CrewAI is pulled in unless the crew genuinely runs.

---

## Mode detection (config.py)

`agents/config.py` decides which mode to use *right now* without importing the
heavy package:

```python
def crewai_installed() -> bool:
    return importlib.util.find_spec("crewai") is not None   # LOOKS, does not import

def orchestration_mode(settings=None) -> str:
    s = settings or get_agent_settings()
    if s.enabled and crewai_installed() and s.has_api_key():
        return "crewai"
    return "deterministic"
```

The richer CrewAI mode is used only when **all three** are true:

1. the layer is **enabled** (`AGENT_ENABLED`, default `True`),
2. the `crewai` **package is installed**, and
3. the configured provider's **LLM API key is present**.

`find_spec` merely *looks* for the module on the import path; it never executes
it, so asking "which mode are we in?" is cheap and side-effect-free. A companion
`mode_explanation()` returns a human-readable reason (e.g. *"deterministic (no
LLM API key found in OPENAI_API_KEY)"*) for reports and logs, and
`GET /agents/status` surfaces all of this.

---

## LLM provider configuration

CrewAI talks to models through **LiteLLM**, a thin adapter that speaks to many
providers behind one interface. The Week 7 settings (`AgentSettings`, a
Pydantic-settings object read from `AGENT_*` environment variables) capture the
provider and model:

| Setting (env var) | Default | Meaning |
|-------------------|---------|---------|
| `AGENT_ENABLED` | `True` | master switch; `False` forces deterministic mode even if CrewAI + a key exist |
| `AGENT_LLM_PROVIDER` | `openai` | which provider (OpenAI is CrewAI's out-of-the-box default) |
| `AGENT_LLM_MODEL` | `gpt-4o-mini` | a small, inexpensive default — the orchestration prompts are short |
| `AGENT_LLM_TEMPERATURE` | `0.2` | low: an operations planner should be steady, not creative |
| `AGENT_VERBOSE` | `False` | print CrewAI's step-by-step reasoning to the console |
| `AGENT_CREW_TIMEOUT_SECONDS` | `120` | a hard ceiling so a misbehaving LLM can never hang a request |

The API key is read from the provider's conventional variable —
`OPENAI_API_KEY` for OpenAI, `ANTHROPIC_API_KEY` for Anthropic — via
`api_key_env()` / `has_api_key()`. LiteLLM wants the model as
`"<provider>/<model>"`, so `litellm_model()` composes e.g. `openai/gpt-4o-mini`
(and respects a provider prefix you write into `AGENT_LLM_MODEL` yourself). To
switch providers you set `AGENT_LLM_PROVIDER` and the matching key — no code
change.

Because none of these have to be set, the orchestrator runs with **no `.env` at
all**: it simply runs in the deterministic mode.

---

## The key design decision

> **The deterministic pipeline is always authoritative. CrewAI adds a
> natural-language reasoning and narration layer on top, and never overrides the
> trusted numbers.**

This is what makes it safe to integrate a non-deterministic LLM into a system
whose whole value is correct, reproducible optimization. Here is how the
Coordinator enforces it:

1. The Coordinator **first** runs the full deterministic five-agent pipeline.
   This produces the authoritative `OrchestrationResult` — the real plan,
   scenario, KPIs, and evaluation, all from the Week 6 execution service.
2. **Only if** the mode is `crewai` does it additionally call `run_crew(...)`.
   The crew receives the already-computed decision as **context** (embedded in
   the task descriptions with the explicit instruction *"do not contradict these
   numbers"*), reviews and explains it, and may call the same tools to run extra
   what-if checks. It returns a natural-language narrative.
3. That narrative is attached as `crew_narrative` on the result. It **enriches**
   the decision; it never replaces the numbers a program reads.

So a phone-charger holiday-peak decision produces the *same* KPIs whether or not
an LLM is configured. With an LLM, you additionally get a paragraph explaining,
in plain English, *why* the holiday scenario saturated the fleet and what a
manager should do about it.

---

## Graceful degradation

The CrewAI narration is strictly best-effort. The Coordinator calls it inside a
`try/except` that catches **anything** — a missing package, an LLM or network
error, a timeout, a bad key:

```python
def _maybe_narrate(self, ctx, request, result):
    try:
        from agents.crew import run_crew        # lazy import
        return run_crew(ctx, request=request, decision=result.as_dict(), settings=self.settings)
    except Exception as exc:
        self.logger.warning("CrewAI narration unavailable, continuing without it: %s", exc)
        return None
```

If narration fails for any reason, the Coordinator logs a warning and returns the
**deterministic result unchanged**, with `crew_narrative` simply left `None`. The
decision is never lost or corrupted by an LLM problem — which is exactly the
"use it if configured, else still work" pattern the whole project follows.

---

## Summary

CrewAI is integrated as a *genuine* orchestration framework — real `Agent`,
`Task`, and `Crew` objects, built from the personas in `prompts.py`, driving the
same tools — yet it is layered so that it can never become a correctness
dependency. The tested platform always does the maths; the LLM adds reasoning and
voice. Install `crewai` and set a key to turn it on; leave them out and the
system runs identically, minus the narrative.
