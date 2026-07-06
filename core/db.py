# Historical storage - dual backend:
#   1. Google Sheets (if GSHEET_ID env var set) - persists across Render deploys
#   2. SQLite local (fallback for local dev)
# Latest state sharing via st.cache_resource (process-level).
from __future__ import annotations

import logging
import json
import os
import sqlite3
import streamlit as st
from datetime import date, datetime
from pathlib import Path

# â"€â"€ Config â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
DB_PATH = Path(__file__).parent.parent / "data" / "history.db"
GSHEET_ID           = os.environ.get("GSHEET_ID")          # set in Render env vars
GSHEET_TAB          = os.environ.get("GSHEET_TAB", "Historial_Dashboard")
GSHEET_LATEST_TAB   = os.environ.get("GSHEET_LATEST_TAB", "Latest_State")
GSHEET_METRICAS_TAB = os.environ.get("GSHEET_METRICAS_TAB", "Metricas_Weekly")

logger = logging.getLogger(__name__)


# â"€â"€ SQLite backend (local dev) â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
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


# â"€â"€ Google Sheets backend (Render production) â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
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


# â"€â"€ Public API (auto-selects backend) â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
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


# â"€â"€ Google Sheets: Latest_State tab â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
def _get_or_create_latest_sheet(client):
    """Return (or create) the Latest_State worksheet."""
    try:
        sh = client.open_by_key(GSHEET_ID)
        try:
            ws = sh.worksheet(GSHEET_LATEST_TAB)
        except Exception:
            ws = sh.add_worksheet(title=GSHEET_LATEST_TAB, rows=5, cols=2)
            ws.append_row(["key", "value"])
        return ws
    except Exception:
        return None


def _save_latest_gsheet(payload: dict) -> bool:
    """
    Saves the latest_state payload to GSheet Latest_State tab.
    Stores the full payload as JSON; if it exceeds GSheet's cell limit (~50K chars)
    falls back to a compact payload (drops raw strings which are optional).
    """
    client = _gsheet_client()
    if not client:
        return False
    ws = _get_or_create_latest_sheet(client)
    if not ws:
        return False
    try:
        # Try full payload first
        full_json = json.dumps(payload, default=str)
        # GSheet cell limit is ~50 000 chars; split off raw strings if needed
        if len(full_json) > 49_000:
            compact = {k: v for k, v in payload.items()
                       if k not in ("productividad_raw", "att_prod_raw", "conversion_raw", "cartera_raw")}
            payload_json = json.dumps(compact, default=str)
        else:
            payload_json = full_json

        # Overwrite the sheet: header row + single data row
        ws.clear()
        ws.append_row(["key", "value"])
        ws.append_row(["latest_state", payload_json])
        return True
    except Exception as e:
        logger.error("[db] _save_latest_gsheet error: %s", e)
        return False


def _load_latest_gsheet():
    """Load the latest_state payload from GSheet Latest_State tab."""
    client = _gsheet_client()
    if not client:
        return None
    ws = _get_or_create_latest_sheet(client)
    if not ws:
        return None
    try:
        all_rows = ws.get_all_values()
        # Rows: [header, data]
        for row in all_rows[1:]:
            if len(row) >= 2 and row[0] == "latest_state" and row[1]:
                return json.loads(row[1])
        return None
    except Exception as e:
        logger.error("[db] _load_latest_gsheet error: %s", e)
        return None


# â"€â"€ Process-level shared cache (survives across user sessions in same process) â"€â"€
@st.cache_resource
def _process_cache() -> dict:
    """
    Single dict shared by ALL user sessions in this Streamlit process.
    Oscar writes here â†' Maria and the whole team reads it instantly.
    """
    return {}


