# Agent Orchestration Flow, End to End (Week 7)
Project: Supply Chain & Logistics Optimizer

This document walks **one request** through the entire Week 7 orchestration layer,
step by step, so you can see exactly how a plain sentence becomes a complete,
recorded optimization decision. It complements the overview
([`agent_orchestration.md`](agent_orchestration.md)) and the CrewAI design
([`crewai_design.md`](crewai_design.md)); read those first for the *what* and the
*why* — this is the *how, in sequence*.

Our example request, in plain English:

> **"Optimize deliveries for a holiday peak, we are short on vans."**

---

## The request enters

A caller sends it to the API:

```bash
curl -X POST http://127.0.0.1:8000/agents/decide \
     -H "Content-Type: application/json" \
     -d '{"goal":"optimize deliveries for a holiday peak, we are short on vans"}'
```

Following the Week 4 layering rule, the router (`api/routers/agents.py`) stays
HTTP-only: it validates the body against `AgentDecisionRequest`, then calls
`agent_service.decide(db, req.model_dump(), persist=True)`. The service
(`api/services/agent_service.py`) is deliberately tiny — it pulls the recognised
fields into a `request` dict and calls the Coordinator, passing the request's
**database session straight through** so every optimization the agents drive runs
on the same session as the rest of the HTTP request:

```
request = {"goal": "optimize deliveries for a holiday peak, we are short on vans"}
coordinator.run(request, db=db, persist=True, benchmark=True)
```

The Coordinator decides the mode (here, `deterministic` — no LLM configured),
creates a fresh `ToolContext` (the blackboard) carrying the session, and an empty
`ExecutionTrace`, then runs the five agents in order.

---

## Step 1 — Planner: decide WHAT to run

`PlannerAgent._run(request=…)` reads the free-text goal and produces an
`ExecutionPlan`. It reasons deterministically:

- **Optimizer** — no explicit `optimizer` was given, so it scans the wording for
  keywords. *"Optimize deliveries"* and being *"short on vans"* points at
  consolidating the load, so it defaults to `assignment` (fewer, fuller
  vehicles). (Had the goal said *"balance the vans"* it would pick `fleet`;
  *"which warehouse should serve…"* → `warehouse`; *"shortest route"* → `routes`.)
- **Priority** — no urgent words (*urgent, asap, critical…*), so `normal`.
- **Warehouse** — none named, so `None` (the execution service will auto-select).
- **Constraints** — none supplied, so `{}`.

```
ExecutionPlan(
    optimizer="assignment", warehouse_id=None, priority="normal",
    objective="minimize_cost_and_vehicles", constraints={},
    rationale="Chose the 'assignment' optimizer (inferred from the request
               wording) for an auto-selected warehouse, at normal priority …",
    steps=[ "Run the 'assignment' optimizer on an auto-selected warehouse",
            "Apply the operating scenario chosen by the Scenario Agent",
            "Measure the twelve KPIs and evaluate before-vs-after",
            "Report the outcome with recommendations" ])
```

`BaseAgent` validates the plan (the optimizer must be one of the four; the
priority one of two) and records a trace step. **The Planner never runs a solver
— it only decides intent.**

---

## Step 2 — Scenario: pick the existing Week 6 scenario

`ScenarioAgent._run(ctx=…, request=…, plan=…)` first calls the
`get_scenario_catalog` tool, which delegates to
`execution_service.list_scenarios()` — so the agent only ever chooses from
scenarios the platform actually implements; it **never invents one**. It then
matches the wording: *"holiday peak"* matches the `holiday` scenario's keywords.

```
ScenarioDecision(
    key="holiday", name="Holiday Peak", category="demand",
    description="demand × 1.6, keep 80% of fleet, fuel × 1.1",
    rationale="inferred from the request wording (matched 'holiday')")
```

Note how well this fits the request: the `holiday` scenario already models both a
demand surge **and** a reduced fleet — exactly *"a holiday peak, short on vans."*
The scenario's actual effects stay owned by Week 6's `scenarios.py`; this agent
only decides *which one* to use. Validated (non-empty key present in the live
catalog) and traced.

---

## Step 3 — Optimization: drive the Week 6 execution service

`OptimizationAgent._run(ctx=…, plan=…, scenario=…, persist=True)` is the "hands"
of the crew, and deliberately thin. It calls the `run_optimization` tool with the
plan's arguments:

```
run_optimization(ctx, optimizer="assignment", scenario="holiday",
                 warehouse_id=None, persist=True, constraints={})
```

