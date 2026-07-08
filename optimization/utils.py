"""
============================================================================
OPTIMIZATION UTILITIES  (Week 5)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE HOLDS
--------------------
  The small, dependency-free helpers the optimization engine reuses
  everywhere: measuring distance between two points on Earth (haversine),
  timing how long a solve takes, and a couple of safe-maths helpers so a
  divide-by-zero can never crash a solver.

WHY A SEPARATE UTILS FILE (and why it imports almost nothing)
-------------------------------------------------------------
  These functions are PURE: given the same inputs they always return the
  same output, they touch no database, and they know nothing about FastAPI or
  OR-Tools. That makes them trivial to test on their own and safe for every
  other optimization module to import without creating circular dependencies.

THE HAVERSINE DISTANCE (reused from Week 2)
-------------------------------------------
  The Week 2 route generator estimated distances with the haversine formula
  (great-circle distance between two latitude/longitude points) multiplied by
  a "winding factor" so a straight-line distance better reflects real roads.
  We reuse the SAME formula and the SAME default winding factor here so the
  optimizer and the stored Week 2 estimates speak the same language.
============================================================================
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

# Mean radius of the Earth in kilometres. Used by the haversine formula.
EARTH_RADIUS_KM = 6371.0088

# Default "winding factor": real roads are longer than a straight line, so we
# scale the great-circle distance up. 1.30 is the SAME value Week 2 used when
# it generated delivery_routes.estimated_distance_km, so estimates line up.
DEFAULT_WINDING_FACTOR = 1.30


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Return the great-circle distance (in kilometres) between two points given
    as latitude/longitude in decimal degrees.

    "Great-circle" means the shortest distance over the surface of a sphere -
    the distance a bird would fly. This is a STRAIGHT-LINE estimate; multiply
    it by a winding factor (see straight_line_to_road_km) to approximate the
    longer distance a vehicle actually drives.

    If any coordinate is missing (None), we return 0.0 rather than crashing,
    so a row with incomplete location data cannot break a whole solve.
    """
    if None in (lat1, lon1, lat2, lon2):
        return 0.0

    # Convert degrees to radians because Python's trig functions use radians.
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))

    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1

    # The haversine formula itself.
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return EARTH_RADIUS_KM * c


def straight_line_to_road_km(
    straight_km: float,
    winding_factor: float = DEFAULT_WINDING_FACTOR,
) -> float:
    """
    Turn a straight-line (haversine) distance into an estimated ROAD distance
    by multiplying by the winding factor. Identical idea to Week 2.
    """
    return straight_km * winding_factor


def road_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    winding_factor: float = DEFAULT_WINDING_FACTOR,
) -> float:
    """
    Convenience: haversine distance already scaled to an estimated road
    distance. This is the distance the optimizer reasons about.
    """
    return straight_line_to_road_km(
        haversine_km(lat1, lon1, lat2, lon2), winding_factor
    )


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Divide, but return `default` instead of raising when the denominator is 0.
    Utilization and average calculations use this so an empty fleet or an
    empty result set can never cause a divide-by-zero.
    """
    if not denominator:
        return default
    return numerator / denominator


def as_percent(fraction: float, digits: int = 1) -> float:
    """Turn a 0..1 fraction into a rounded 0..100 percentage."""
    return round(fraction * 100.0, digits)


def simulated_package_demand(
    shipment_id: str,
    min_packages: int = 1,
    max_packages: int = 10,
) -> int:
    """
    Return a STABLE, SIMULATED package count for one shipment.

    WHY THIS EXISTS
      The real Olist dataset records an order but NOT how many packages each
      delivery is (there is no per-shipment package count in our tables). The
      vehicle-capacity constraints only become meaningful if each shipment has
      a size, so - exactly like the Week 2 simulation filled real gaps with
      documented assumptions - we derive a small, deterministic demand from the
      shipment id.

    HOW IT IS DETERMINISTIC
      We hash the id into the range [min_packages, max_packages]. The same id
      always yields the same demand, so runs are reproducible (no randomness),
      yet different shipments get different sizes so the packing/assignment is
      non-trivial. This is clearly SIMULATED, never presented as real data.
    """
    span = max_packages - min_packages + 1
    if span <= 0:
        return min_packages
    # A simple, stable hash: sum of character codes. Deterministic across runs
    # (Python's built-in hash() is salted per-process, so we avoid it here).
    digest = sum(ord(ch) for ch in str(shipment_id))
    return min_packages + (digest % span)


@dataclass
class Timer:
    """
    A tiny stopwatch used to report how long a solve took.

    Usage:
        with Timer() as t:
            ... do the optimization ...
        print(t.elapsed_ms)

    We use time.perf_counter (a high-resolution, monotonic clock) because it is
    the right tool for measuring durations - it never jumps backwards the way a
    wall-clock can.
    """

    elapsed_ms: float = 0.0
    _start: float = 0.0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc_info) -> None:
        self.elapsed_ms = round((time.perf_counter() - self._start) * 1000.0, 3)
