"""
============================================================================
WEEK 7 - AI MULTI-AGENT ORCHESTRATION DEMO
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SCRIPT DOES
---------------------
  A friendly walk-through of the Week 7 AI orchestration layer. It sends a few
  plain-language requests to the new /agents endpoints and prints what the crew
  decided - the plan, the scenario it chose, the KPIs it measured, its verdict,
  and the human-readable report it wrote. It is meant to be READ as much as run:
  it shows how one sentence ("optimize for a holiday peak") turns into a
  complete, recorded optimization decision, entirely by ORCHESTRATING the
  existing Week 6 execution service (never OR-Tools directly).

HOW THE REQUESTS ARE MADE
-------------------------
  Same as the Week 4/5/6 demos: the in-process FastAPI TestClient by default (no
  separate server needed), or a real running server if API_BASE_URL is set.

ORCHESTRATION MODE
------------------
  By default the crew runs in the DETERMINISTIC mode - no LLM, no network, fully
  reproducible - so this demo runs out of the box. If you install `crewai` and
  set an LLM API key (see .env.example), GET /agents/status will report the
  "crewai" mode and the decisions will additionally carry an LLM narrative.

PREREQUISITES
-------------
        pip install -r requirements.txt
        python database/init_db.py
        python notebooks/week3_load_database.py
        python notebooks/week7_agents_demo.py
============================================================================
"""

import os
import sys
import warnings

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*httpx.*")
warnings.filterwarnings("ignore", message=".*starlette.testclient.*")


def get_client():
    base_url = os.getenv("API_BASE_URL")
    if base_url:
        import httpx

        print(f"(using a real running server at {base_url})")
        return httpx.Client(base_url=base_url, timeout=180.0)

    from fastapi.testclient import TestClient

    from api.main import app

    print("(using the in-process TestClient - no separate server needed)")
    return TestClient(app)


def banner(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def show_decision(title, decision):
    """Print the headline pieces of one agent decision in a readable way."""
    plan = decision.get("plan", {})
    scenario = decision.get("scenario", {})
    opt = decision.get("optimization", {})
    ev = decision.get("evaluation", {})
    trace = decision.get("trace", {})

    print(f"\n--- {title} ---")
    print(f"  mode           : {decision.get('mode')} ({decision.get('mode_detail')})")
    print(f"  success        : {decision.get('success')}")
    print(f"  plan           : optimizer={plan.get('optimizer')} "
          f"priority={plan.get('priority')} warehouse={plan.get('warehouse_id') or 'auto'}")
    print(f"  scenario       : {scenario.get('key')} ({scenario.get('name')})")
    print(f"  run            : {'stored ' + str(opt.get('run_id')) if opt.get('persisted') else 'simulated'}"
          f"  invoked={opt.get('invoked')}")
    print(f"  verdict        : {ev.get('verdict')}  -  {ev.get('headline')}")
    if ev.get("benchmark"):
        b = ev["benchmark"]
        print(f"  vs 'normal'    : cost delta {b['cost_delta']}, "
              f"distance delta {b['distance_delta_km']} km, stockouts delta {b['stockouts_delta']}")
    print("  trace          :")
    for step in trace.get("steps", []):
        mark = "ok " if step["success"] else "FAIL"
        print(f"     [{mark}] {step['agent']:<18} {step['duration_ms']:>8.1f} ms  {step['summary'][:70]}")


def main():
    client = get_client()

    banner("STATUS  (which orchestration mode is active?)")
    status = client.get("/agents/status").json()
    print(f"  mode      : {status['orchestration_mode']}")
    print(f"  detail    : {status['mode_detail']}")
    print(f"  crewai    : installed={status['crewai_installed']}  "
          f"llm={status['llm_provider']} / {status['llm_model']}")
    print(f"  agents    : {', '.join(status['agents'])}")
    print(f"  optimizers: {', '.join(status['optimizers'])}")

    # 1) A plain-language request under an inferred, stressed scenario.
    banner("DECISION 1  (autonomous: a holiday peak, short on vans)")
    r = client.post(
        "/agents/decide",
        json={"goal": "optimize deliveries for a holiday peak, we are busy and short on vans",
              "max_shipments": 40},
    )
    d1 = r.json()
    show_decision("holiday peak (stored)", d1)

    # 2) An explicit fleet-balancing what-if (simulate = not stored).
    banner("DECISION 2  (what-if: balance the fleet under a vehicle breakdown)")
    r = client.post(
        "/agents/simulate",
        json={"optimizer": "fleet", "goal": "half our vehicles broke down, balance the rest",
              "max_shipments": 40},
    )
    d2 = r.json()
    show_decision("vehicle breakdown (simulated)", d2)

    # 3) A calm, normal-operations cost run - and print the full report.
    banner("DECISION 3  (normal operations, minimize cost) + full report")
    r = client.post(
        "/agents/decide",
        json={"goal": "minimize delivery cost for normal operations", "max_shipments": 30},
    )
    d3 = r.json()
    show_decision("normal cost run (stored)", d3)

    print("\n----- REPORTING AGENT: markdown report -----\n")
    print(d3["report"]["markdown"])

    print("\n----- REPORTING AGENT: recommendations -----")
    for rec in d3["report"]["recommendations"]:
        print(f"  * {rec}")

    banner("DONE")
    print("The crew turned three plain-language requests into three complete,")
    print("measured, recorded decisions - all by orchestrating the Week 6")
    print("execution service. No agent touched OR-Tools directly.")


if __name__ == "__main__":
    main()
