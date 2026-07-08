# AI Multi-Agent Orchestration Layer (Week 7)
Project: Supply Chain & Logistics Optimizer

Week 6 gave the project a complete optimization **execution layer**: one service
that takes a single request, runs a solver (optionally under a scenario),
measures twelve KPIs, evaluates the result against an un-optimized baseline, and
stores the run. Week 7 puts an **AI multi-agent orchestration layer** on **top**
of that: five specialised agents that read a plain-language request, decide
**what** should happen, drive the Week 6 service to make it happen, judge the
result, and write a report — turning the platform into an *autonomous supply
chain decision system*.

This document is the overview. Its two companions go deeper:
[`crewai_design.md`](crewai_design.md) (how the optional CrewAI/LLM mode is
wired) and [`agent_flow.md`](agent_flow.md) (one request walked end to end).

> **Everything in Week 7 is additive.** No Week 0–6 file is rewritten. The
> agents live in a new `agents/` package and a new `/agents/*` API namespace,
> and they **reuse the Week 6 execution service unchanged** — the agents never
> call OR-Tools, the solvers, or the database directly.

---

## The running example

Every week of this project follows one small story: **a customer orders a phone
charger**. Weeks 0–2 modelled the charger's journey (order → warehouse → packed
→ route → delivered). Week 3 stored it, Week 4 served it over HTTP, Week 5 built
the optimizers that decide *which van carries the charger and by what route*,
and Week 6 wrapped those optimizers so we could run a scenario, score it, and
save it. Week 7 asks the natural next question: instead of a human choosing the
optimizer and the scenario by hand, can the system take a sentence like *"optimize
deliveries for a holiday peak, we are short on vans"* and work the whole thing
out itself? That is what the agents do.

---

## Why an orchestration layer?

The Week 6 service is powerful but *low-level*: to use it you must already know
which of the four optimizers to call (`assignment`, `fleet`, `routes`,
`warehouse`), which of the eleven scenarios to run under, and which constraints
to pass. A planner who just wants to say *"we're slammed this holiday and short
on vans, sort out deliveries"* still has to translate that intent into precise
arguments.

An **agent** is a small, single-purpose decision-maker. Give each agent one job,
have them cooperate in a fixed order, and a vague request becomes a precise,
recorded decision — with a full audit trail of who decided what. That is the
orchestration layer: not new optimization power, but a **reasoning and
coordination layer** that turns intent into the right Week 6 call and explains
the outcome.

---

## The five agents (each with one job)

Each agent does exactly one thing and produces exactly one typed object, which
the next agent consumes. Keeping the jobs separate is what keeps the crew
legible: if a decision is wrong you can see it in one small object before
anything expensive runs.

| Agent | File | Its single job | Produces |
|-------|------|----------------|----------|
| **Planner** | `agents/planner_agent.py` | Decide **what** to run: which optimizer, which warehouse, what priority, which constraints. Never solves anything. | `ExecutionPlan` |
| **Scenario** | `agents/scenario_agent.py` | Choose **one existing Week 6 scenario** to run under (holiday, vehicle_breakdown, …). Never invents a scenario. | `ScenarioDecision` |
| **Optimization** | `agents/optimization_agent.py` | **Drive the Week 6 execution service** through the tool. The "hands" of the crew — thin on purpose. | `OptimizationOutcome` |
| **Evaluation** | `agents/evaluation_agent.py` | Read the 12 KPIs + before/after evaluation, form a **verdict**, optionally benchmark vs `normal`. Never recomputes numbers. | `EvaluationSummary` |
| **Reporting** | `agents/reporting_agent.py` | Write the **report** (markdown / json / text) with recommendations and future improvements. | `AgentReport` |

All five inherit a shared shell, `BaseAgent` (`agents/base_agent.py`), which
wraps each agent's real work (`_run`) in the same chores every time: log the
start, time it, catch and record any error, validate the produced object, and
write one entry into the run's execution trace. This is the same
**template-method** idea as the Week 4 `BaseService`: the shell lives in one
place, and each agent only fills in the hole.

---

## The Coordinator

The **Coordinator** (`agents/coordinator.py`) is the single entry point of the
layer. Give it a request and it runs the five agents in order, threading each
agent's output into the next, and returns one `OrchestrationResult` holding
every structured output plus the execution trace:

```
request
  -> PlannerAgent       decide WHAT to run            (ExecutionPlan)
  -> ScenarioAgent      choose the operating scenario  (ScenarioDecision)
  -> OptimizationAgent  run it via the execution service (OptimizationOutcome)
  -> EvaluationAgent    judge the KPIs + evaluation    (EvaluationSummary)
  -> ReportingAgent     write the report               (AgentReport)
  -> OrchestrationResult (everything + the trace + the mode)
```

