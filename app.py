import streamlit as st
import pandas as pd
import json
import base64
from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.loader import load_sheet_maestro, refresh_net_rev_adj, load_cartera
from core.metrics import (get_all_semaforos, tier_farmer, EMOJI, COLOR_HEX,
                          calcular_compensacion_completa, score_farmer,
                          assign_quartiles, QUARTILE_COLOR, QUARTILE_LABEL)
from core.db import save_snapshot, get_available_dates, save_latest_state, load_latest_state
from core.auth import require_auth, render_topbar
from core.style import inject_global_css

st.set_page_config(
    page_title="Rappi Farmers Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global Rappi CSS ──────────────────────────────────────────────────────────
st.markdown(inject_global_css(), unsafe_allow_html=True)

# ── Auth gate ─────────────────────────────────────────────────────────────────
email, is_supervisor = require_auth()

# ── Sidebar — only navigation branding ──────────────────────────────────────
with st.sidebar:
    _logo_path = Path(__file__).parent / "assets" / "rappi_logo.png"
    if _logo_path.exists():
        _logo_b64 = base64.b64encode(_logo_path.read_bytes()).decode()
        st.markdown(
            f'<img src="data:image/png;base64,{_logo_b64}" width="110" '
            f'style="display:block;margin:0.5rem auto 0.8rem">',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div style="text-align:center;padding:0.5rem 0 0.8rem">'
            '<span style="font-size:1.4rem;font-weight:900;color:#E8281F">rappi</span>'
            '<span style="font-size:0.65rem;font-weight:700;color:rgba(255,255,255,0.5);'
            'display:block;letter-spacing:1px">FARMERS</span></div>',
            unsafe_allow_html=True
        )
    st.markdown('<hr style="border:none;border-top:1px solid rgba(255,255,255,0.1);margin:0 0 0.5rem">',
                unsafe_allow_html=True)

# ── Collect date / progress info (needed for topbar) ─────────────────────────
today = date.today()

# ── Farmer auto-load (before topbar so we have updated_at) ───────────────────
if not is_supervisor:
    if "farmers_data" not in st.session_state:
        latest = load_latest_state()
        if latest:
            st.session_state["farmers_data"] = latest["farmers_data"]
            st.session_state["dia_corte"]    = latest["dia_corte"]
            st.session_state["dias_mes"]     = latest["dias_mes"]
            st.session_state["snap_date"]    = today
            if latest.get("productividad_raw"):
                try:
                    import io as _io
                    df_raw = pd.read_json(_io.StringIO(latest["productividad_raw"]))
                    df_raw.columns = [int(c) for c in df_raw.columns]
                    st.session_state["_productividad_raw"] = df_raw
                except Exception:
                    pass
            if latest.get("att_prod_raw"):
                st.session_state["_att_prod_raw"] = latest["att_prod_raw"]
            if latest.get("conversion_raw"):
                st.session_state["_conversion_raw"] = latest["conversion_raw"]
            if latest.get("cartera_raw"):
                st.session_state["_cartera_raw"] = latest["cartera_raw"]

dia_corte    = st.session_state.get("dia_corte", today.day - 1 if today.day > 1 else 1)
dias_mes     = st.session_state.get("dias_mes", 31)
progreso_pct = ((dia_corte - 1) / dias_mes) * 100
latest_meta  = load_latest_state()
updated_at   = latest_meta.get("updated_at", "")[:16].replace("T", " ") if latest_meta else ""

# ── TOP BAR (replaces sidebar user panel) ─────────────────────────────────────
render_topbar(updated_at=updated_at, dia_corte=dia_corte, progreso_pct=progreso_pct)

# ── SUPERVISOR CONTROLS (top of main content) ─────────────────────────────────
if is_supervisor:
    _has_data = "farmers_data" in st.session_state
    with st.expander("⚙️  Cargar / actualizar datos", expanded=not _has_data):
        # ── Row 1: Config chips + uploader ────────────────────────────────────
        st.markdown("""
        <div style="font-size:0.78rem;font-weight:600;color:#64748B;
                    text-transform:uppercase;letter-spacing:0.7px;margin-bottom:0.6rem">
            Configuración del corte
        </div>""", unsafe_allow_html=True)

        col_cfg1, col_cfg2, col_gap, col_up = st.columns([1.4, 1.4, 0.3, 6])
        with col_cfg1:
            dia_corte = st.number_input(
                "Día de corte",
                min_value=1, max_value=31,
                value=today.day - 1 if today.day > 1 else 1,
                help="Día de envío − 1",
                key="dia_corte_input"
            )
        with col_cfg2:
            dias_mes = st.number_input(
                "Días del mes",
                min_value=28, max_value=31,
                value=31, key="dias_mes_input"
            )
        with col_up:
            uploaded_file = st.file_uploader(
                "📂  Sheet Maestro (xlsx)",
                type=["xlsx"],
                help="Sheet_Maestro_Farmers.xlsx — se publica automáticamente para todo el equipo",
                key="file_uploader_main",
                label_visibility="visible"
            )

        if uploaded_file:
            with st.spinner("Leyendo datos..."):
                try:
                    farmers_data = load_sheet_maestro(
                        uploaded_file, dia_corte=dia_corte, dias_mes=dias_mes
                    )
                    st.session_state["farmers_data"] = farmers_data
                    st.session_state["dia_corte"]    = dia_corte
                    st.session_state["dias_mes"]     = dias_mes
                    st.session_state["snap_date"]    = today

                    prod_raw_json = att_prod_raw_json = conversion_raw_json = cartera_raw_json = None
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

                        # Cartera sheet (portfolio analysis)
                        if "Cartera" in xl.sheet_names:
                            try:
                                cartera_raw_json = load_cartera(xl)
                                if cartera_raw_json:
                                    st.session_state["_cartera_raw"] = cartera_raw_json
                            except Exception as _ce:
                                print(f"[app] Cartera load error: {_ce}")

                        st.session_state["_sheet_names"] = xl.sheet_names
                    except Exception as _e:
                        _att_error = str(_e)

                    save_latest_state(
                        farmers_data           = farmers_data,
                        dia_corte              = dia_corte,
                        dias_mes               = dias_mes,
                        productividad_raw_json = prod_raw_json,
                        att_prod_raw_json      = att_prod_raw_json,
                        conversion_raw_json    = conversion_raw_json,
                        cartera_raw_json       = cartera_raw_json,
                        updated_by             = email,
                    )
                    # Refresh progreso after load
                    progreso_pct = ((dia_corte - 1) / dias_mes) * 100
                    n = len(farmers_data)
                    extras = []
                    if att_prod_raw_json:   extras.append("Follow Track ✓")
                    if conversion_raw_json: extras.append("Conversión Real ✓")
                    if cartera_raw_json:    extras.append("Cartera ✓")
                    extra_str = " · ".join(extras)
                    if _att_error:
                        sheets_found = ", ".join(_sheet_debug) if _sheet_debug else "ninguna"
                        st.warning(f"⚠️ Error leyendo pestañas extra: {_att_error} · Pestañas: {sheets_found}")
                    st.success(f"✅ {n} farmers cargados" + (f" · {extra_str}" if extra_str else " para el equipo"))
                except Exception as e:
                    st.error(f"Error: {e}")

        # ── Row 2: Asignación del mes ─────────────────────────────────────────
        st.markdown('<hr style="border:none;border-top:1px solid #F0F0F0;margin:0.8rem 0 0.6rem">', unsafe_allow_html=True)
        st.markdown("""
        <div style="font-size:0.78rem;font-weight:600;color:#64748B;
                    text-transform:uppercase;letter-spacing:0.7px;margin-bottom:0.6rem">
            Asignación del mes (Cartera independiente)
        </div>""", unsafe_allow_html=True)

        col_asig, col_asig_info = st.columns([6, 3])
        with col_asig:
            asignacion_file = st.file_uploader(
                "📋  Asignación.xlsx (cartera del mes)",
                type=["xlsx"],
                help="Archivo de asignación mensual con columnas: COUNTRY_BRAND_ID, BRAND_OWNER_EMAIL_NUEVO, GMV_L28D…",
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

                    # Persist: merge with existing state to preserve farmers_data etc.
                    _existing = load_latest_state() or {}
                    if _existing.get("farmers_data"):
                        save_latest_state(
                            farmers_data           = _existing["farmers_data"],
                            dia_corte              = _existing.get("dia_corte", dia_corte),
                            dias_mes               = _existing.get("dias_mes", dias_mes),
                            productividad_raw_json = _existing.get("productividad_raw"),
                            att_prod_raw_json      = _existing.get("att_prod_raw"),
                            conversion_raw_json    = _existing.get("conversion_raw"),
                            cartera_raw_json       = asig_json,
                            updated_by             = email,
                        )
                    n_brands  = len(df_asig)
                    n_farmers = df_asig[farmer_col_a].nunique() if farmer_col_a else "?"
                    st.success(
                        f"✅ Asignación cargada: **{n_brands} marcas** · **{n_farmers} farmers** "
                        f"· Cartera disponible para todo el equipo"
                    )
                except Exception as _ae:
                    st.error(f"❌ Error leyendo Asignación: {_ae}")

        with col_asig_info:
            if "_cartera_raw" in st.session_state:
                try:
                    import io as _io_c
                    _df_c = pd.read_json(_io_c.StringIO(st.session_state["_cartera_raw"]))
                    st.markdown(f"""
                    <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;
                                padding:0.55rem 0.9rem;font-size:0.83rem;color:#065F46;font-weight:600">
                        ✅ Cartera activa: {len(_df_c)} marcas
                    </div>""", unsafe_allow_html=True)
                except Exception:
                    pass
            else:
                st.markdown("""
                <div style="background:#FFFBEB;border:1px solid #FDE68A;border-radius:8px;
                            padding:0.55rem 0.9rem;font-size:0.83rem;color:#78350F">
                    ⚠️ Sin cartera cargada aún
                </div>""", unsafe_allow_html=True)

        # ── Row 3: Snapshot controls ───────────────────────────────────────────
        st.markdown('<div style="height:0.3rem"></div>', unsafe_allow_html=True)
        col_snap, col_hist, col_spacer = st.columns([2, 2, 5])
        with col_snap:
            if "farmers_data" in st.session_state:
                if st.button("💾 Guardar snapshot", use_container_width=True):
                    save_snapshot(
                        snap_date    = st.session_state["snap_date"],
                        dia_corte    = st.session_state["dia_corte"],
                        farmers_data = st.session_state["farmers_data"],
                    )
                    st.success("Guardado ✅")
        with col_hist:
            available_dates = get_available_dates()
            if available_dates:
                st.markdown(f"""
                <div style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px;
                            padding:0.55rem 0.9rem;font-size:0.83rem;color:#0369A1;font-weight:600">
                    📅 {len(available_dates)} snapshot{"s" if len(available_dates) != 1 else ""} histórico{"s" if len(available_dates) != 1 else ""}
                </div>""", unsafe_allow_html=True)

# ── No data loaded ─────────────────────────────────────────────────────────────
if "farmers_data" not in st.session_state:
    if is_supervisor:
        st.markdown("""
        <div style="background:#FFFBEB;border:1px solid #FDE68A;border-left:4px solid #F59E0B;
                    border-radius:10px;padding:1rem 1.3rem;margin-top:0.5rem;
                    font-size:0.88rem;color:#78350F">
            ☝️ <b>Expande la sección de arriba</b> y sube el Sheet Maestro para comenzar.
            Los datos quedarán disponibles automáticamente para todo el equipo.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:#FFF7F7;border:1px solid #FECACA;border-left:4px solid #EF4444;
                    border-radius:10px;padding:1rem 1.3rem;margin-top:0.5rem;
                    font-size:0.88rem;color:#7F1D1D">
            ⏳ <b>El supervisor aún no ha cargado datos para este período.</b>
            Vuelve más tarde o contacta a Oscar Pedraza.
        </div>
        <div class="rb-card" style="margin-top:1rem">
            <div style="font-weight:700;color:#E8281F;margin-bottom:0.6rem;font-size:1rem">
                ¿Qué verás aquí?
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
                <div style="display:flex;align-items:center;gap:0.5rem;
                            background:#F8FAFC;border-radius:8px;padding:0.6rem 0.8rem;
                            font-size:0.84rem;color:#374151">
                    📊 Semáforo de tus métricas del mes
                </div>
                <div style="display:flex;align-items:center;gap:0.5rem;
                            background:#F8FAFC;border-radius:8px;padding:0.6rem 0.8rem;
                            font-size:0.84rem;color:#374151">
                    💰 Estado de tu compensación variable
                </div>
                <div style="display:flex;align-items:center;gap:0.5rem;
                            background:#F8FAFC;border-radius:8px;padding:0.6rem 0.8rem;
                            font-size:0.84rem;color:#374151">
                    🎯 Conversión por palanca (MD, Ads, Churn)
                </div>
                <div style="display:flex;align-items:center;gap:0.5rem;
                            background:#F8FAFC;border-radius:8px;padding:0.6rem 0.8rem;
                            font-size:0.84rem;color:#374151">
                    📈 Tendencias históricas de tus KPIs
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.stop()

# ── Quick summary ─────────────────────────────────────────────────────────────
farmers_data = st.session_state["farmers_data"]
dia_corte    = st.session_state.get("dia_corte", today.day - 1)
dias_mes     = st.session_state.get("dias_mes", 31)
progreso_pct = ((dia_corte - 1) / dias_mes) * 100

# Always recalculate Net_Rev_Adj with today's date so the pace is current
try:
    refresh_net_rev_adj(farmers_data, dias_mes)
except Exception:
    pass  # keep existing values if anything goes wrong

# Last update banner (for farmers)
if not is_supervisor:
    latest_meta = load_latest_state()
    if latest_meta:
        updated_at = latest_meta.get("updated_at", "")[:16].replace("T", " ")
        st.markdown(f"""
        <div class="last-update-banner">
            📅 Datos actualizados el <b>{updated_at}</b> · Corte día <b>{dia_corte}</b>
            ({progreso_pct:.1f}% del mes)
        </div>
        """, unsafe_allow_html=True)

# ── Section header ────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;
            margin:0.2rem 0 1rem">
    <div>
        <div style="font-size:1.25rem;font-weight:800;color:#0F172A;letter-spacing:-0.3px">
            Resumen del equipo
        </div>
        <div style="font-size:0.8rem;color:#64748B;margin-top:2px">
            Corte día <b>{dia_corte}</b> · <b>{progreso_pct:.1f}%</b> del mes completado
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

tier_counts = {"red": 0, "yellow": 0, "green": 0}
metric_reds  = {m: 0 for m in ["Churn", "MD Total", "MD Pro", "Ads Bookings", "Ads Revenue",
                                "Net Rev Adj", "Pitch Integral", "No Contactados"]}

for farmer, data in farmers_data.items():
    sems = get_all_semaforos(data)
    t    = tier_farmer(sems)
    tier_counts[t] = tier_counts.get(t, 0) + 1
    for metric, s in sems.items():
        if s == "red" and metric in metric_reds:
            metric_reds[metric] += 1

n_total = sum(tier_counts.values())

# KPI overview cards
col1, col2, col3, col4 = st.columns(4)
_kpi_style = "border-radius:12px;padding:1rem 1.2rem;text-align:center;font-weight:700"
with col1:
    st.markdown(f"""<div style="background:#FEF2F2;border:1px solid #FECACA;{_kpi_style}">
        <div style="font-size:2rem;color:#EF4444">{tier_counts["red"]}</div>
        <div style="font-size:0.75rem;color:#9CA3AF;margin-top:4px;font-weight:600">🔴 EN ROJO</div>
    </div>""", unsafe_allow_html=True)
with col2:
    st.markdown(f"""<div style="background:#FFFBEB;border:1px solid #FDE68A;{_kpi_style}">
        <div style="font-size:2rem;color:#F59E0B">{tier_counts["yellow"]}</div>
        <div style="font-size:0.75rem;color:#9CA3AF;margin-top:4px;font-weight:600">🟡 EN AMARILLO</div>
    </div>""", unsafe_allow_html=True)
with col3:
    st.markdown(f"""<div style="background:#F0FDF4;border:1px solid #BBF7D0;{_kpi_style}">
        <div style="font-size:2rem;color:#059669">{tier_counts["green"]}</div>
        <div style="font-size:0.75rem;color:#9CA3AF;margin-top:4px;font-weight:600">🟢 EN VERDE</div>
    </div>""", unsafe_allow_html=True)
with col4:
    st.markdown(f"""<div style="background:#F8FAFC;border:1px solid #E2E8F0;{_kpi_style}">
        <div style="font-size:2rem;color:#0F172A">{n_total}</div>
        <div style="font-size:0.75rem;color:#9CA3AF;margin-top:4px;font-weight:600">👥 TOTAL FARMERS</div>
    </div>""", unsafe_allow_html=True)

# KPIs críticos
sorted_metrics = sorted(metric_reds.items(), key=lambda x: x[1], reverse=True)
top_metrics    = [(m, c) for m, c in sorted_metrics if c > 0][:4]
if top_metrics:
    st.markdown("""
    <div style="font-size:0.78rem;font-weight:700;color:#64748B;text-transform:uppercase;
                letter-spacing:0.7px;margin:1.1rem 0 0.5rem">KPIs más críticos</div>
    """, unsafe_allow_html=True)
    metric_cols = st.columns(len(top_metrics))
    for i, (metric, count) in enumerate(top_metrics):
        bg = "#FEF2F2" if count >= 5 else "#FFFBEB" if count >= 2 else "#F0FDF4"
        fc = "#EF4444" if count >= 5 else "#F59E0B" if count >= 2 else "#059669"
        bc = "#FECACA" if count >= 5 else "#FDE68A" if count >= 2 else "#BBF7D0"
        with metric_cols[i]:
            st.markdown(f"""
            <div style="background:{bg};border:1px solid {bc};border-radius:10px;
                        padding:0.8rem 1rem;text-align:center">
                <div style="font-size:1.5rem;font-weight:800;color:{fc}">{count}</div>
                <div style="font-size:0.73rem;color:#6B7280;font-weight:600;margin-top:3px">{metric}</div>
            </div>""", unsafe_allow_html=True)

st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)

# ── Semáforo table header ──────────────────────────────────────────────────────
st.markdown("""
<div style="font-size:1rem;font-weight:800;color:#0F172A;
            letter-spacing:-0.2px;margin:0.8rem 0 0.6rem">
    Semáforo del equipo
</div>
""", unsafe_allow_html=True)

# ── Scores & quartiles ────────────────────────────────────────────────────────
all_scores = {}
all_comps  = {}
all_sems   = {}
for farmer, data in farmers_data.items():
    sems = get_all_semaforos(data)
    comp = calcular_compensacion_completa(data)
    all_sems[farmer]   = sems
    all_comps[farmer]  = comp
    all_scores[farmer] = score_farmer(sems, comp)

quartiles = assign_quartiles(all_scores)

sorted_farmers = sorted(farmers_data.items(), key=lambda x: -all_scores.get(x[0], 0))

# ── Formatting helpers ────────────────────────────────────────────────────────
def fmt_att(val):
    if val is None: return "<span style='color:#9CA3AF'>S/D</span>"
    pct = val * 100
    c = "#00B341" if pct >= 95 else "#00B341" if pct >= 90 else "#F59E0B" if pct >= 80 else "#EF4444"
    return f"<span style='color:{c};font-weight:700'>{pct:.0f}%</span>"

def fmt_pi(val):
    if val is None: return "<span style='color:#9CA3AF'>S/D</span>"
    pct = val * 100
    c = "#00B341" if pct >= 65 else "#F59E0B" if pct >= 50 else "#EF4444"
    return f"<span style='color:{c};font-weight:700'>{pct:.0f}%</span>"

def fmt_netrev(val):
    if val is None: return "<span style='color:#9CA3AF'>S/D</span>"
    c = "#00B341" if val >= 0 else "#F59E0B" if val >= -5 else "#EF4444"
    return f"<span style='color:{c};font-weight:700'>{val:+.1f}pp</span>"

def fmt_nc(val):
    if val is None: return "<span style='color:#9CA3AF'>S/D</span>"
    c = "#EF4444" if val > 40 else "#F59E0B" if val > 25 else "#00B341"
    return f"<span style='color:{c};font-weight:700'>{val:.0f}%</span>"

def fmt_recurr(val):
    """% cuentas recurrentes sin contactar (2+ semanas). MAYOR = MEJOR (identifica candidatos a limpiar portafolio)."""
    if val is None: return "<span style='color:#9CA3AF'>S/D</span>"
    c = "#EF4444" if val < 10 else "#F59E0B" if val < 20 else "#00B341"
    return f"<span style='color:{c};font-weight:700'>{val:.0f}%</span>"

def fmt_prod(val):
    if val is None: return "<span style='color:#EF4444'>⛔ S/D</span>"
    pct = val * 100
    c = "#00B341" if pct >= 90 else "#F59E0B" if pct >= 80 else "#EF4444"
    pfx = "⛔ " if pct < 90 else ""
    return f"<span style='color:{c};font-weight:700'>{pfx}{pct:.0f}%</span>"

# ── Build table rows ──────────────────────────────────────────────────────────
rows_html  = ""
current_q  = None

for farmer, data in sorted_farmers:
    q         = quartiles.get(farmer, "Q4")
    comp      = all_comps[farmer]
    var_pct   = comp.get("variable_pct", 0)
    qualifies = comp.get("qualifies", True)

    if q != current_q:
        current_q = q
        qcolor = QUARTILE_COLOR.get(q, "#9CA3AF")
        qlabel = QUARTILE_LABEL.get(q, q)
        qdesc  = {"Q1": "Top performers", "Q2": "En camino",
                  "Q3": "Requieren seguimiento", "Q4": "Intervención urgente"}
        rows_html += f"""
        <tr>
            <td colspan="10" style="
                background:{qcolor}12;
                border-left:4px solid {qcolor};
                padding:6px 14px;
                font-weight:700;
                color:{qcolor};
                font-size:0.82rem;
                letter-spacing:0.5px;
            ">{qlabel} — {qdesc.get(q,'')}</td>
        </tr>"""

    name      = data.get("name", farmer)
    qcolor    = QUARTILE_COLOR.get(q, "#9CA3AF")
    var_color = "#00B341" if var_pct >= 80 else "#F59E0B" if var_pct >= 50 else "#EF4444"
    qual_icon = "" if qualifies else " ⛔"

    rows_html += f"""
    <tr style="border-bottom:1px solid #F3F4F6;transition:background 0.15s">
        <td style="padding:10px 12px;border-left:3px solid {qcolor}">
            <span style="
                background:{qcolor}18;color:{qcolor};
                font-size:0.68rem;font-weight:700;
                padding:2px 7px;border-radius:4px;margin-right:7px;
            ">{q}</span>
            <span style="font-weight:600;color:#1A1A1A">{name}{qual_icon}</span>
        </td>
        <td style="padding:10px 8px;text-align:center">{fmt_att(data.get('ATT_Churn'))}</td>
        <td style="padding:10px 8px;text-align:center">{fmt_att(data.get('ATT_MD_Total'))}</td>
        <td style="padding:10px 8px;text-align:center">{fmt_att(data.get('ATT_MD_Pro'))}</td>
        <td style="padding:10px 8px;text-align:center">{fmt_att(data.get('ATT_Rev_real'))}</td>
        <td style="padding:10px 8px;text-align:center">{fmt_netrev(data.get('Net_Rev_Adj'))}</td>
        <td style="padding:10px 8px;text-align:center">{fmt_pi(data.get('Pitch_Pct'))}</td>
        <td style="padding:10px 8px;text-align:center">{fmt_nc(data.get('pct_cuentas_no_contactadas'))}</td>
        <td style="padding:10px 8px;text-align:center">{fmt_recurr(data.get('pct_recurrencia_no'))}</td>
        <td style="padding:10px 8px;text-align:center">{fmt_prod(data.get('productividad_pct'))}</td>
        <td style="padding:10px 8px;text-align:center;font-weight:700;
                   color:{var_color}">{var_pct:.0f}%</td>
    </tr>"""

st.markdown(f"""
<table class="semaforo-table" style="
    width:100%;border-collapse:collapse;font-size:0.87rem;
    background:#FFFFFF;border:1px solid #E5E7EB;border-radius:12px;overflow:hidden;
    box-shadow:0 2px 8px rgba(0,0,0,0.06);
">
    <thead>
        <tr style="background:#F9FAFB;color:#6B7280;font-size:0.73rem;
                   text-transform:uppercase;letter-spacing:0.8px">
            <th style="padding:11px 14px;text-align:left;min-width:180px">Farmer</th>
            <th style="padding:11px 8px;text-align:center">Churn</th>
            <th style="padding:11px 8px;text-align:center">MD</th>
            <th style="padding:11px 8px;text-align:center">MD Pro</th>
            <th style="padding:11px 8px;text-align:center">Ads Rev</th>
            <th style="padding:11px 8px;text-align:center">Net Rev</th>
            <th style="padding:11px 8px;text-align:center">Pitch</th>
            <th style="padding:11px 8px;text-align:center">No Cont.</th>
            <th style="padding:11px 8px;text-align:center">Recurrencia</th>
            <th style="padding:11px 8px;text-align:center">Productividad</th>
            <th style="padding:11px 8px;text-align:center">Variable</th>
        </tr>
    </thead>
    <tbody>{rows_html}</tbody>
</table>
""", unsafe_allow_html=True)

st.markdown("""
<div style="margin-top:0.8rem;font-size:0.74rem;color:#9CA3AF;display:flex;gap:1.5rem;flex-wrap:wrap">
    <span>🏆 <b>Q1</b> Top performers</span>
    <span>✅ <b>Q2</b> En camino</span>
    <span>⚠️ <b>Q3</b> Seguimiento activo</span>
    <span>🚨 <b>Q4</b> Intervención urgente</span>
    <span>⛔ = Pierde variable (productividad &lt; 90%)</span>
    <span>No Cont. = % cuentas únicas sin contactar</span>
    <span>Recurrencia = % cuentas sin contactar 2+ semanas · <b style="color:#00B341">↑ mayor = mejor</b></span>
    <span style="color:#00B341">■ ≥95%</span>
    <span style="color:#00B341">■ 90-95%</span>
    <span style="color:#F59E0B">■ 80-90%</span>
    <span style="color:#EF4444">■ &lt;80%</span>
</div>
""", unsafe_allow_html=True)
