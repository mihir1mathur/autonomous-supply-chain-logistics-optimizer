"""
============================================================================
FORMATTING HELPERS
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  Turns raw values from the API into clean, human-friendly strings for the UI.
  It is PURE Python - no Streamlit, no backend, no pandas - so it imports
  anywhere and is easy to test (the dashboard validation script calls these directly).

THE ONE FORMATTING RULE THAT MATTERS MOST
----------------------------------------------------------
  The backend stores VEHICLE / WAREHOUSE UTILIZATION as a FRACTION in 0..1
  (e.g. 0.767 means 76.7%). A dashboard must NEVER show "0.77" to a human - it
  shows "76.7%". So there are two distinct percent helpers, and picking the
  right one is deliberate:

    fraction_to_percent(0.767)   -> "76.7%"   (value is a 0..1 fraction)
    format_percent_value(27.5)   -> "27.5%"   (value is ALREADY a percent, e.g.
                                                the evaluation numbers)

  Getting these two mixed up is the classic dashboard bug, so they are named
  unambiguously and documented here in one place.

IMPORTANT: FORMATTING IS NOT COMPUTATION
  These helpers only re-present numbers the backend already produced. They never
  add, average, or otherwise derive a KPI - that would break the presentation-layer rule
  that the dashboard does not compute metrics.
============================================================================
"""

from __future__ import annotations