The Coordinator holds no per-request state beyond the five agent instances and
the settings, so one singleton is reused across requests — each run gets its own
`ToolContext` and `ExecutionTrace`. If an agent raises, the Coordinator captures
it, marks the result unsuccessful, and **still returns the trace and whatever was
produced so far**: an autonomous system should fail loudly and legibly, never
silently.

---

## The layered architecture

The layering rule from Week 4 is preserved end to end — each layer only talks to
the next one down, and only the bottom of the stack touches the engine and the
database:

```
        User  (browser, dashboard, script, curl)
          │  POST /agents/decide  {"goal": "optimize deliveries for a holiday peak"}
          ▼
   api/routers/agents.py            THIN router (HTTP only)          [Week 7, new]
          ▼
   api/services/agent_service.py    the agent bridge service          [Week 7, new]
          ▼
   agents/coordinator.py            the ORCHESTRATOR (the "crew")      [Week 7, new]
          ▼
   Planner → Scenario → Optimization → Evaluation → Reporting         [Week 7, new]
          ▼
   agents/tools.py                  the ONLY seam to the platform      [Week 7, new]
          ▼
   api/services/execution_service.py   the Week 6 EXECUTION LAYER      [Week 6, reused]
          ▼
   optimization/*_solver.py            the Week 5 OR-Tools ENGINE      [Week 5, reused]
          ▼
   optimization_runs table  +  the Week 3 database (PostgreSQL)        [Week 3/6]
```

**The key architectural rule:** the agents *never* reach past `tools.py`. Every
capability they may use is exposed as a small named function in
`agents/tools.py`, and those functions call `execution_service.run()` /
`.simulate()` / `.run_benchmark()`. So the actual optimization is always done by
the trusted, tested Week 6 service — never re-implemented and never bypassed. The
agents orchestrate; the execution service owns the numbers.

---

## The two orchestration modes

Every earlier week runs **offline and deterministically**: the API starts with
no `.env`, the solvers are pure, and the validation scripts pass with no external
service. A Large Language Model (LLM) is the opposite — it needs an API key, a
network call, and it is not deterministic. So Week 7 supports **two modes** and
picks between them automatically (`agents/config.py`):

- **`deterministic`** — the **default**, always-available mode. The five agents
  run as a plain, rule-based pipeline: no LLM, no network, fully reproducible.
  This is what the demo and validation exercise, so the whole project keeps
  working out of the box. It is also the **authoritative** path — its numbers
  always come from the Week 6 execution service.
- **`crewai`** — the **optional**, richer mode. When the `crewai` package is
  installed **and** an LLM key is present **and** the layer is enabled, the same
  five agents are assembled into a real CrewAI crew that reasons in natural
  language over the **same** execution-service-backed tools, and adds a narrative
  on top of the trusted numbers.

**Why detection, not a hard dependency.** The layer *detects* whether CrewAI and
a key are available (using `importlib.util.find_spec`, which looks for the
package without importing its heavy dependency tree) and chooses the mode. This
mirrors the project's established "runs with no `.env`" pattern: the feature is
there when configured, and the project still works perfectly when it is not.
`agents/crew.py` is never even imported in the default mode. See
[`crewai_design.md`](crewai_design.md) for the full CrewAI integration.

---

## The `/agents/*` API endpoints

Week 5 owns `/optimize/*` (raw solvers); Week 6 owns `/optimization/*` (the
execution layer). Week 7 adds a **distinct `/agents/*` namespace** for the AI
layer, so the earlier weeks are untouched and the concerns never collide. The
router (`api/routers/agents.py`) is thin, exactly like every earlier router.

| Method & path | Purpose |
|---------------|---------|
| `GET /agents/status` | Describe the layer: current mode, whether CrewAI is installed, the configured LLM, and the agents/optimizers available. No database. |
| `POST /agents/decide` | Make one autonomous decision (plan → scenario → run → evaluate → report) and **store** the optimization run. |
| `POST /agents/simulate` | The same, but a throwaway **what-if** — the run is not stored. |

The request body is intentionally forgiving. The only field that really matters
is `goal` (free text); everything else is an optional override to pin down a
specific `optimizer`, `scenario`, `warehouse_id`, `priority`, or constraint. So
`POST /agents/decide` with `{"goal": "..."}` is enough, and `{}` runs a sensible
default — the same "empty body works" convention as Weeks 5 and 6.

