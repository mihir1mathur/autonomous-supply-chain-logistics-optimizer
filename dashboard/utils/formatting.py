"""
============================================================================
FORMATTING HELPERS  (Week 8)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  Turns raw values from the API into clean, human-friendly strings for the UI.
  It is PURE Python - no Streamlit, no backend, no pandas - so it imports
  anywhere and is easy to test (the Week 8 validation calls these directly).

THE ONE FORMATTING RULE THAT MATTERS MOST (Week 8, Part 5)
----------------------------------------------------------
  The backend stores VEHICLE / WAREHOUSE UTILIZATION as a FRACTION in 0..1
  (e.g. 0.767 means 76.7%). A dashboard must NEVER show "0.77" to a human - it
  shows "76.7%". So there are two distinct percent helpers, and picking the
  right one is deliberate:

    fraction_to_percent(0.767)   -> "76.7%"   (value is a 0..1 fraction)
    format_percent_value(27.5)   -> "27.5%"   (value is ALREADY a percent, e.g.
                                                the Week 6 evaluation numbers)

  Getting these two mixed up is the classic dashboard bug, so they are named
  unambiguously and documented here in one place.

IMPORTANT: FORMATTING IS NOT COMPUTATION
  These helpers only re-present numbers the backend already produced. They never
  add, average, or otherwise derive a KPI - that would break the Week 8 rule
  that the dashboard does not compute metrics.
============================================================================
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# A placeholder currency symbol for the (simulated) cost figures. The costs in
# this project are simulated planning numbers, not real Olist money, so the
# symbol is purely cosmetic and kept in one place.
CURRENCY_SYMBOL = "$"

# What to show when a value is missing (None) - a dash reads better than "None".
MISSING = "-"


# ===========================================================================
# NUMBERS
# ===========================================================================
def format_number(value: Any, decimals: int = 2) -> str:
    """
    Format a number with thousands separators and fixed decimals.

    format_number(1234.5)      -> "1,234.50"
    format_number(1234.5, 0)   -> "1,235"
    A None (or non-numeric) value becomes the MISSING dash.
    """
    number = _to_float(value)
    if number is None:
        return MISSING
    return f"{number:,.{decimals}f}"


def format_int(value: Any) -> str:
    """Format an integer with thousands separators (None -> dash)."""
    number = _to_float(value)
    if number is None:
        return MISSING
    return f"{int(round(number)):,}"


def format_currency(value: Any, decimals: int = 2) -> str:
    """
    Format a (simulated) cost as money: format_currency(1234.5) -> "$1,234.50".
    """
    number = _to_float(value)
    if number is None:
        return MISSING
    return f"{CURRENCY_SYMBOL}{number:,.{decimals}f}"


def format_distance_km(value: Any, decimals: int = 1) -> str:
    """Format a distance in kilometres: format_distance_km(12.34) -> '12.3 km'."""
    number = _to_float(value)
    if number is None:
        return MISSING
    return f"{number:,.{decimals}f} km"


# ===========================================================================
# PERCENTAGES  (see the big note at the top - two distinct helpers)
# ===========================================================================
def fraction_to_percent(value: Any, decimals: int = 1) -> str:
    """
    Turn a 0..1 FRACTION into a percentage string.

    fraction_to_percent(0.767) -> "76.7%".  Use this for utilization values,
    which the backend stores as fractions.
    """
    number = _to_float(value)
    if number is None:
        return MISSING
    return f"{number * 100:.{decimals}f}%"


def format_percent_value(value: Any, decimals: int = 1, signed: bool = False) -> str:
    """
    Format a value that is ALREADY a percent (e.g. the Week 6 evaluation numbers
    like cost_reduction_percent = 27.5).

    format_percent_value(27.5)              -> "27.5%"
    format_percent_value(27.5, signed=True) -> "+27.5%"   (nice for improvements)
    format_percent_value(-4.0, signed=True) -> "-4.0%"
    """
    number = _to_float(value)
    if number is None:
        return MISSING
    if signed:
        return f"{number:+.{decimals}f}%"
    return f"{number:.{decimals}f}%"


# ===========================================================================
# TIME
# ===========================================================================
def format_ms(value: Any) -> str:
    """
    Format a millisecond duration, switching to seconds when it is large.

    format_ms(42.5)    -> "42.5 ms"
    format_ms(2500)    -> "2.50 s"
    """
    number = _to_float(value)
    if number is None:
        return MISSING
    if number >= 1000:
        return f"{number / 1000:.2f} s"
    return f"{number:.1f} ms"


def format_datetime(value: Any) -> str:
    """
    Format an ISO timestamp (or datetime) as a readable local-style string.

    format_datetime("2026-07-08T12:34:56+00:00") -> "2026-07-08 12:34:56 UTC".
    Anything unparseable is returned as-is (never raises), so a surprising value
    still shows something rather than crashing the page.
    """
    if value is None or value == "":
        return MISSING
    dt = _to_datetime(value)
    if dt is None:
        return str(value)
    suffix = " UTC" if dt.tzinfo is not None else ""
    return dt.strftime("%Y-%m-%d %H:%M:%S") + suffix


def short_run_id(run_id: Any, keep: int = 8) -> str:
    """
    Shorten a long run id for compact tables: short_run_id('run-abcdef123456')
    -> 'run-abcd...'. The full id is still available for copy elsewhere.
    """
    if not run_id:
        return MISSING
    text = str(run_id)
    if len(text) <= keep:
        return text
    return text[:keep] + "..."


# ===========================================================================
# GENERIC
# ===========================================================================
def title_case(key: Any) -> str:
    """Turn a snake_case key into a Title Case label: 'total_cost' -> 'Total Cost'."""
    if key is None:
        return MISSING
    return str(key).replace("_", " ").strip().title()


def yes_no(value: Any) -> str:
    """Render a boolean-ish value as 'Yes'/'No' (None -> dash)."""
    if value is None:
        return MISSING
    return "Yes" if bool(value) else "No"


def safe_get(data: Any, *keys: str, default: Any = None) -> Any:
    """
    Read a nested value out of dicts without KeyErrors:
    safe_get(resp, 'evaluation', 'summary') returns resp['evaluation']['summary']
    or `default` if any step is missing. Keeps page code short and crash-proof
    when the backend omits an optional field.
    """
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


# ===========================================================================
# TINY PRIVATE COERCERS  (never raise)
# ===========================================================================
def _to_float(value: Any) -> float | None:
    """Best-effort float, or None if the value is missing / not a number."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_datetime(value: Any) -> datetime | None:
    """Best-effort datetime from an ISO string or a datetime, else None."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    # datetime.fromisoformat handles "2026-07-08T12:34:56+00:00"; also accept a
    # trailing "Z" (UTC) which older Python versions do not parse directly.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
