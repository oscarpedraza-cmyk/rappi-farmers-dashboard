"""
Historical storage — dual backend:
  1. Google Sheets (if GSHEET_ID env var set) — persists across Render deploys
  2. SQLite local (fallback for local dev)
"""
import os
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent.parent / "data" / "history.db"
GSHEET_ID = os.environ.get("GSHEET_ID")          # set in Render env vars
GSHEET_TAB = os.environ.get("GSHEET_TAB", "Historial_Dashboard")


# ── SQLite backend (local dev) ────────────────────────────────────────────────
def _conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(str(DB_PATH))


def init_db():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                snap_date   TEXT NOT NULL,
                dia_corte   INTEGER NOT NULL,
                farmer      TEXT NOT NULL,
                data_json   TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_farmer ON snapshots(farmer)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_date ON snapshots(snap_date)")


def _save_sqlite(snap_date: date, dia_corte: int, farmers_data: dict):
    init_db()
    with _conn() as con:
        for farmer, data in farmers_data.items():
            con.execute(
                "DELETE FROM snapshots WHERE snap_date=? AND farmer=?",
                (snap_date.isoformat(), farmer)
            )
            con.execute(
                "INSERT INTO snapshots (snap_date, dia_corte, farmer, data_json, created_at) VALUES (?,?,?,?,?)",
                (snap_date.isoformat(), dia_corte, farmer, json.dumps(data), datetime.now().isoformat())
            )


def _get_sqlite(farmer: str = None, weeks_back: int = 8) -> list:
    init_db()
    with _conn() as con:
        if farmer:
            rows = con.execute(
                "SELECT snap_date, dia_corte, farmer, data_json FROM snapshots "
                "WHERE farmer=? ORDER BY snap_date DESC LIMIT ?",
                (farmer, weeks_back * 7)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT snap_date, dia_corte, farmer, data_json FROM snapshots "
                "ORDER BY snap_date DESC LIMIT ?",
                (weeks_back * 7 * 15,)
            ).fetchall()
    result = []
    for snap_date, dia_corte, farmer_email, data_json in rows:
        entry = json.loads(data_json)
        entry["snap_date"] = snap_date
        entry["dia_corte"] = dia_corte
        result.append(entry)
    return result


def _get_dates_sqlite() -> list:
    init_db()
    with _conn() as con:
        rows = con.execute(
            "SELECT DISTINCT snap_date FROM snapshots ORDER BY snap_date DESC"
        ).fetchall()
    return [r[0] for r in rows]


# ── Google Sheets backend (Render production) ─────────────────────────────────
def _gsheet_client():
    """Returns gspread client using service account from GOOGLE_CREDS env var."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds_json = os.environ.get("GOOGLE_CREDS")
        if not creds_json:
            return None
        creds_dict = json.loads(creds_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception:
        return None


def _get_or_create_sheet(client):
    try:
        sh = client.open_by_key(GSHEET_ID)
        try:
            ws = sh.worksheet(GSHEET_TAB)
        except Exception:
            ws = sh.add_worksheet(title=GSHEET_TAB, rows=5000, cols=10)
            ws.append_row(["snap_date", "dia_corte", "farmer", "data_json", "created_at"])
        return ws
    except Exception:
        return None


def _save_gsheet(snap_date: date, dia_corte: int, farmers_data: dict):
    client = _gsheet_client()
    if not client:
        return False
    ws = _get_or_create_sheet(client)
    if not ws:
        return False
    try:
        all_rows = ws.get_all_values()
        snap_str = snap_date.isoformat()
        # Delete existing rows for this date
        rows_to_delete = [
            i + 1 for i, row in enumerate(all_rows[1:], start=1)
            if len(row) > 2 and row[0] == snap_str
        ]
        for i in reversed(rows_to_delete):
            ws.delete_rows(i + 1)
        # Append new rows
        now = datetime.now().isoformat()
        new_rows = [
            [snap_str, dia_corte, farmer, json.dumps(data), now]
            for farmer, data in farmers_data.items()
        ]
        ws.append_rows(new_rows)
        return True
    except Exception:
        return False


def _get_gsheet(farmer: str = None, weeks_back: int = 8) -> list:
    client = _gsheet_client()
    if not client:
        return []
    ws = _get_or_create_sheet(client)
    if not ws:
        return []
    try:
        all_rows = ws.get_all_values()
        result = []
        for row in all_rows[1:]:
            if len(row) < 4:
                continue
            if farmer and row[2] != farmer:
                continue
            entry = json.loads(row[3])
            entry["snap_date"] = row[0]
            entry["dia_corte"] = int(row[1]) if row[1] else None
            result.append(entry)
        return sorted(result, key=lambda x: x["snap_date"], reverse=True)
    except Exception:
        return []


def _get_dates_gsheet() -> list:
    client = _gsheet_client()
    if not client:
        return []
    ws = _get_or_create_sheet(client)
    if not ws:
        return []
    try:
        all_rows = ws.get_all_values()
        dates = sorted({row[0] for row in all_rows[1:] if row}, reverse=True)
        return dates
    except Exception:
        return []


# ── Public API (auto-selects backend) ────────────────────────────────────────
def _use_gsheet():
    return bool(GSHEET_ID and os.environ.get("GOOGLE_CREDS"))


def save_snapshot(snap_date: date, dia_corte: int, farmers_data: dict) -> bool:
    if _use_gsheet():
        ok = _save_gsheet(snap_date, dia_corte, farmers_data)
        if ok:
            return True
    _save_sqlite(snap_date, dia_corte, farmers_data)
    return True


def get_history(farmer: str = None, weeks_back: int = 8) -> list:
    if _use_gsheet():
        result = _get_gsheet(farmer, weeks_back)
        if result:
            return result
    return _get_sqlite(farmer, weeks_back)


def get_available_dates() -> list:
    if _use_gsheet():
        dates = _get_dates_gsheet()
        if dates:
            return dates
    return _get_dates_sqlite()


def get_farmer_trend(farmer: str, metric_keys: list) -> list:
    history = get_history(farmer=farmer, weeks_back=12)
    trend = []
    for snap in reversed(history):
        row = {"snap_date": snap["snap_date"]}
        for key in metric_keys:
            row[key] = snap.get(key)
        trend.append(row)
    return trend


def get_consecutive_red_weeks(farmer: str, metric_key: str, red_threshold: float = 0.90) -> int:
    history = get_history(farmer=farmer, weeks_back=8)
    count = 0
    for snap in history:
        val = snap.get(metric_key)
        if val is None:
            break
        if val < red_threshold:
            count += 1
        else:
            break
    return count