import re
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
    Format a value that is ALREADY a percent (e.g. the evaluation numbers
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


def humanize_scenario_change(change: Any) -> str:
    """
    Rewrite ONE backend 'scenario change' line as plain business English for the
    UI. This is display-only: it re-words the text the execution layer already
    produced and never alters the scenario itself. Unrecognised lines are
    returned unchanged so nothing is ever hidden.

      'Demand x1.8: package counts scaled (up).' -> 'Customer demand increased by 80%.'
      'Stock x0.4: tracked inventory scaled down.' -> 'Supplier inventory reduced by 60%.'
    """
    if change is None:
        return MISSING
    text = str(change).strip()
    low = text.lower()

    m = re.search(r"demand x([\d.]+)", low)
    if m:
        mult = float(m.group(1))
        if mult >= 1.0:
            return f"Customer demand increased by {_fmt_pct((mult - 1) * 100)}%."
        return f"Customer demand reduced by {_fmt_pct((1 - mult) * 100)}%."

    m = re.search(r"fuel x([\d.]+)", low)
    if m:
        mult = float(m.group(1))
        if mult >= 1.0:
            return f"Fuel cost increased by {_fmt_pct((mult - 1) * 100)}%."
        return f"Fuel cost reduced by {_fmt_pct((1 - mult) * 100)}%."

    m = re.search(r"stock x([\d.]+)", low)
    if m:
        mult = float(m.group(1))
        if mult <= 1.0:
            return f"Supplier inventory reduced by {_fmt_pct((1 - mult) * 100)}%."
        return f"Supplier inventory increased by {_fmt_pct((mult - 1) * 100)}%."

    m = re.search(r"fraction ([\d.]+)", low)
    if m and "fleet" in low:
        frac = float(m.group(1))
        return f"Available fleet capacity reduced by {_fmt_pct((1 - frac) * 100)}%."

    m = re.search(r"closure:\s*(\d+)", low)
    if m:
        n = int(m.group(1))
        return f"Warehouse capacity reduced due to site closure ({n} site{'s' if n != 1 else ''})."

    m = re.search(r"kept the (\d+).*dropped (\d+)", low)
    if m:
        kept, dropped = int(m.group(1)), int(m.group(2))
        return f"Served the {kept} highest-priority shipment(s); {dropped} deprioritized."

    if low.startswith("no changes"):
        return "No changes - baseline operational configuration."

    return text


def _fmt_pct(value: float) -> str:
    """Format a percentage cleanly (10.0 -> '10', 12.5 -> '12.5')."""
    rounded = round(value)
    if abs(value - rounded) < 0.05:
        return str(int(rounded))
    return f"{value:.1f}"


# ===========================================================================
# EVALUATION WORDING  (business-friendly copies of the agent evaluation block)
# ===========================================================================
# An evaluation `verdict` -> (headline message, tone). Tone drives the banner
# colour on the page ("good" -> green, "bad" -> red, "neutral" -> info). The
# verdict itself is produced by the backend; this only re-words it.
_EVALUATION_RESULT = {
    "improved": ("✓ Better than baseline", "good"),
    "degraded": ("⚠ Worse than baseline", "bad"),
    "mixed": ("⚖ Trade-offs detected vs. baseline", "neutral"),
    "neutral": ("≈ Similar to baseline", "neutral"),
}

# How each evaluation `improvements` percentage reads as a plain bullet. Values
# are ALREADY percentages and POSITIVE means BETTER, so a positive number uses
# the "better" verb and a negative one uses the "worse" verb.
#   (label, improvements-key, verb-when-better, verb-when-worse)
_IMPROVEMENT_BULLETS = [
    ("Cost", "cost_reduction_percent", "reduced", "increased"),
    ("Distance", "distance_reduction_percent", "reduced", "increased"),
    ("Utilization", "utilization_improvement_percent", "improved", "decreased"),
    ("Deliveries", "delivery_improvement_percent", "improved", "decreased"),
    ("Stockouts", "stockout_reduction_percent", "reduced", "increased"),
]

# Below this magnitude (in percentage points) a change reads as "unchanged".
# Mirrors the backend's own ±0.5pp "material change" threshold.
_UNCHANGED_THRESHOLD = 0.5


def evaluation_result(verdict: Any) -> tuple[str, str]:
    """
    Map an evaluation verdict to a (message, tone) for a business-friendly
    "Overall Result" banner. Unknown verdicts fall back to a neutral message.
    """
    key = str(verdict or "").lower()
    return _EVALUATION_RESULT.get(key, ("≈ Similar to baseline", "neutral"))


def summarize_improvements(improvements: dict | None) -> list[str]:
    """
    Turn the evaluation `improvements` percentages into concise business bullets,
    e.g. 'Cost reduced by 23%', 'Distance unchanged', 'Utilization improved by 5%'.

    Display-only: it re-words numbers the backend already computed and never
    derives a metric itself.
    """
    improvements = improvements or {}
    bullets: list[str] = []
    for label, key, better_word, worse_word in _IMPROVEMENT_BULLETS:
        value = improvements.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        if abs(value) < _UNCHANGED_THRESHOLD:
            bullets.append(f"{label} unchanged")
        elif value > 0:
            bullets.append(f"{label} {better_word} by {_fmt_pct(abs(value))}%")
        else:
            bullets.append(f"{label} {worse_word} by {_fmt_pct(abs(value))}%")
    return bullets


# The evaluation metrics shown with a visual indicator, in report order.
#   (label, improvements-key, verb-when-better, verb-when-worse, caution_if_better)
# `caution_if_better` flags a metric whose "improvement" still warrants attention
# (higher vehicle utilization is more efficient but leaves less scheduling slack).
_EVAL_METRICS = [
    ("Cost", "cost_reduction_percent", "reduced", "increased", False),
    ("Distance", "distance_reduction_percent", "reduced", "increased", False),
    ("Inventory holding cost", "inventory_reduction_percent", "reduced", "increased", False),
    ("Stockouts", "stockout_reduction_percent", "reduced", "increased", False),
    ("Late deliveries", "late_delivery_reduction_percent", "reduced", "increased", False),
    ("Order fulfillment", "delivery_improvement_percent", "improved", "declined", False),
    ("Vehicle utilization", "utilization_improvement_percent", "increased", "decreased", True),
]


def evaluation_indicators(improvements: dict | None) -> list[tuple[str, str, str]]:
    """
    Classify each evaluation metric for display as (icon, colour, text):

      ✓ green  - a genuine improvement
      → gray   - no material change
      ⚠ orange - improved but worth watching (e.g. utilization rose)
      ✗ red    - a regression

    Values are already percentages where POSITIVE means BETTER. Display-only.
    """
    improvements = improvements or {}
    rows: list[tuple[str, str, str]] = []
    for label, key, better, worse, caution in _EVAL_METRICS:
        value = improvements.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        if abs(value) < _UNCHANGED_THRESHOLD:
            rows.append(("→", "gray", f"{label} unchanged"))
        elif value > 0:
            icon, colour = ("⚠", "orange") if caution else ("✓", "green")
            rows.append((icon, colour, f"{label} {better} by {_fmt_pct(abs(value))}%"))
        else:
            rows.append(("✗", "red", f"{label} {worse} by {_fmt_pct(abs(value))}%"))
    return rows


def business_risks(kpis: dict | None) -> list[str]:
    """
    Concise, business-oriented risk observations derived from a run's KPIs.

    Display-only: it interprets already-computed KPI values as plain-English
    operational risks; it never recomputes a metric. Recommendations (what to do)
    are kept separate from these risks (what to watch).
    """
    kpis = kpis or {}

    def _num(key: str):
        value = kpis.get(key)
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    risks: list[str] = []
    veh = _num("vehicle_utilization")
    wh = _num("warehouse_utilization")
    late = _num("late_deliveries")
    stock = _num("stockouts")

    if veh is not None and veh >= 0.90:
        risks.append(
            f"High vehicle utilization ({veh * 100:.0f}%) may reduce scheduling "
            "flexibility and leaves little slack to absorb disruptions."
        )
    if wh is not None and wh >= 0.90:
        risks.append(
            f"Warehouse utilization ({wh * 100:.0f}%) is near capacity; consider "
            "balancing load across additional sites."
        )
    if late is not None and late > 0:
        risks.append(f"Late deliveries ({int(late)}) indicate fleet capacity pressure.")
    if stock is not None and stock > 0:
        risks.append(
            f"Stockouts ({int(stock)}) indicate insufficient inventory allocation "
            "for this demand level."
        )
    if not risks:
        risks.append("No material operational risks detected under this scenario.")
    return risks


def humanize_decision_message(message: Any) -> str:
    """
    Reword the decision banner headline for the UI. The backend headline begins
    with the verdict word; only the vague 'Mixed' verdict is reworded to the
    clearer 'Trade-offs detected'. Dynamic values are preserved verbatim.

      'Mixed - cost reduction +2%, ...' -> 'Trade-offs detected: cost reduction +2%, ...'
    """
    if not message:
        return message
    text = str(message)
    if text.startswith("Mixed - "):
        return "Trade-offs detected: " + text[len("Mixed - "):]
    if text.startswith("Mixed"):
        return "Trade-offs detected" + text[len("Mixed"):]
    return text


def humanize_recommendation(text: Any) -> str:
    """
    Clean one backend recommendation for a recruiter-facing display by removing
    developer-oriented API references (e.g. 'via GET /optimization/metrics').
    The wording is otherwise left as the reporting agent produced it.
    """
    if text is None:
        return MISSING
    cleaned = re.sub(r"\s*via (?:GET|POST|PUT|DELETE|PATCH) /[^\s]+", "", str(text)).strip()
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def order_recommendations(recommendations: list | None) -> list:
    """
    Order recommendations action-first for display, without dropping any (except
    exact duplicates): (1) immediate operational action, (2) alternative
    optimizer / mitigation strategy, (3) historical comparison / follow-up.

    Display-only and stable: the relative order within each group is preserved.
    """
    def _rank(text: Any) -> int:
        low = str(text).lower()
        if "stored in the history" in low or "past runs" in low:
            return 2  # historical comparison / follow-up analysis
        if "optimizer" in low:
            return 1  # alternative optimizer / mitigation strategy
        return 0      # immediate operational action

    seen: set[str] = set()
    unique: list = []
    for rec in recommendations or []:
        key = str(rec).strip()
        if key in seen:
            continue  # drop exact duplicates only
        seen.add(key)
        unique.append(rec)
    return sorted(unique, key=_rank)


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
