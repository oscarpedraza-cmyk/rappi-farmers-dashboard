import streamlit as st
import pandas as pd
import json
import base64
from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.loader import load_sheet_maestro
from core.metrics import (get_all_semaforos, tier_farmer, EMOJI, COLOR_HEX,
                          calcular_compensacion_completa, score_farmer,
                          assign_quartiles, QUARTILE_COLOR, QUARTILE_LABEL)
from core.db import save_snapshot, get_available_dates, save_latest_state, load_latest_state
from core.auth import require_auth, render_sidebar_user_badge
from core.style import inject_global_css

st.set_page_config(
    page_title="Rappi Farmers Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global Rappi CSS ──────────────────────────────────────────────────────────
st.markdown(inject_global_css(), unsafe_allow_html=True)

# ── Auth gate ─────────────────────────────────────────────────────────────────
email, is_supervisor = require_auth()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    _logo_path = Path(__file__).parent / "assets" / "rappi_logo.png"
    if _logo_path.exists():
        _logo_b64 = base64.b64encode(_logo_path.read_bytes()).decode()
        st.markdown(
            f'<img src="data:image/png;base64,{_logo_b64}" width="130" style="display:block;margin-bottom:4px">',
            unsafe_allow_html=True
        )
    else:
        st.markdown("""
        <div style="padding:0.4rem 0 0.6rem">
            <span style="font-size:1.6rem;font-weight:900;color:#FFFFFF;letter-spacing:-1px">rappi</span>
            <span style="font-size:0.7rem;font-weight:600;color:rgba(255,255,255,0.7);margin-left:6px">FARMERS</span>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('<hr style="border:none;border-top:1px solid rgba(255,255,255,0.2);margin:0 0 0.8rem">', unsafe_allow_html=True)

    render_sidebar_user_badge()

    st.markdown("---")
    st.markdown('<p style="color:rgba(255,255,255,0.6);font-size:0.72rem;text-transform:uppercase;letter-spacing:0.5px;margin:0">⚙️ Configuración</p>',
                unsafe_allow_html=True)

    today = date.today()

    if is_supervisor:
        # ── Supervisor controls ──────────────────────────────────────────────
        dia_corte = st.number_input(
            "Día de corte",
            min_value=1, max_value=31,
            value=today.day - 1 if today.day > 1 else 1,
            help="Siempre es el día de envío − 1"
        )
        dias_mes = st.number_input("Días del mes", min_value=28, max_value=31, value=31)
        progreso_pct = ((dia_corte - 1) / dias_mes) * 100
        st.metric("Progreso del mes", f"{progreso_pct:.1f}%")

        st.markdown("---")
        st.markdown('<p style="color:rgba(255,255,255,0.6);font-size:0.72rem;text-transform:uppercase;letter-spacing:0.5px;margin:0">📂 Cargar datos</p>',
                    unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "Sheet_Maestro_Farmers.xlsx",
            type=["xlsx"],
            help="Sube el archivo actualizado — se guardará automáticamente para todo el equipo"
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

                    # Raw sheets for sub-pages
                    prod_raw_json     = None
                    att_prod_raw_json = None
                    _sheet_debug      = []
                    _att_error        = None
                    try:
                        # Seek back — load_sheet_maestro() already read the file stream
                        uploaded_file.seek(0)
                        xl = pd.ExcelFile(uploaded_file, engine="openpyxl")
                        _sheet_debug = list(xl.sheet_names)
                        # Productividad → Conversión tab
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
                        # ATT productividad → Follow Track tab (raw, sin transformar)
                        att_sheet = next(
                            (s for s in xl.sheet_names
                             if s.strip().lower() == "att productividad"), None
                        )
                        if att_sheet:
                            df_att_raw = xl.parse(att_sheet, header=0)
                            # Drop fully-empty rows and columns
                            df_att_raw = df_att_raw.dropna(how="all").dropna(axis=1, how="all")
                            st.session_state["_att_prod_raw"] = df_att_raw.to_json()
                            att_prod_raw_json = df_att_raw.to_json()
                        st.session_state["_sheet_names"] = xl.sheet_names
                    except Exception as _e:
                        _att_error = str(_e)

                    # ── Auto-save for team ─────────────────────────────────
                    save_latest_state(
                        farmers_data          = farmers_data,
                        dia_corte             = dia_corte,
                        dias_mes              = dias_mes,
                        productividad_raw_json= prod_raw_json,
                        att_prod_raw_json     = att_prod_raw_json,
                        updated_by            = email,
                    )

                    n = len(farmers_data)
                    if att_prod_raw_json:
                        st.success(f"✅ {n} farmers cargados · Follow Track ✓")
                    else:
                        sheets_found = ", ".join(_sheet_debug) if _sheet_debug else "ninguna"
                        st.success(f"✅ {n} farmers cargados para el equipo")
                        st.warning(
                            f"⚠️ No se encontró la pestaña **ATT productividad** en el archivo. "
                            f"Pestañas detectadas: `{sheets_found}`"
                            + (f"\nError: {_att_error}" if _att_error else "")
                        )
                except Exception as e:
                    st.error(f"Error: {e}")

        st.markdown("---")
        if "farmers_data" in st.session_state:
            if st.button("💾 Guardar snapshot histórico", use_container_width=True):
                save_snapshot(
                    snap_date   = st.session_state["snap_date"],
                    dia_corte   = st.session_state["dia_corte"],
                    farmers_data = st.session_state["farmers_data"],
                )
                st.success("Guardado en histórico ✅")

        available_dates = get_available_dates()
        if available_dates:
            st.markdown(f'<p style="color:rgba(255,255,255,0.6);font-size:0.75rem">📅 {len(available_dates)} corridas históricas</p>',
                        unsafe_allow_html=True)

    else:
        # ── Farmer view: auto-load latest state ──────────────────────────────
        if "farmers_data" not in st.session_state:
            latest = load_latest_state()
            if latest:
                st.session_state["farmers_data"]  = latest["farmers_data"]
                st.session_state["dia_corte"]     = latest["dia_corte"]
                st.session_state["dias_mes"]      = latest["dias_mes"]
                st.session_state["snap_date"]     = today
                # Restore raw productividad for Conversión tab
                if latest.get("productividad_raw"):
                    try:
                        import io as _io
                        df_raw = pd.read_json(_io.StringIO(latest["productividad_raw"]))
                        df_raw.columns = [int(c) for c in df_raw.columns]
                        st.session_state["_productividad_raw"] = df_raw
                    except Exception:
                        pass
                # Restore ATT productividad for Follow Track tab
                if latest.get("att_prod_raw"):
                    st.session_state["_att_prod_raw"] = latest["att_prod_raw"]

        dia_corte    = st.session_state.get("dia_corte", today.day - 1)
        dias_mes     = st.session_state.get("dias_mes", 31)
        progreso_pct = ((dia_corte - 1) / dias_mes) * 100

        st.metric("Progreso del mes", f"{progreso_pct:.1f}%")
        st.metric("Día de corte", dia_corte)

        # Show last updated info
        latest_meta = load_latest_state()
        if latest_meta:
            updated_at = latest_meta.get("updated_at", "")[:16].replace("T", " ")
            st.markdown(f"""
            <div style="background:rgba(0,0,0,0.15);border-radius:8px;padding:0.6rem 0.8rem;margin-top:0.5rem">
                <div style="font-size:0.7rem;color:rgba(255,255,255,0.6)">Última actualización</div>
                <div style="font-size:0.8rem;color:white;font-weight:600">{updated_at}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(
        '<p style="color:rgba(255,255,255,0.5);font-size:0.7rem;text-align:center">Rappi Growth · AR/UY 🇦🇷🇺🇾</p>',
        unsafe_allow_html=True
    )


# ── Main Page ─────────────────────────────────────────────────────────────────
# Header
if is_supervisor:
    header_sub = "Supervisor · Vista completa con carga de datos"
else:
    name = st.session_state.get("auth_name", "")
    header_sub = f"Bienvenido, {name} · Vista de resultados del equipo"

st.markdown(f"""
<div class="rb-page-header">
    <h1>🚀 Rappi Farmers Dashboard</h1>
    <p>{header_sub} — Equipo AR/UY</p>
</div>
""", unsafe_allow_html=True)

# No data loaded yet
if "farmers_data" not in st.session_state:
    if is_supervisor:
        st.info("👈 **Sube el Sheet Maestro** en el panel izquierdo para comenzar. Los datos quedarán disponibles para todo el equipo automáticamente.")
    else:
        st.warning("⏳ **El supervisor aún no ha cargado datos para este período.** Vuelve más tarde o contacta a Oscar Pedraza.")
        st.markdown("""
        <div class="rb-card" style="margin-top:1rem">
            <h4 style="color:#E8281F;margin:0 0 0.5rem">¿Qué verás aquí?</h4>
            <ul style="color:#374151;margin:0;padding-left:1.2rem">
                <li>📊 Semáforo de tus métricas comerciales del mes</li>
                <li>💰 Estado de tu compensación variable</li>
                <li>🎯 Tu conversión por palanca (MD, Ads, Churn)</li>
                <li>📈 Tendencias históricas de tus KPIs</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    st.stop()

# ── Quick summary ─────────────────────────────────────────────────────────────
farmers_data = st.session_state["farmers_data"]
dia_corte    = st.session_state.get("dia_corte", today.day - 1)
dias_mes     = st.session_state.get("dias_mes", 31)
progreso_pct = ((dia_corte - 1) / dias_mes) * 100

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

st.markdown(f"### Resumen del equipo — Corte día {dia_corte} | {progreso_pct:.1f}% del mes")

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

col1, col2, col3, col4 = st.columns(4)
with col1: st.metric("🔴 En rojo",     tier_counts["red"],
                      help="Farmers con al menos 1 KPI en rojo")
with col2: st.metric("🟡 En amarillo", tier_counts["yellow"])
with col3: st.metric("🟢 En verde",    tier_counts["green"])
with col4: st.metric("👥 Total farmers", sum(tier_counts.values()))

st.markdown("#### KPIs más críticos del equipo")
metric_cols   = st.columns(4)
sorted_metrics = sorted(metric_reds.items(), key=lambda x: x[1], reverse=True)
for i, (metric, count) in enumerate(sorted_metrics[:4]):
    with metric_cols[i]:
        color = "🔴" if count >= 5 else "🟡" if count >= 2 else "🟢"
        st.metric(f"{color} {metric}", f"{count} farmers en rojo")

st.markdown("---")
st.markdown("### Semáforo del equipo")

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
    c = "#EF4444" if val > 40 else "#F59E0B" if val > 30 else "#00B341"
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
        <td style="padding:10px 8px;text-align:center">{fmt_nc(data.get('pct_no_contactados'))}</td>
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
    <span style="color:#00B341">■ ≥95%</span>
    <span style="color:#00B341">■ 90-95%</span>
    <span style="color:#F59E0B">■ 80-90%</span>
    <span style="color:#EF4444">■ &lt;80%</span>
</div>
""", unsafe_allow_html=True)
