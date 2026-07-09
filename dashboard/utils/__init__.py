"""
============================================================================
DASHBOARD UTILS   -- formatting + export helpers
Project: Supply Chain & Logistics Optimizer
============================================================================

Small, dependency-light helpers shared across the pages and components:

  formatting.py  turn raw API values into human-friendly display strings
                 (percentages as %, money with a currency symbol, ms as ms/s,
                 timestamps as readable dates). PURE - no Streamlit, no backend.
  export.py      build CSV / JSON / Markdown byte payloads from API data and
                 wire them to Streamlit download buttons.

Keeping these here (not inside the pages) means every page formats numbers the
SAME way and no page re-implements a download. Nothing in formatting.py imports
Streamlit or the backend, so it is trivially unit-testable (the dashboard
validation script calls it directly).
============================================================================
"""
