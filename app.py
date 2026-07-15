from __future__ import annotations

import io
import logging
import os
import streamlit as st
import pandas as pd
import base64
from datetime import date, datetime
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
sys.path.insert(0, str(Path(__file__).parent))

from core.loader import load_sheet_maestro, refresh_net_rev_adj, load_cartera
from core.db import save_snapshot, get_available_dates, save_latest_state, load_latest_state
from core.auth import require_auth, render_topbar
from core.style import inject_global_css

st.set_page_config(
    page_title="Carga de Datos — Rappi Farmers",
    page_icon="📂",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(inject_global_css(), unsafe_allow_html=True)
email, is_supervisor = require_auth()

# ── Sidebar logo ──────────────────────────────────────────────────────────────
with st.sidebar:
    _logo_path = Path(__file__).parent / "assets" / "rappi_logo.png"
    if _logo_path.exists():
        _logo_b64 = base64.b64encode(_logo_path.read_bytes()).decode()
        st.markdown(
            f'<img src="data:image/png;base64,{_logo_b64}" width="100" '
            f'style="display:block;margin:0.5rem auto 0.7rem">',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div style="text-align:center;padding:0.5rem 0 0.7rem">'
            '<span style="font-size:1.35rem;font-weight:900;color:#FF441B">rappi</span>'
            '<span style="font-size:0.62rem;font-weight:700;color:#94A3B8;'
            'display:block;letter-spacing:1px">FARMERS</span></div>',
            unsafe_allow_html=True
        )
    st.markdown('<hr style="border:none;border-top:1px solid #E2E8F0;margin:0 0 0.4rem">',
                unsafe_allow_html=True)

today = date.today()

# ── Auto-load for farmers (non-supervisors) ───────────────────────────────────
if not is_supervisor:
    if "farmers_data" not in st.session_state:
        latest = load_latest_state()
        if latest:
            st.session_state["farmers_data"]       = latest["farmers_data"]
            st.session_state["dia_corte"]          = latest["dia_corte"]
            st.session_state["dias_mes"]           = latest["dias_mes"]
            st.session_state["_updated_at"]        = latest.get("updated_at", "")
            st.session_state["_updated_by"]        = latest.get("updated_by", "")
            if latest.get("productividad_raw"):
                try:
                    df_raw = pd.read_json(io.StringIO(latest["productividad_raw"]))
                    df_raw.columns = [int(c) for c in df_raw.columns]
                    st.session_state["_productividad_raw"] = df_raw
                except Exception:
                    pass
            if latest.get("att_prod_raw"):
                st.session_state["_att_prod_raw"] = latest["att_prod_raw"]
            if latest.get("conversion_raw"):
                st.session_state["_conversion_raw"] = latest["conversion_raw"]
            _cartera_src = latest.get("asignacion_raw") or latest.get("cartera_raw")
            if _cartera_src:
                st.session_state["_cartera_raw"] = _cartera_src

dia_corte    = st.session_state.get("dia_corte", today.day - 1 if today.day > 1 else 1)
dias_mes     = st.session_state.get("dias_mes", 31)
progreso_pct = ((dia_corte - 1) / dias_mes) * 100
_raw_updated_at = st.session_state.get("_updated_at", "")
updated_at = _raw_updated_at[:16].replace("T", " ") if _raw_updated_at else ""

render_topbar(updated_at=updated_at, dia_corte=dia_corte, progreso_pct=progreso_pct)

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="rb-page-header">
    <h1>📂 Carga de Datos</h1>
    <p>Cargá aquí los archivos del período. Los datos quedan disponibles para todo el equipo automáticamente.</p>
</div>
""", unsafe_allow_html=True)

# ── Persistence status ────────────────────────────────────────────────────────
_has_gsheets = bool(os.environ.get("GSHEET_ID"))
if is_supervisor:
    if _has_gsheets:
        st.markdown("""
        <div style="background:#F0FDF4;border:1px solid #86EFAC;border-left:4px solid #16A34A;
                    border-radius:8px;padding:0.6rem 1rem;margin-bottom:0.9rem;font-size:0.82rem;color:#15803D;display:flex;gap:8px;align-items:center">
            <span style="font-size:1rem">☁️</span>
            <div><b>Google Sheets activo</b> — los datos persisten entre deploys de Render automáticamente.</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:#FFFBEB;border:1px solid #FDE68A;border-left:4px solid #D97706;
                    border-radius:8px;padding:0.6rem 1rem;margin-bottom:0.9rem;font-size:0.82rem;color:#92400E;display:flex;gap:8px;align-items:center">
            <span style="font-size:1rem">⚠️</span>
            <div><b>Modo SQLite local</b> — los datos se pierden cuando Render reinicia el servicio.
            Para persistencia permanente, configurá <code>GSHEET_ID</code> y <code>GOOGLE_CREDS</code> en las variables de entorno de Render.</div>
        </div>""", unsafe_allow_html=True)

# ── Upload status table ───────────────────────────────────────────────────────
st.markdown('<div class="rb-section-title">Estado de archivos cargados</div>', unsafe_allow_html=True)

_latest = load_latest_state()

def _status_row(name: str, key: str, rec_count_fn=None) -> dict:
    if not _latest:
        return {"name": name, "loaded": False, "date": "—", "time": "—", "records": "—"}
    data = _latest.get(key)
    updated = _latest.get("updated_at", "")
    if data:
        dt_str = updated[:16].replace("T", " ") if updated else "—"
        date_part = dt_str[:10] if len(dt_str) >= 10 else "—"
        time_part = dt_str[11:] if len(dt_str) > 10 else "—"
        records = "—"
        if rec_count_fn:
            try:
                records = rec_count_fn(data)
            except Exception:
                records = "?"
        return {"name": name, "loaded": True, "date": date_part, "time": time_part, "records": records}
    return {"name": name, "loaded": False, "date": "—", "time": "—", "records": "—"}

def _count_json_rows(json_str: str) -> str:
    try:
        df = pd.read_json(io.StringIO(json_str))
        return f"{len(df):,}"
    except Exception:
        return "?"

def _count_farmers(fd) -> str:
    if isinstance(fd, dict):
        return f"{len(fd)} farmers"
    return "?"

file_statuses = [
    _status_row("Sheet Maestro (farmers_data)", "farmers_data", _count_farmers),
    _status_row("Asignación / Cartera", "asignacion_raw",
                lambda d: _count_json_rows(d) + " marcas"),
    _status_row("Productividad (Follow Track)", "productividad_raw",
                lambda d: _count_json_rows(d) + " filas"),
    _status_row("Conversión / DETALLE", "conversion_raw",
                lambda d: _count_json_rows(d) + " pitches"),
]

# Status table — inject one self-contained HTML block
_rows_html = ""
for fs in file_statuses:
    status_text = "✓ Cargado" if fs["loaded"] else "— Sin datos"
    status_color = "#16A34A" if fs["loaded"] else "#94a3b8"
    status_weight = "700" if fs["loaded"] else "400"
    _rows_html += (
        f'<div style="display:grid;grid-template-columns:3fr 1.4fr 1fr 1.4fr 1.4fr;'
        f'border-bottom:1px solid #E2E8F0;align-items:center">'
        f'<div style="padding:9px 12px;font-size:12px;font-weight:600;color:#0f172a">{fs["name"]}</div>'
        f'<div style="padding:9px 12px;font-size:11px;color:#64748b">{fs["date"]}</div>'
        f'<div style="padding:9px 12px;font-size:11px;color:#64748b">{fs["time"]}</div>'
        f'<div style="padding:9px 12px;font-size:11px;color:{status_color};font-weight:{status_weight}">{status_text}</div>'
        f'<div style="padding:9px 12px;font-size:11px;color:#64748b">{fs["records"]}</div>'
        f'</div>'
    )
_by_html = ""
if _latest and _latest.get("updated_by"):
    _by_html = (
        f'<div style="font-size:11px;color:#94a3b8;padding:6px 12px 8px;'
        f'border-top:1px solid #E2E8F0">Última carga por: '
        f'<b>{_latest["updated_by"]}</b></div>'
    )
_header_cols = "".join(
    f'<div style="padding:8px 12px;font-size:10px;font-weight:700;text-transform:uppercase;'
    f'letter-spacing:0.07em;color:#94a3b8">{h}</div>'
    for h in ["Archivo", "Fecha", "Hora", "Estado", "Registros"]
)
_table_html = (
    '<div style="background:#fff;border:1.5px solid #E2E8F0;border-radius:14px;'
    'overflow:hidden;margin-bottom:1rem">'
    '<div style="display:grid;grid-template-columns:3fr 1.4fr 1fr 1.4fr 1.4fr;'
    'background:#f8fafc;border-bottom:1px solid #E2E8F0">'
    + _header_cols +
    '</div>'
    + _rows_html
    + _by_html +
    '</div>'
)
st.markdown(_table_html, unsafe_allow_html=True)

# ── Supervisor upload controls ─────────────────────────────────────────────────
if is_supervisor:
    _has_data = "farmers_data" in st.session_state
    with st.expander("⬆️ Cargar / actualizar archivos", expanded=not _has_data):

        # ── Row 1: Sheet Maestro ──────────────────────────────────────────────
        st.markdown("""
        <div style="font-size:0.72rem;font-weight:700;color:#64748B;text-transform:uppercase;
                    letter-spacing:0.7px;margin-bottom:0.55rem">Configuración del corte</div>
        """, unsafe_allow_html=True)

        col_cfg1, col_cfg2, col_gap, col_up = st.columns([1.4, 1.4, 0.3, 6])
        with col_cfg1:
            dia_corte_in = st.number_input(
                "Día de corte", min_value=1, max_value=31,
                value=today.day - 1 if today.day > 1 else 1,
                help="Día de envío − 1", key="dia_corte_input"
            )
        with col_cfg2:
            dias_mes_in = st.number_input(
                "Días del mes", min_value=28, max_value=31,
                value=31, key="dias_mes_input"
            )
        with col_up:
            uploaded_file = st.file_uploader(
                "📊 Sheet Maestro (.xlsx)",
                type=["xlsx"],
                help="Sheet_Maestro_Farmers.xlsx — contiene todas las pestañas del período",
                key="file_uploader_main",
            )

        if uploaded_file:
            with st.spinner("Procesando Sheet Maestro..."):
                try:
                    farmers_data = load_sheet_maestro(
                        uploaded_file, dia_corte=dia_corte_in, dias_mes=dias_mes_in
                    )
                    st.session_state["farmers_data"] = farmers_data
                    st.session_state["dia_corte"]    = dia_corte_in
                    st.session_state["dias_mes"]     = dias_mes_in
                    st.session_state["snap_date"]    = today

                    prod_raw_json = att_prod_raw_json = conversion_raw_json = cartera_raw_json = None
                    asig_from_maestro_json = None
                    _sheet_debug = []
                    _att_error   = None
                    try:
                        uploaded_file.seek(0)
                        xl = pd.ExcelFile(uploaded_file, engine="openpyxl")
                        _sheet_debug = list(xl.sheet_names)

                        if "Productividad" in xl.sheet_names:
                            df_prod_raw = xl.parse("Productividad", header=0)
                            df_prod_raw.columns = range(len(df_prod_raw.columns))
                            df_prod_raw = df_prod_raw[
                                df_prod_raw[14].apply(
                                    lambda v: isinstance(v, str) and "@rappi" in v.lower()
                                )
                            ].copy()
                            df_prod_raw[14] = df_prod_raw[14].str.strip().str.lower()
                            st.session_state["_productividad_raw"] = df_prod_raw
                            prod_raw_json = df_prod_raw.to_json()

                        att_sheet = next(
                            (s for s in xl.sheet_names if s.strip().lower() == "att productividad"), None
                        )
                        if att_sheet:
                            df_att_raw = xl.parse(att_sheet, header=0)
                            df_att_raw = df_att_raw.dropna(how="all").dropna(axis=1, how="all")
                            st.session_state["_att_prod_raw"] = df_att_raw.to_json()
                            att_prod_raw_json = df_att_raw.to_json()

                        _conv_candidates = {"conversión", "conversion", "detalle", "hoja1"}
                        conv_sheet = next(
                            (s for s in xl.sheet_names if s.strip().lower() in _conv_candidates), None
                        )
                        if not conv_sheet:
                            for _s in xl.sheet_names:
                                try:
                                    _probe = xl.parse(_s, header=0, nrows=3)
                                    if "FARMER" in _probe.columns and "MD" in _probe.columns:
                                        conv_sheet = _s
                                        break
                                except Exception:
                                    pass
                        if conv_sheet:
                            df_conv_raw = xl.parse(conv_sheet, header=0)
                            df_conv_raw = df_conv_raw.dropna(how="all")
                            if "FARMER" in df_conv_raw.columns:
                                df_conv_raw["FARMER"] = df_conv_raw["FARMER"].astype(str).str.strip().str.lower()
                            st.session_state["_conversion_raw"] = df_conv_raw.to_json()
                            conversion_raw_json = df_conv_raw.to_json()

                        if "Cartera" in xl.sheet_names:
                            try:
                                cartera_raw_json = load_cartera(xl)
                                if cartera_raw_json:
                                    st.session_state["_cartera_raw"] = cartera_raw_json
                            except Exception as _ce:
                                logger.error("[app] Cartera load error: %s", _ce)

                        # Asignación tab in Maestro — eliminates separate file upload
                        _asig_sheet = next(
                            (s for s in xl.sheet_names
                             if s.strip().lower() in ("asignación", "asignacion")), None
                        )
                        if _asig_sheet:
                            try:
                                df_asig_m = xl.parse(_asig_sheet, header=0)
                                df_asig_m = df_asig_m.dropna(how="all")
                                df_asig_m.columns = [str(c).strip() for c in df_asig_m.columns]
                                _fc = next(
                                    (c for c in df_asig_m.columns if "email_nuevo" in c.lower()), None
                                )
                                if _fc:
                                    df_asig_m[_fc] = df_asig_m[_fc].astype(str).str.strip().str.lower()
                                asig_from_maestro_json = df_asig_m.to_json()
                                st.session_state["_cartera_raw"] = asig_from_maestro_json
                            except Exception as _ae:
                                logger.error("[app] Asignación tab parse error: %s", _ae)

                        st.session_state["_sheet_names"] = xl.sheet_names
                    except Exception as _e:
                        _att_error = str(_e)

                    _prev_state     = load_latest_state() or {}
                    _asig_preserved = asig_from_maestro_json or _prev_state.get("asignacion_raw")
                    save_latest_state(
                        farmers_data           = farmers_data,
                        dia_corte              = dia_corte_in,
                        dias_mes               = dias_mes_in,
                        productividad_raw_json = prod_raw_json,
                        att_prod_raw_json      = att_prod_raw_json,
                        conversion_raw_json    = conversion_raw_json,
                        cartera_raw_json       = cartera_raw_json,
                        asignacion_raw_json    = _asig_preserved,
                        updated_by             = email,
                    )
                    if _asig_preserved:
                        st.session_state["_cartera_raw"] = _asig_preserved
                    st.session_state["_updated_at"] = datetime.now().isoformat()
                    st.session_state["_updated_by"] = email

                    n = len(farmers_data)
                    extras = []
                    if att_prod_raw_json:      extras.append("Follow Track")
                    if conversion_raw_json:    extras.append("Conversión")
                    if cartera_raw_json:       extras.append("Cartera")
                    if asig_from_maestro_json: extras.append("Asignación (del Maestro)")
                    extra_str = " · ".join(extras)

                    if _att_error:
                        sheets_found = ", ".join(_sheet_debug) if _sheet_debug else "ninguna"
                        st.warning(f"⚠️ Algunas pestañas no se pudieron leer: {_att_error} · Pestañas: {sheets_found}")
                    st.success(
                        f"✅ {n} farmers cargados" +
                        (f" · Pestañas: {extra_str}" if extra_str else "") +
                        " — datos disponibles para el equipo"
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error cargando el Maestro: {e}")

        # ── Row 2: Asignación independiente ──────────────────────────────────
        st.markdown(
            '<hr style="border:none;border-top:1px solid #F1F5F9;margin:0.85rem 0 0.6rem">',
            unsafe_allow_html=True
        )
        st.markdown("""
        <div style="font-size:0.72rem;font-weight:700;color:#64748B;text-transform:uppercase;
                    letter-spacing:0.7px;margin-bottom:0.55rem">
            Asignación independiente
            <span style="font-weight:400;text-transform:none;letter-spacing:0;color:#94A3B8">
             — solo si NO está incluida como pestaña en el Maestro
            </span>
        </div>
        """, unsafe_allow_html=True)

        col_asig, col_asig_info = st.columns([6, 3])
        with col_asig:
            asignacion_file = st.file_uploader(
                "📋 Asignación.xlsx",
                type=["xlsx"],
                help="Cartera mensual: COUNTRY_BRAND_ID, BRAND_OWNER_EMAIL_NUEVO, GMV_L28D…",
                key="file_uploader_asignacion",
            )

        if asignacion_file:
            with st.spinner("Cargando asignación..."):
                try:
                    df_asig = pd.read_excel(asignacion_file, header=0, engine="openpyxl")
                    df_asig = df_asig.dropna(how="all")
                    df_asig.columns = [str(c).strip() for c in df_asig.columns]
                    farmer_col_a = next(
                        (c for c in df_asig.columns if "email_nuevo" in c.lower()), None
                    )
                    if farmer_col_a:
                        df_asig[farmer_col_a] = df_asig[farmer_col_a].astype(str).str.strip().str.lower()
                    asig_json = df_asig.to_json()
                    st.session_state["_cartera_raw"] = asig_json

                    _existing = load_latest_state() or {}
                    save_latest_state(
                        farmers_data           = _existing.get("farmers_data", {}),
                        dia_corte              = _existing.get("dia_corte", dia_corte_in),
                        dias_mes               = _existing.get("dias_mes", dias_mes_in),
                        productividad_raw_json = _existing.get("productividad_raw"),
                        att_prod_raw_json      = _existing.get("att_prod_raw"),
                        conversion_raw_json    = _existing.get("conversion_raw"),
                        cartera_raw_json       = _existing.get("cartera_raw"),
                        asignacion_raw_json    = asig_json,
                        updated_by             = email,
                    )
                    n_brands  = len(df_asig)
                    n_farmers = df_asig[farmer_col_a].nunique() if farmer_col_a else "?"
                    st.success(f"✅ {n_brands} marcas · {n_farmers} farmers — cartera activa")
                    st.rerun()
                except Exception as _ae:
                    st.error(f"❌ Error leyendo Asignación: {_ae}")

        with col_asig_info:
            if "_cartera_raw" in st.session_state:
                try:
                    _df_c = pd.read_json(io.StringIO(st.session_state["_cartera_raw"]))
                    st.markdown(f"""
                    <div style="background:#F0FDF4;border:1px solid #86EFAC;border-radius:8px;
                                padding:0.55rem 0.9rem;font-size:0.81rem;color:#15803D;font-weight:600">
                        ✅ Cartera activa: {len(_df_c):,} marcas
                    </div>""", unsafe_allow_html=True)
                except Exception:
                    pass
            else:
                st.markdown("""
                <div style="background:#FFFBEB;border:1px solid #FDE68A;border-radius:8px;
                            padding:0.55rem 0.9rem;font-size:0.81rem;color:#78350F">
                    ⚠️ Sin cartera cargada
                </div>""", unsafe_allow_html=True)

        # ── Row 3: Snapshot ───────────────────────────────────────────────────
        st.markdown(
            '<hr style="border:none;border-top:1px solid #F1F5F9;margin:0.85rem 0 0.6rem">',
            unsafe_allow_html=True
        )
        col_snap, col_hist, col_spacer = st.columns([2, 2, 5])
        with col_snap:
            if "farmers_data" in st.session_state:
                if st.button("💾 Guardar snapshot histórico", use_container_width=True):
                    save_snapshot(
                        snap_date    = st.session_state["snap_date"],
                        dia_corte    = st.session_state["dia_corte"],
                        farmers_data = st.session_state["farmers_data"],
                    )
                    st.success("Snapshot guardado ✅")
        with col_hist:
            available_dates = get_available_dates()
            if available_dates:
                st.markdown(f"""
                <div style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px;
                            padding:0.55rem 0.9rem;font-size:0.81rem;color:#0369A1;font-weight:600">
                    📅 {len(available_dates)} snapshot{"s" if len(available_dates) != 1 else ""} guardado{"s" if len(available_dates) != 1 else ""}
                </div>""", unsafe_allow_html=True)

# ── Guide for non-supervisors ─────────────────────────────────────────────────
if not is_supervisor:
    has_data = "farmers_data" in st.session_state
    if has_data:
        _updated = st.session_state.get("_updated_at", "")[:16].replace("T", " ")
        st.markdown(f"""
        <div style="background:#F0FDF4;border:1px solid #86EFAC;border-left:4px solid #16A34A;
                    border-radius:8px;padding:0.75rem 1.1rem;margin-top:0.5rem;font-size:0.85rem;color:#15803D">
            ✅ <b>Datos disponibles</b> — última actualización: {_updated}<br>
            <span style="color:#4ADE80;font-size:0.78rem">Navegá por el menú lateral para ver tu dashboard.</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:#FFFBEB;border:1px solid #FDE68A;border-left:4px solid #D97706;
                    border-radius:8px;padding:0.75rem 1.1rem;margin-top:0.5rem;font-size:0.84rem;color:#92400E">
            ⏳ <b>El supervisor aún no cargó datos para este período.</b>
            Volvé más tarde o contactá a Oscar Pedraza.
        </div>
        """, unsafe_allow_html=True)