That tool (`agents/tools.py`) opens/uses the shared session and calls
`execution_service.run(db, persist=True, optimizer="assignment",
scenario="holiday")`. The Week 6 service then does the whole heavy pipeline —
**exactly the work described in [`optimization_execution.md`](optimization_execution.md)**:

```
load real inputs from the DB  →  apply the 'holiday' scenario (demand ×1.6,
  keep 80% of fleet, fuel ×1.1)  →  solve with the Week 5 assignment solver  →
  measure the 12 KPIs  →  evaluate before-vs-after  →  store one optimization_runs row
```

The tool stashes the full result dict on the blackboard (`ctx.last_outcome`) and
returns it unchanged. The agent wraps it:

```
OptimizationOutcome(
    optimizer="assignment", scenario="holiday",
    invoked="execution_service.run", persisted=True,
    run_id="…", success=True, result={ run_id, metrics, evaluation, scenario_changes, … })
```

Validation here checks the result really contains `metrics`. **The agent never
touches OR-Tools, the solvers, or the database directly** — all of that is the
trusted Week 6/5 code.

---

## Step 4 — Evaluation: read the KPIs, form a verdict, benchmark

`EvaluationAgent._run(ctx=…, outcome=…, benchmark=True)` reuses the Week 6 numbers
verbatim — it **interprets**, it does not recompute. From the result it reads:

- the **12 KPIs** (`metrics`): total cost, travel distance, vehicle utilization,
  warehouse utilization, inventory holding cost, stockouts, late deliveries,
  orders fulfilled, runtime, solver status, model variables, model constraints;
- the **before-vs-after evaluation** (`evaluation`): the signed improvement
  percentages, where *positive always means better* (see
  [`evaluation_framework.md`](evaluation_framework.md)).

