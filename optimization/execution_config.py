"""
============================================================================
EXECUTION CONFIG  (Week 6)   -- tunable settings for the EXECUTION layer
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  Week 5 gave the project an optimization ENGINE (optimization/config.py holds
  its solver settings). Week 6 wraps that engine in an EXECUTION LAYER that
  runs optimizations, measures performance (KPIs), evaluates before-vs-after,
  and persists every run. That layer needs a few extra tunable numbers of its
  own - how much it costs to hold a unit of stock for a period, the default
  per-km rate used when a plan has no vehicle rate, and the utilization above
  which a delivery is flagged "at risk of being late".

  Those numbers live HERE, in one typed settings object, exactly like the Week
  4 API config (api/config.py) and the Week 5 optimization config
  (optimization/config.py). Keeping Week 6's tunables in their OWN file means
  the Week 5 config is never touched - this file is purely additive.

WHY A SECOND SETTINGS OBJECT (and not editing optimization/config.py)
---------------------------------------------------------------------
  The project's rule is that each week is ADDITIVE and never rewrites earlier
  work. optimization/config.py belongs to Week 5 and stays exactly as it was.
  This file adds the Week 6 knobs alongside it. Both read from the same .env
  with the shared OPT_ prefix; `extra="ignore"` lets each object ignore the
  other's variables, so they coexist cleanly.

HONESTY ABOUT SIMULATED COSTS (same discipline as Week 2)
---------------------------------------------------------
  The Olist data has no accounting figures - no holding cost, no fuel price.
  These rates are therefore SIMULATED assumptions (documented, with sensible
  defaults), never presented as real data. They exist so the KPIs have
  meaningful, comparable units, in keeping with the project's real-vs-simulated
  discipline. The per-km default (1.20) matches the rate Week 2 used to compute
  delivery_routes.estimated_cost, so the numbers line up with the stored data.
============================================================================
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ExecutionSettings(BaseSettings):
    """
    Week 6 execution-layer settings (KPI pricing + reporting thresholds).

    Pydantic reads each field from an environment variable with the OPT_ prefix
    (e.g. OPT_INVENTORY_HOLDING_COST_PER_UNIT). If the variable is absent, the
    default written here is used, so the execution layer runs with no .env.
    """

    model_config = SettingsConfigDict(
        env_prefix="OPT_",
        env_file=".env",
        extra="ignore",  # ignore unrelated variables (DATABASE_*, API_*, other OPT_*).
    )

    # ---- KPI pricing (SIMULATED, documented) ------------------------------
    # The per-km cost used to price a plan when a vehicle has no cost_per_km of
    # its own (e.g. warehouse selection and route optimization do not carry a
    # vehicle). 1.20 matches the rate Week 2 used for estimated_cost.
    default_cost_per_km: float = 1.20
    # The cost of holding ONE unit of stock for the reporting period. Inventory
    # holding cost = stock on hand * this rate. A simulated accounting figure.
    inventory_holding_cost_per_unit: float = 0.10

    # ---- Late-delivery proxy (a reporting threshold) ----------------------
    # This project has no live delivery clock, so "late deliveries" is a
    # documented PROXY: a shipment carried on a vehicle loaded above this
    # fraction of capacity is flagged "at risk of being late" (a stressed,
    # over-full vehicle is the operational signal of lateness). Defaults to the
    # same 0.90 Week 5 uses for "overloaded" so the two ideas agree.
    late_delivery_load_threshold: float = 0.90


@lru_cache
def get_execution_settings() -> ExecutionSettings:
    """
    Return the ONE shared execution-layer settings object.

    @lru_cache means the environment is read once and reused, mirroring
    get_settings() (Week 4) and get_optimization_settings() (Week 5).
    """
    return ExecutionSettings()


# A module-level instance for code that just wants to read a value directly.
execution_settings = get_execution_settings()
