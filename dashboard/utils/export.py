"""
============================================================================
EXPORT HELPERS
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  Lets a user DOWNLOAD what they are looking at:

    - the optimization history as a CSV,
    - a single stored run as JSON,
    - an agent report as Markdown, and
    - an agent report as JSON.

  These are the four exports the dashboard provides. No PDF - CSV,
  JSON and Markdown cover the need with zero extra dependencies.

TWO LAYERS, ON PURPOSE
----------------------
  1. PURE BUILDERS (..._bytes functions) turn API data into a bytes payload
     using only the standard library (csv, json). They import nothing from
     Streamlit, so the dashboard validation script can call and check them directly.
  2. THIN STREAMLIT WRAPPERS (download_* functions) render a Streamlit
     download button around a pure builder. Streamlit is imported LAZILY inside
     each wrapper, so this module still imports even where Streamlit is absent.

  The dashboard EXPORTS data the backend produced; it never generates new
  numbers here.
============================================================================
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Iterable

# The scalar columns exported to CSV from a history row. We deliberately export
# the flat KPI columns (not the nested metrics/evaluation/details dicts), which
# keeps the CSV clean and spreadsheet-friendly. The list mirrors the columns of
# the optimization_runs table exposed by OptimizationRunResponse.
HISTORY_CSV_COLUMNS = [
    "run_id",
    "created_at",
    "scenario",
    "optimizer",
    "warehouse_id",
    "success",
    "solver_status",
    "total_cost",
    "travel_distance_km",
    "vehicle_utilization",
    "warehouse_utilization",
    "inventory_holding_cost",
    "stockouts",
    "late_deliveries",
    "orders_fulfilled",
    "runtime_ms",
    "num_constraints",
    "num_variables",
    "vehicles_used",
]


# ===========================================================================
# PURE BUILDERS  (standard library only - safe to unit-test)
# ===========================================================================
def history_to_csv_bytes(rows: Iterable[dict], columns: list[str] | None = None) -> bytes:
    """
    Turn a list of history rows (dicts from GET /optimization/history) into CSV
    bytes with a header line. Only the scalar columns in HISTORY_CSV_COLUMNS are
    written; nested dicts are skipped so the CSV stays tabular.
    """
    cols = columns or HISTORY_CSV_COLUMNS
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        # Keep only the chosen scalar columns; coerce None to "" for a clean cell.
        writer.writerow({c: _scalar(row.get(c)) for c in cols})
    return buffer.getvalue().encode("utf-8")


def run_to_json_bytes(run: dict) -> bytes:
    """Serialise one run (any JSON-able dict) to pretty-printed JSON bytes."""
    return _json_bytes(run)


def report_to_markdown_bytes(report: dict) -> bytes:
    """
    Pull the Markdown text out of an agent report and return it as bytes.

    The report dict is the reporting agent's output ({markdown, text, json,
    recommendations, future_improvements}). We export the ALREADY-RENDERED
    markdown - the dashboard never writes a report itself.
    """
    markdown = report.get("markdown") if isinstance(report, dict) else None
    if not markdown:
        markdown = "# Report\n\n(No markdown report was produced.)\n"
    return str(markdown).encode("utf-8")


def report_to_json_bytes(report: dict) -> bytes:
    """Serialise the full agent report dict to pretty-printed JSON bytes."""
    return _json_bytes(report)


# ===========================================================================
# STREAMLIT WRAPPERS  (Streamlit imported lazily so the module still imports)
# ===========================================================================
def download_history_csv(rows: Iterable[dict], *, filename: str = "optimization_history.csv", key: str | None = None) -> None:
    """Render a 'Download CSV' button for the optimization history."""
    import streamlit as st

    st.download_button(
        label="Download history (CSV)",
        data=history_to_csv_bytes(rows),
        file_name=filename,
        mime="text/csv",
        key=key,
    )


def download_run_json(run: dict, *, filename: str = "optimization_run.json", key: str | None = None) -> None:
    """Render a 'Download JSON' button for a single run."""
    import streamlit as st

    st.download_button(
        label="Download run (JSON)",
        data=run_to_json_bytes(run),
        file_name=filename,
        mime="application/json",
        key=key,
    )


def download_report_markdown(report: dict, *, filename: str = "agent_report.md", key: str | None = None) -> None:
    """Render a 'Download Markdown' button for an agent report."""
    import streamlit as st

    st.download_button(
        label="Download report (Markdown)",
        data=report_to_markdown_bytes(report),
        file_name=filename,
        mime="text/markdown",
        key=key,
    )


def download_report_json(report: dict, *, filename: str = "agent_report.json", key: str | None = None) -> None:
    """Render a 'Download JSON' button for an agent report."""
    import streamlit as st

    st.download_button(
        label="Download report (JSON)",
        data=report_to_json_bytes(report),
        file_name=filename,
        mime="application/json",
        key=key,
    )


# ===========================================================================
# TINY PRIVATE HELPERS
# ===========================================================================
def _json_bytes(obj: Any) -> bytes:
    """Pretty JSON bytes; `default=str` keeps unusual values from crashing."""
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str).encode("utf-8")


def _scalar(value: Any) -> Any:
    """Flatten a cell for CSV: dicts/lists become '' (they are not tabular)."""
    if value is None or isinstance(value, (dict, list)):
        return ""
    return value