def save_latest_state(farmers_data: dict, dia_corte: int, dias_mes: int,
                      productividad_raw_json: str = None,
                      att_prod_raw_json: str = None,
                      conversion_raw_json: str = None,
                      cartera_raw_json: str = None,
                      asignacion_raw_json: str = None,
                      updated_by: str = "supervisor") -> bool:
    """
    Persists the most recent upload so all farmer sessions can read it.
    Saves to:
      1. st.cache_resource (instant â€" shared across all sessions in same process)
      2. Google Sheets (survives Streamlit Cloud redeploys â€" primary persistent store)
      3. SQLite (backup â€" survives local process restarts)
    """
    payload = {
        "farmers_data":      farmers_data,
        "dia_corte":         dia_corte,
        "dias_mes":          dias_mes,
        "productividad_raw": productividad_raw_json,
        "att_prod_raw":      att_prod_raw_json,
        "conversion_raw":    conversion_raw_json,
        "cartera_raw":       cartera_raw_json,
        "asignacion_raw":    asignacion_raw_json,
        "updated_by":        updated_by,
        "updated_at":        datetime.now().isoformat(),
    }

    # 1. Write to process-level cache (all sessions see this immediately)
    cache = _process_cache()
    cache["latest"] = payload

    # 2. Persist to Google Sheets (survives Streamlit Cloud redeploys)
    if _use_gsheet():
        try:
            _save_latest_gsheet(payload)
        except Exception as e:
            logger.error("[db] save_latest_state gsheet error: %s", e)

    # 3. Persist to SQLite as backup
    try:
        init_db()
        payload_json = json.dumps(payload, default=str)
        with _conn() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS latest_state (
                    id          INTEGER PRIMARY KEY,
                    state_json  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                )
            """)
            con.execute("DELETE FROM latest_state")
            con.execute(
                "INSERT INTO latest_state (state_json, updated_at) VALUES (?, ?)",
                (payload_json, datetime.now().isoformat())
            )
    except Exception as e:
        logger.error("[db] save_latest_state sqlite error: %s", e)

    return True


def load_latest_state():
    """
    Returns the dict saved by save_latest_state, or None if nothing saved yet.
    Reads from:
      1. st.cache_resource (instant, always current within the process)
      2. Google Sheets (survives Streamlit Cloud redeploys)
      3. SQLite fallback (local dev, survives process restarts)
    Keys: farmers_data, dia_corte, dias_mes, productividad_raw, updated_by, updated_at
    """
    # 1. Try process-level cache first (fastest, most current)
    cache = _process_cache()
    if cache.get("latest"):
        return cache["latest"]

    # 2. Try Google Sheets (survives Streamlit Cloud redeploys)
    if _use_gsheet():
        try:
            result = _load_latest_gsheet()
            if result:
                cache["latest"] = result   # warm up process cache
                return result
        except Exception as e:
            logger.error("[db] load_latest_state gsheet error: %s", e)

    # 3. Fall back to SQLite (survives process restarts, local dev)
    try:
        init_db()
        with _conn() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS latest_state (
                    id          INTEGER PRIMARY KEY,
                    state_json  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                )
            """)
            row = con.execute(
                "SELECT state_json FROM latest_state ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        result = json.loads(row[0])
        # Warm up the process cache so next calls are instant
        cache["latest"] = result
        return result
    except Exception as e:
        logger.error("[db] load_latest_state error: %s", e)
        return None


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


# â"€â"€ WBR: Checklist semanal persistente â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
def _init_wbr_tables():
    init_db()
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS wbr_checklist (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                week_key    TEXT NOT NULL,
                task_id     TEXT NOT NULL,
                done        INTEGER NOT NULL DEFAULT 0,
                updated_at  TEXT NOT NULL,
                UNIQUE(week_key, task_id)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS wbr_disciplinario (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                farmer_email TEXT NOT NULL UNIQUE,
                estado      TEXT NOT NULL DEFAULT 'Recolectando evidencia',
                fecha_inicio TEXT,
                proximo_paso TEXT,
                fecha_limite TEXT,
                notas       TEXT,
                updated_at  TEXT NOT NULL
            )
        """)


def get_checklist_state(week_key: str) -> dict[str, bool]:
    """Returns {task_id: done} for the given ISO week key (e.g. '2026-W20')."""
    try:
        _init_wbr_tables()
        with _conn() as con:
            rows = con.execute(
                "SELECT task_id, done FROM wbr_checklist WHERE week_key=?",
                (week_key,)
            ).fetchall()
        return {r[0]: bool(r[1]) for r in rows}
    except Exception:
        return {}


def save_checklist_task(week_key: str, task_id: str, done: bool):
    """Upsert a single checklist task completion."""
    try:
        _init_wbr_tables()
        with _conn() as con:
            con.execute("""
                INSERT INTO wbr_checklist (week_key, task_id, done, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(week_key, task_id) DO UPDATE SET done=excluded.done, updated_at=excluded.updated_at
            """, (week_key, task_id, int(done), datetime.now().isoformat()))
    except Exception as e:
        logger.error("[db] checklist save error: %s", e)


def get_all_disciplinarios() -> list:
    """Returns all active disciplinary process records."""
    try:
        _init_wbr_tables()
        _init_llamados_table()   # ensure tipo_contrato column exists
        with _conn() as con:
            rows = con.execute(
                "SELECT farmer_email, estado, fecha_inicio, proximo_paso, "
                "fecha_limite, notas, updated_at, "
                "COALESCE(tipo_contrato, 'Manpower') AS tipo_contrato "
                "FROM wbr_disciplinario ORDER BY updated_at DESC"
            ).fetchall()
        return [
            {"farmer_email": r[0], "estado": r[1], "fecha_inicio": r[2],
             "proximo_paso": r[3], "fecha_limite": r[4], "notas": r[5],
             "updated_at": r[6], "tipo_contrato": r[7]}
            for r in rows
        ]
    except Exception:
        return []


def save_disciplinario(farmer_email: str, estado: str, fecha_inicio: str,
                       proximo_paso: str, fecha_limite: str, notas: str,
                       tipo_contrato: str = "Manpower"):
    """Upsert a disciplinary process record."""
    try:
        _init_wbr_tables()
        _init_llamados_table()   # ensure tipo_contrato column exists
        with _conn() as con:
            con.execute("""
                INSERT INTO wbr_disciplinario
                    (farmer_email, estado, fecha_inicio, proximo_paso,
                     fecha_limite, notas, tipo_contrato, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(farmer_email) DO UPDATE SET
                    estado=excluded.estado,
                    fecha_inicio=excluded.fecha_inicio,
                    proximo_paso=excluded.proximo_paso,
                    fecha_limite=excluded.fecha_limite,
                    notas=excluded.notas,
                    tipo_contrato=excluded.tipo_contrato,
                    updated_at=excluded.updated_at
            """, (farmer_email, estado, fecha_inicio, proximo_paso,
                  fecha_limite, notas, tipo_contrato, datetime.now().isoformat()))
    except Exception as e:
        logger.error("[db] disciplinario save error: %s", e)


def delete_disciplinario(farmer_email: str):
    """Remove a disciplinary record (process closed)."""
    try:
        _init_wbr_tables()
        with _conn() as con:
            con.execute("DELETE FROM wbr_disciplinario WHERE farmer_email=?", (farmer_email,))
    except Exception as e:
        logger.error("[db] disciplinario delete error: %s", e)


# â"€â"€ WBR: Llamados de atenciÃ³n â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
def _init_llamados_table():
    init_db()
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS wbr_llamados (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                farmer_email  TEXT NOT NULL,
                numero        INTEGER NOT NULL,
                fecha         TEXT NOT NULL,
                motivo        TEXT,
                tipo_contrato TEXT NOT NULL DEFAULT 'Manpower',
                updated_at    TEXT NOT NULL
            )
        """)
        # Migrate: add tipo_contrato column to disciplinario if missing
        try:
            con.execute(
                "ALTER TABLE wbr_disciplinario ADD COLUMN tipo_contrato TEXT DEFAULT 'Manpower'"
            )
        except Exception:
            pass  # Already exists


def get_all_llamados() -> list:
    """Return all llamados de atenciÃ³n records, ordered by farmer + number."""
    try:
        _init_llamados_table()
        with _conn() as con:
            rows = con.execute(
                "SELECT id, farmer_email, numero, fecha, motivo, tipo_contrato, updated_at "
                "FROM wbr_llamados ORDER BY farmer_email, numero"
            ).fetchall()
        return [
            {"id": r[0], "farmer_email": r[1], "numero": r[2], "fecha": r[3],
             "motivo": r[4], "tipo_contrato": r[5] or "Manpower", "updated_at": r[6]}
            for r in rows
        ]
    except Exception:
        return []


def save_llamado(farmer_email: str, numero: int, fecha: str,
                 motivo: str, tipo_contrato: str):
    """Insert a new llamado de atenciÃ³n record."""
    try:
        _init_llamados_table()
        with _conn() as con:
            con.execute(
                "INSERT INTO wbr_llamados "
                "(farmer_email, numero, fecha, motivo, tipo_contrato, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (farmer_email, numero, fecha, motivo or "",
                 tipo_contrato, datetime.now().isoformat())
            )
    except Exception as e:
        logger.error("[db] save_llamado error: %s", e)


def delete_llamado(llamado_id: int):
    """Remove a specific llamado record by id."""
    try:
        _init_llamados_table()
        with _conn() as con:
            con.execute("DELETE FROM wbr_llamados WHERE id=?", (llamado_id,))
    except Exception as e:
        logger.error("[db] delete_llamado error: %s", e)


# â"€â"€ WBR: Documento semanal persistente â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
def _init_wbr_doc_table():
    init_db()
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS wbr_docs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                week_key   TEXT NOT NULL UNIQUE,
                doc_json   TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


def save_wbr_doc(week_key: str, doc_data: dict):
    """Persist parsed WBR document for the given ISO week."""
    try:
        _init_wbr_doc_table()
        with _conn() as con:
            con.execute("""
                INSERT INTO wbr_docs (week_key, doc_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(week_key) DO UPDATE SET
                    doc_json=excluded.doc_json,
                    updated_at=excluded.updated_at
            """, (week_key, json.dumps(doc_data, default=str), datetime.now().isoformat()))
    except Exception as e:
        logger.error("[db] save_wbr_doc error: %s", e)


def load_wbr_doc(week_key: str) -> dict:
    """Load parsed WBR document for the given ISO week. Returns {} if none."""
    try:
        _init_wbr_doc_table()
        with _conn() as con:
            row = con.execute(
                "SELECT doc_json FROM wbr_docs WHERE week_key=?", (week_key,)
            ).fetchone()
        if not row:
            return {}
        return json.loads(row[0])
    except Exception as e:
        logger.error("[db] load_wbr_doc error: %s", e)
        return {}


# â"€â"€ MÃ©tricas Semanales â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
def _init_metricas_table():
    init_db()
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS metricas_weekly (
                id         INTEGER PRIMARY KEY,
                data_json  TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


def _save_metricas_gsheet(records: list) -> bool:
    """Store farmer-level metricas as tabular rows in a dedicated GSheet tab."""
    client = _gsheet_client()
    if not client:
        return False
    try:
        sh = client.open_by_key(GSHEET_ID)
        try:
            ws = sh.worksheet(GSHEET_METRICAS_TAB)
        except Exception:
            ws = sh.add_worksheet(title=GSHEET_METRICAS_TAB, rows=15000, cols=7)
        ws.clear()
        headers = ["week", "metric", "country", "farmer", "brand", "value", "vs_lw"]
        rows = [headers]
        for r in records:
            rows.append([
                str(r.get("week", "")),
                str(r.get("metric", "")),
                str(r.get("country", "")),
                str(r.get("farmer", "")),
                str(r.get("brand", "")),
                "" if r.get("value") is None else r["value"],
                "" if r.get("vs_lw") is None else r["vs_lw"],
            ])
        ws.update("A1", rows)
        return True
    except Exception as e:
        logger.error("[db] _save_metricas_gsheet error: %s", e)
        return False


def _load_metricas_gsheet():
    """Load farmer-level metricas from GSheet tab. Returns list of dicts or None."""
    client = _gsheet_client()
    if not client:
        return None
    try:
        sh = client.open_by_key(GSHEET_ID)
        ws = sh.worksheet(GSHEET_METRICAS_TAB)
        all_values = ws.get_all_values()
        if len(all_values) < 2:
            return None
        headers = all_values[0]
        records = []
        for row in all_values[1:]:
            if not any(row):
                continue
            rec = dict(zip(headers, row))
            for num_col in ("value", "vs_lw"):
                if num_col in rec:
                    try:
                        rec[num_col] = float(rec[num_col]) if rec[num_col] != "" else None
                    except (ValueError, TypeError):
                        rec[num_col] = None
            records.append(rec)
        return records if records else None
    except Exception as e:
        logger.error("[db] _load_metricas_gsheet error: %s", e)
        return None


def save_metricas_weekly(records: list) -> bool:
    """
    Persist accumulated farmer-level metricas (list of dicts).
    Saves to: process cache â†' GSheet â†' SQLite.
    """
    # 1. Process cache
    cache = _process_cache()
    cache["metricas_weekly"] = records

    # 2. GSheet (production)
    if _use_gsheet():
        try:
            _save_metricas_gsheet(records)
        except Exception as e:
            logger.error("[db] save_metricas_weekly gsheet error: %s", e)

    # 3. SQLite (local dev)
    try:
        _init_metricas_table()
        data_json = json.dumps(records, default=str)
        with _conn() as con:
            con.execute("DELETE FROM metricas_weekly")
            con.execute(
                "INSERT INTO metricas_weekly (data_json, updated_at) VALUES (?, ?)",
                (data_json, datetime.now().isoformat())
            )
    except Exception as e:
        logger.error("[db] save_metricas_weekly sqlite error: %s", e)

    return True


def load_metricas_weekly():
    """
    Returns list of farmer-level metricas dicts, or None if nothing saved.
    Reads from: process cache â†' GSheet â†' SQLite.
    """
    # 1. Process cache
    cache = _process_cache()
    if cache.get("metricas_weekly") is not None:
        return cache["metricas_weekly"]

    # 2. GSheet
    if _use_gsheet():
        try:
            records = _load_metricas_gsheet()
            if records:
                cache["metricas_weekly"] = records
                return records
        except Exception as e:
            logger.error("[db] load_metricas_weekly gsheet error: %s", e)

    # 3. SQLite
    try:
        _init_metricas_table()
        with _conn() as con:
            row = con.execute(
                "SELECT data_json FROM metricas_weekly ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        records = json.loads(row[0])
        cache["metricas_weekly"] = records
        return records
    except Exception as e:
        logger.error("[db] load_metricas_weekly error: %s", e)
        return None