It weighs six improvement fields (cost, distance, stockouts, late deliveries,
utilization, delivery) against a small noise threshold (0.5 points) and forms a
**verdict**: `improved` if some improved and none worsened, `degraded` if the
reverse, `mixed` if both, `neutral` if neither. It writes a one-line `headline`
(preferring the framework's own summary) and raises **notes** for anything a
manager should watch — under `holiday` there will typically be stockouts (orders
that could not be served with a smaller fleet against higher demand) and at-risk
late deliveries (the fleet running hot).

Because the scenario is not `normal`, and `benchmark=True`, it also runs an
**optional benchmark**: it re-runs the *same* optimizer under `normal` as a
throwaway `simulate` (through the same tool), then reports the KPI deltas — *how
much did the holiday peak cost us versus ordinary operations?* It carefully
restores the original outcome on the blackboard afterward, so later readers still
see the real, stored run.

```
EvaluationSummary(
    verdict="mixed", headline="Mixed - …",
    kpis={…12 KPIs…}, improvements={…percentages…},
    benchmark={ reference_scenario:"normal", cost_delta:…, stockouts_delta:+12, … },
    notes=["12 order(s) could not be served under this scenario (stockouts) …",
           "38 delivery(ies) are flagged at risk of being late …"])
```

---

## Step 5 — Reporting: write the report + recommendations

`ReportingAgent._run(...)` takes everything the others decided and builds **one**
underlying JSON structure, then renders it three ways so it can serve three
audiences at once:

- **markdown** — headings, a KPI table, evaluation, benchmark, notes,
  recommendations (for a human);
- **text** — the same, plain, for logs and terminals;
- **json** — the structured object (for a program or the Week 8 dashboard).

Because all three render from the same data, they can never drift apart. It also
derives two action lists **from the actual outcome, not boilerplate**:

- **Recommendations** — keyed off the verdict and the KPIs: e.g. because there
  were stockouts, *"add fleet capacity, pre-position inventory, or run the
  'warehouse' optimizer to spread demand across more sites"*; because deliveries
  are at risk, *"run the 'fleet' optimizer to rebalance load off the over-full
  vehicles"*; and because the run was stored, *"compare it against past runs via
  GET /optimization/metrics."*
- **Future improvements** — e.g. feed the stored runs into a Week 8 dashboard;
  implement the reserved OR-Tools VRP routing strategy; let the crew trial
  several optimizers/scenarios and recommend the best. In deterministic mode it
  additionally suggests enabling the CrewAI LLM mode.

---

## The result

The Coordinator assembles everything into one `OrchestrationResult` and returns
it up through the service and router as JSON:

```
{ "mode": "deterministic",
  "success": true,
  "message": "Mixed - …",
  "plan":        { optimizer:"assignment", priority:"normal", … },
  "scenario":    { key:"holiday", name:"Holiday Peak", … },
  "optimization":{ run_id:"…", persisted:true, success:true, result:{…} },
  "evaluation":  { verdict:"mixed", kpis:{…}, benchmark:{…}, notes:[…] },
  "report":      { markdown:"…", text:"…", json:{…}, recommendations:[…] },
  "trace":       { steps:[5 AgentSteps], total_ms:…, all_succeeded:true },
  "crew_narrative": null }
```

`POST /agents/simulate` runs identically but with `persist=False`, so the run is
computed and reported but **not stored** — a safe what-if.

---

## How it maps to the Week 7 architecture

Each step above is one hop down the layered diagram from
[`agent_orchestration.md`](agent_orchestration.md):

```
User  ──►  /agents/decide  ──►  agent_service  ──►  Coordinator
                                                       │
   ┌───────────────────────────────────────────────────┘
   ▼
 Planner ──► Scenario ──► Optimization ──► Evaluation ──► Reporting
   (plan)     (scenario)      │  (via tools.py)  ▲            │
                              ▼                  │            ▼
                      execution_service.run  ────┘        OrchestrationResult
                              │                              (+ trace)
                              ▼
                      Week 5 OR-Tools engine  ──►  optimization_runs (DB)
```

The trace records one `AgentStep` per box in the middle row, so the finished
decision carries its own audit trail:

```
PlannerAgent      build_execution_plan  ok  "plan: assignment optimizer, priority=normal, warehouse=auto, 0 constraint(s)"
ScenarioAgent     select_scenario       ok  "scenario 'holiday' (Holiday Peak) - inferred from the request wording"
OptimizationAgent execute_optimization  ok  "ran assignment/holiday via run -> success=True, status=OPTIMAL, run_id=…"
EvaluationAgent   evaluate_outcome      ok  "verdict=mixed; Mixed - …"
ReportingAgent    write_report          ok  "report written (… chars, 4 recommendation(s))"
```

---

## A concrete narrated example

Running the assignment optimizer under `holiday` on a busy warehouse (drawing on
the representative numbers in [`scenario_execution.md`](scenario_execution.md)):

> The Planner reads *"holiday peak, short on vans"* and plans a **cost/consolidation
> (`assignment`)** run. The Scenario agent matches this to the existing **`holiday`**
> scenario — demand × 1.6, only 80% of the fleet, fuel × 1.1 — a perfect fit for
> "peak plus fewer vans." The Optimization agent presses the button: the Week 6
> service loads the data, applies those effects, solves, and stores the run. The
> Evaluation agent reads the KPIs — utilization pinned at **100%**, **12 orders
> become stockouts**, **38 deliveries at risk of being late** — and, benchmarking
> against `normal`, reports that the holiday peak turned a comfortable 75%-utilized,
> zero-stockout day into a saturated one. Verdict: **mixed** (the plan carries what
> it can as cheaply as possible, but demand simply exceeds the reduced fleet). The
> Reporting agent writes it up and recommends **adding fleet capacity or
> pre-positioning inventory before the peak** — a decision a planner can act on
> today, produced end to end from one sentence.

With the CrewAI mode enabled (see [`crewai_design.md`](crewai_design.md)), the
*same* numbers are produced, and a `crew_narrative` paragraph is attached
explaining the trade-off in natural language — the LLM never changes the figures.

---

## Tying it back — and forward

**Back to Weeks 0–6 (the phone charger journey).** The charger the customer
ordered in Week 0 was modelled (Week 2), stored (Week 3), served over HTTP
(Week 4), and had its van and route optimized (Week 5) and scored under scenarios
(Week 6). Week 7 is the layer that finally lets someone *ask, in plain words*,
for that optimization to happen for a whole holiday's worth of chargers — and get
back not just numbers but a reasoned, recorded decision. Every charger still
flows through the exact same tested pipeline; the agents just decide which button
to press and explain the result.

**Forward to Week 8 (monitoring dashboards).** Every `/agents/decide` run stores
an `optimization_runs` row (Week 6) and produces a structured JSON report and
trace (Week 7). Week 8 will build monitoring dashboards over those stored runs —
charting KPIs, verdicts, and evaluations across many autonomous decisions over
time. That is exactly why the Reporting agent emits a machine-ingestible `json`
rendering and lists a dashboard as its first future improvement: the data the
next week needs is already being written, in the right shape, today.
