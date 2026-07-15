"""Storage identifiers and limits for the persistence layer.

Google Sheets tab names and the SQLite path used by :mod:`core.db`. Secret
values (the spreadsheet id, the service-account JSON) are read from environment
variables at call time — only their variable *names* and non-secret defaults
live here.
"""
from __future__ import annotations

import os
from pathlib import Path

# ── SQLite (local dev / Render fallback) ──────────────────────────────────────
# core/config/storage.py → project_root/data/history.db
DB_PATH: Path = Path(__file__).resolve().parent.parent / "data" / "history.db"

# ── Google Sheets backend (Render production) ─────────────────────────────────
GSHEET_ID: str | None = os.environ.get("GSHEET_ID")
GSHEET_TAB: str = os.environ.get("GSHEET_TAB", "Historial_Dashboard")
GSHEET_LATEST_TAB: str = os.environ.get("GSHEET_LATEST_TAB", "Latest_State")
GSHEET_METRICAS_TAB: str = os.environ.get("GSHEET_METRICAS_TAB", "Metricas_Weekly")

# A single Google Sheets cell holds ~50 000 chars; keep a safety margin.
GSHEET_CELL_LIMIT: int = 49_000

# Raw payload keys dropped from the latest-state blob when it exceeds the limit.
GSHEET_OPTIONAL_RAW_KEYS: tuple[str, ...] = (
    "productividad_raw",
    "att_prod_raw",
    "conversion_raw",
    "cartera_raw",
)

# ── Session ───────────────────────────────────────────────────────────────────
SESSION_TTL_SECONDS: int = 6 * 3600   # 6 hours


def use_gsheet() -> bool:
    """Return True when both Google Sheets env vars are configured.

    Read live (not cached) so tests and runtime can toggle the backend via the
    environment without re-importing the module.
    """
    return bool(os.environ.get("GSHEET_ID") and os.environ.get("GOOGLE_CREDS"))
