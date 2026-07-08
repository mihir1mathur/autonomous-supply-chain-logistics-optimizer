"""
============================================================================
OPTIMIZATION CONFIG  (Week 5)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  It holds the TUNABLE SETTINGS of the optimization engine: how long a solver
  may run, the winding factor used for distances, the simulated package-size
  range, the fleet utilization thresholds (what counts as "overloaded" or
  "under-utilized"), and the safety caps on how much work a single request may
  ask for. Each setting has a safe default, so the engine runs with no .env at
  all, and each can be overridden by an environment variable (prefixed OPT_).

WHY A SEPARATE CONFIG (the same reasoning as Weeks 3 and 4)
-----------------------------------------------------------
  Values that a user might reasonably want to change - a solver time limit, a
  utilization threshold - do not belong hidden inside the solver code. Keeping
  them in one typed settings object means one place to look and one place to
  change, and the numbers are validated at startup instead of failing weirdly
  deep inside a solve.

HOW IT WORKS (pydantic-settings, exactly like api/config.py)
------------------------------------------------------------
  APISettings in Week 4 used pydantic-settings' BaseSettings with the API_
  prefix. This mirrors that pattern with the OPT_ prefix, so the whole project
  configures the same way.
============================================================================
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class OptimizationSettings(BaseSettings):
    """
    All tunable optimization settings in one typed object.

    Pydantic reads each field from an environment variable with the OPT_
    prefix (e.g. OPT_SOLVER_TIME_LIMIT_SECONDS). If the variable is absent, the
    default written here is used. Bad values fail loudly at startup.
    """

    model_config = SettingsConfigDict(
        env_prefix="OPT_",
        env_file=".env",
        extra="ignore",  # ignore unrelated variables (DATABASE_*, API_*).
    )

    # ---- Solver limits ----------------------------------------------------
    # The maximum wall-clock time OR-Tools may spend on a single CP-SAT solve.
    # A limit guarantees an endpoint always returns promptly, even on a large,
    # hard instance - it returns the best solution found so far.
    solver_time_limit_seconds: float = 5.0
    # How many worker threads CP-SAT may use in parallel (0 = let it decide).
    solver_workers: int = 8

    # ---- Distance model (kept identical to Week 2) ------------------------
    # Straight-line (haversine) distances are scaled by this to approximate
    # real road distance. 1.30 is the value Week 2 used for delivery_routes.
    winding_factor: float = 1.30

    # ---- Simulated shipment size (see optimization/utils.py) --------------
    # The Olist data has no per-shipment package count, so we simulate one in
    # this range, deterministically from the shipment id. Tune to make the
    # capacity constraints looser (smaller) or tighter (larger).
    min_packages_per_shipment: int = 1
    max_packages_per_shipment: int = 10

    # ---- Fleet utilization thresholds -------------------------------------
    # A vehicle loaded above this fraction of its capacity is "overloaded"
    # (a stress signal), and below the lower one is "under-utilized" (wasteful).
    # These are REPORTING thresholds; the hard capacity limit is always 1.0.
    overloaded_utilization: float = 0.90
    underutilized_utilization: float = 0.30

    # ---- Safety caps (protect the server, like the API page-size cap) -----
    # The most shipments / stops / demands one optimization request may include.
    # A request asking for more is clamped to these so a single call can never
    # build an enormous, slow model.
    max_shipments_per_request: int = 300
    max_route_stops_per_request: int = 100
    max_warehouse_demands_per_request: int = 200

    # ---- Route optimization -----------------------------------------------
    # The default routing strategy. "nearest_neighbor" is the simple heuristic
    # implemented in Week 5; the interface is ready for a future VRP solver.
    default_route_strategy: str = "nearest_neighbor"


@lru_cache
def get_optimization_settings() -> OptimizationSettings:
    """
    Return the ONE shared optimization settings object.

    @lru_cache means the environment is read once and the result reused, rather
    than re-parsed on every solve. The service layer and the solvers both read
    settings through this function, which also makes it easy to override in
    tests later.
    """
    return OptimizationSettings()


# A module-level instance for code that just wants to read a value directly.
settings = get_optimization_settings()