> **Why `/decide` returns 200 even on a partial failure.** An autonomous decision
> always produces an auditable trace and (usually) a report, even if an agent
> could not complete. So the endpoint returns `200` with the full result plus a
> `success` flag and `message`, rather than a bare `4xx` — the caller reads
> `success` and inspects `trace` to see exactly what happened. (Malformed JSON in
> the body is still a clean `422` via the Week 4 validation handler.)

---

## The structured data contracts

The agents pass **typed dataclasses** down the pipeline rather than loose dicts,
exactly like the Week 5 solution models and the Week 6 `RunMetrics` /
`EvaluationResult`. A typed object documents the shape once, is trivial to build
and test, and turns into clean JSON with `as_dict()`. All of these live in
`agents/utils.py`, which imports nothing heavy (no CrewAI, FastAPI, database, or
OR-Tools), so it can be unit-tested in isolation.

| Contract | Produced by | Carries |
|----------|-------------|---------|
| `ExecutionPlan` | Planner | `optimizer`, `warehouse_id`, `priority`, `objective`, `constraints`, `rationale`, `steps` |
| `ScenarioDecision` | Scenario | `key`, `name`, `category`, `description`, `rationale` (the key is validated against the live Week 6 catalog) |
| `OptimizationOutcome` | Optimization | `optimizer`, `scenario`, `invoked`, `persisted`, `run_id`, `success`, and the full execution-service `result` dict |
| `EvaluationSummary` | Evaluation | `verdict` (improved/degraded/mixed/neutral), `headline`, `kpis` (the 12), `improvements` (evaluation %s), optional `benchmark`, `notes` |
| `AgentReport` | Reporting | `markdown`, `text`, `json`, `recommendations`, `future_improvements` |
| `OrchestrationResult` | Coordinator | `request`, `mode`, `mode_detail`, `success`, all five outputs as dicts, `trace`, optional `crew_narrative`, `message` |

### The execution trace

Alongside the decision, every run produces an **audit trail**. As each agent
finishes, `BaseAgent` records one `AgentStep` — which agent ran, its action,
whether it succeeded, how long it took (a `Timer` over `time.perf_counter`), a
one-line human summary, and any error. The `ExecutionTrace` gathers these steps
in order and exposes `total_ms` and `all_succeeded`.

```
AgentStep(agent="PlannerAgent",      action="build_execution_plan", success=True, duration_ms=…, summary="plan: assignment optimizer, priority=high, …")
AgentStep(agent="ScenarioAgent",     action="select_scenario",      success=True, …, summary="scenario 'holiday' (Holiday Peak) - inferred from …")
AgentStep(agent="OptimizationAgent", action="execute_optimization", success=True, …, summary="ran assignment/holiday via run -> success=True, …")
AgentStep(agent="EvaluationAgent",   action="evaluate_outcome",     success=True, …, summary="verdict=improved; …")
AgentStep(agent="ReportingAgent",    action="write_report",         success=True, …, summary="report written (… chars, … recommendation(s))")
```

This is what turns "the agents did something" into a story a human — or the
planned Week 8 dashboard — can follow after the fact.

---

## What is reused, unchanged

| From | Reused by Week 7 |
|------|------------------|
| Week 6 | the entire `execution_service` (`run` / `simulate` / `run_benchmark` / `list_scenarios`), the scenario catalog, the 12 KPIs, and the before-vs-after evaluation |
| Week 5 | the four OR-Tools solvers — reached only indirectly, through Week 6 |
| Week 4 | the thin-router rule, dependency-injected `get_db`, and the JSON error envelope |
| Week 3 | the SQLAlchemy models and the lazy engine/`SessionLocal` (the tool opens/closes its own session only when the API does not pass one) |

---

## Trying it

```bash
python database/init_db.py                    # ensure optimization_runs exists (Week 6)
uvicorn api.main:app --reload
# then, in the Swagger UI at /docs, or:
curl http://127.0.0.1:8000/agents/status
curl -X POST http://127.0.0.1:8000/agents/decide \
     -H "Content-Type: application/json" \
     -d '{"goal":"optimize deliveries for a holiday peak, we are short on vans"}'
curl -X POST http://127.0.0.1:8000/agents/simulate \
     -H "Content-Type: application/json" \
     -d '{"goal":"which warehouse should serve these orders?"}'

# or from Python, no server needed:
python -c "from agents import coordinator; print(coordinator.run({'goal':'optimize for a holiday peak'}).report['markdown'])"
```
