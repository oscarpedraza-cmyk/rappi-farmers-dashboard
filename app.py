import streamlit as st
from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.loader import load_sheet_maestro
from core.metrics import (get_all_semaforos, tier_farmer, EMOJI, COLOR_HEX,
                          calcular_compensacion_completa, score_farmer,
                          assign_quartiles, QUARTILE_COLOR, QUARTILE_LABEL)
from core.db import save_snapshot, get_available_dates

st.set_page_config(
    page_title="Rappi Farmers Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #FF6B00 0%, #FF4500 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .main-header h1 { margin: 0; font-size: 1.8rem; }
    .main-header p  { margin: 0.3rem 0 0; opacity: 0.9; font-size: 0.95rem; }

    .metric-card {
        background: #1E1E2E;
        border-radius: 10px;
        padding: 1rem;
        border-left: 4px solid;
        margin-bottom: 0.5rem;
    }
    .upload-box {
        background: #F8F9FA;
        border: 2px dashed #FF6B00;
        border-radius: 10px;
        padding: 1.5rem;
        text-align: center;
    }
    .stMetric label { font-size: 0.75rem !important; }
    div[data-testid="stSidebarContent"] { background: #0F0F1A; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Rappi_logo.svg/320px-Rappi_logo.svg.png", width=120)
    st.markdown("---")
    st.markdown("### ⚙️ Configuración de corrida")

    today = date.today()
    dia_corte = st.number_input(
        "Día de corte",
        min_value=1, max_value=31,
        value=today.day - 1 if today.day > 1 else 1,
        help="Siempre es el día de envío − 1"
    )
    dias_mes = st.number_input("Días del mes", min_value=28, max_value=31, value=30)

    progreso_pct = ((dia_corte - 1) / dias_mes) * 100
    st.metric("Progreso del mes", f"{progreso_pct:.1f}%")

    st.markdown("---")
    st.markdown("### 📂 Cargar Sheet Maestro")
    uploaded_file = st.file_uploader(
        "Sheet_Maestro_Farmers.xlsx",
        type=["xlsx"],
        help="Sube el archivo actualizado para calcular métricas"
    )

    if uploaded_file:
        with st.spinner("Leyendo datos..."):
            try:
                farmers_data = load_sheet_maestro(uploaded_file, dia_corte=dia_corte, dias_mes=dias_mes)
                st.session_state["farmers_data"] = farmers_data
                st.session_state["dia_corte"] = dia_corte
                st.session_state["dias_mes"] = dias_mes
                st.session_state["snap_date"] = today

                # Guardar Productividad raw para pestaña de Conversión
                try:
                    import pandas as pd
                    xl = pd.ExcelFile(uploaded_file)
                    if "Productividad" in xl.sheet_names:
                        df_prod_raw = xl.parse("Productividad", header=0)
                        df_prod_raw.columns = range(len(df_prod_raw.columns))
                        # Filtrar solo farmers activos
                        df_prod_raw = df_prod_raw[
                            df_prod_raw[14].apply(lambda v: isinstance(v, str) and "@rappi" in v.lower())
                        ].copy()
                        df_prod_raw[14] = df_prod_raw[14].str.strip().str.lower()
                        st.session_state["_productividad_raw"] = df_prod_raw
                except Exception:
                    pass

                st.success(f"✅ {len(farmers_data)} farmers cargados")
            except Exception as e:
                st.error(f"Error leyendo el archivo: {e}")

    st.markdown("---")

    if "farmers_data" in st.session_state:
        if st.button("💾 Guardar snapshot histórico", use_container_width=True):
            save_snapshot(
                snap_date=st.session_state["snap_date"],
                dia_corte=st.session_state["dia_corte"],
                farmers_data=st.session_state["farmers_data"],
            )
            st.success("Guardado en histórico ✅")

    available_dates = get_available_dates()
    if available_dates:
        st.markdown(f"📅 **{len(available_dates)} corridas guardadas**")


# ── Main Page ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🚀 Rappi Farmers Dashboard</h1>
    <p>Supervisión comercial en tiempo real — Equipo AR/UY</p>
</div>
""", unsafe_allow_html=True)

if "farmers_data" not in st.session_state:
    st.info("👈 **Sube el Sheet Maestro** en el panel izquierdo para comenzar")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("""
        **📊 Vista Equipo**
        Macro view: scorecard del equipo, rankings, alertas globales
        """)
    with col2:
        st.markdown("""
        **👤 Vista Farmer**
        Micro view: métricas individuales, productividad cruzada, recomendaciones
        """)
    with col3:
        st.markdown("""
        **📈 Histórico**
        Tendencias semanales por farmer y por palanca
        """)
    with col4:
        st.markdown("""
        **💰 Compensación**
        Calculadora de variable en tiempo real + Revenue Share ADS
        """)
    st.stop()

# ── Quick team summary on home page ──────────────────────────────────────────
farmers_data = st.session_state["farmers_data"]
dia_corte = st.session_state["dia_corte"]

st.markdown(f"### Resumen rápido — Corte día {dia_corte} | {progreso_pct:.1f}% del mes")

tier_counts = {"red": 0, "yellow": 0, "green": 0}
metric_reds = {m: 0 for m in ["Churn", "MD Total", "MD Pro", "Ads Bookings", "Ads Revenue",
                                "Net Rev Adj", "Pitch Integral", "No Contactados"]}

for farmer, data in farmers_data.items():
    sems = get_all_semaforos(data)
    t = tier_farmer(sems)
    tier_counts[t] = tier_counts.get(t, 0) + 1
    for metric, s in sems.items():
        if s == "red" and metric in metric_reds:
            metric_reds[metric] += 1

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🔴 En rojo", tier_counts["red"], help="Farmers con al menos 1 KPI en rojo")
with col2:
    st.metric("🟡 En amarillo", tier_counts["yellow"])
with col3:
    st.metric("🟢 En verde", tier_counts["green"])
with col4:
    total = sum(tier_counts.values())
    st.metric("👥 Total farmers", total)

st.markdown("#### KPIs más críticos del equipo")
metric_cols = st.columns(4)
sorted_metrics = sorted(metric_reds.items(), key=lambda x: x[1], reverse=True)
for i, (metric, count) in enumerate(sorted_metrics[:4]):
    with metric_cols[i]:
        color = "🔴" if count >= 5 else "🟡" if count >= 2 else "🟢"
        st.metric(f"{color} {metric}", f"{count} farmers en rojo")

st.markdown("---")
st.markdown("### Semáforo del equipo")

# ── Calcular scores y cuartiles ───────────────────────────────────────────────
all_scores = {}
all_comps = {}
all_sems = {}
for farmer, data in farmers_data.items():
    sems = get_all_semaforos(data)
    comp = calcular_compensacion_completa(data)
    all_sems[farmer] = sems
    all_comps[farmer] = comp
    all_scores[farmer] = score_farmer(sems, comp)

quartiles = assign_quartiles(all_scores)

# ── Ordenar por cuartil y score (Q1 arriba, Q4 abajo) ────────────────────────
sorted_farmers = sorted(
    farmers_data.items(),
    key=lambda x: (-all_scores.get(x[0], 0))
)

def fmt_att(val):
    if val is None: return "<span style='color:#555'>S/D</span>"
    pct = val * 100
    if pct >= 95:   c = "#4CAF50"
    elif pct >= 90: c = "#8BC34A"
    elif pct >= 80: c = "#FFA726"
    else:           c = "#FF4B4B"
    return f"<span style='color:{c};font-weight:bold'>{pct:.0f}%</span>"

def fmt_pi(val):
    if val is None: return "<span style='color:#555'>S/D</span>"
    pct = val * 100
    c = "#4CAF50" if pct >= 65 else "#FFA726" if pct >= 50 else "#FF4B4B"
    return f"<span style='color:{c};font-weight:bold'>{pct:.0f}%</span>"

def fmt_netrev(val):
    if val is None: return "<span style='color:#555'>S/D</span>"
    c = "#4CAF50" if val >= 0 else "#FFA726" if val >= -5 else "#FF4B4B"
    return f"<span style='color:{c};font-weight:bold'>{val:+.1f}pp</span>"

def fmt_nc(val):
    if val is None: return "<span style='color:#555'>S/D</span>"
    c = "#FF4B4B" if val > 40 else "#FFA726" if val > 30 else "#4CAF50"
    return f"<span style='color:{c};font-weight:bold'>{val:.0f}%</span>"

def fmt_prod(val):
    if val is None: return "<span style='color:#FF4B4B'>⛔ S/D</span>"
    pct = val * 100
    c = "#4CAF50" if pct >= 90 else "#FFA726" if pct >= 80 else "#FF4B4B"
    prefix = "⛔ " if pct < 90 else ""
    return f"<span style='color:{c};font-weight:bold'>{prefix}{pct:.0f}%</span>"

rows_html = ""
current_q = None
for farmer, data in sorted_farmers:
    q = quartiles.get(farmer, "Q4")
    comp = all_comps[farmer]
    var_pct = comp.get("variable_pct", 0)
    qualifies = comp.get("qualifies", True)

    # Separator row between quartiles
    if q != current_q:
        current_q = q
        qcolor = QUARTILE_COLOR.get(q, "#9E9E9E")
        qlabel = QUARTILE_LABEL.get(q, q)
        qdesc = {"Q1": "Top performers", "Q2": "En camino", "Q3": "Requieren seguimiento", "Q4": "Intervención urgente"}
        rows_html += f"""
        <tr>
            <td colspan="10" style="background:{qcolor}22;border-left:4px solid {qcolor};
                padding:6px 12px;font-weight:bold;color:{qcolor};font-size:0.85rem">
                {qlabel} — {qdesc.get(q,'')}
            </td>
        </tr>"""

    name = data.get("name", farmer)
    qcolor = QUARTILE_COLOR.get(q, "#9E9E9E")
    var_color = "#4CAF50" if var_pct >= 80 else "#FFA726" if var_pct >= 50 else "#FF4B4B"
    qualifier_icon = "" if qualifies else " ⛔"

    score = all_scores.get(farmer, 0)

    churn   = fmt_att(data.get("ATT_Churn"))
    md      = fmt_att(data.get("ATT_MD_Total"))
    mdpro   = fmt_att(data.get("ATT_MD_Pro"))
    ads     = fmt_att(data.get("ATT_Rev_real"))
    netrev  = fmt_netrev(data.get("Net_Rev_Adj"))
    pi      = fmt_pi(data.get("Pitch_Pct"))
    nc      = fmt_nc(data.get("pct_no_contactados"))
    prod    = fmt_prod(data.get("productividad_pct"))

    rows_html += f"""
    <tr style="border-bottom:1px solid #222;hover:background:#1a1a2e">
        <td style="padding:8px 10px;border-left:3px solid {qcolor}">
            <span style="background:{qcolor}33;color:{qcolor};font-size:0.7rem;
                  font-weight:bold;padding:2px 6px;border-radius:4px;margin-right:6px">{q}</span>
            <span style="font-weight:600;color:white">{name}{qualifier_icon}</span>
        </td>
        <td style="padding:8px;text-align:center">{churn}</td>
        <td style="padding:8px;text-align:center">{md}</td>
        <td style="padding:8px;text-align:center">{mdpro}</td>
        <td style="padding:8px;text-align:center">{ads}</td>
        <td style="padding:8px;text-align:center">{netrev}</td>
        <td style="padding:8px;text-align:center">{pi}</td>
        <td style="padding:8px;text-align:center">{nc}</td>
        <td style="padding:8px;text-align:center">{prod}</td>
        <td style="padding:8px;text-align:center;font-weight:bold;color:{var_color}">{var_pct:.0f}%</td>
    </tr>"""

st.markdown(f"""
<table style="width:100%;border-collapse:collapse;font-size:0.88rem;background:#0F0F1A">
    <thead>
        <tr style="background:#1E1E2E;color:#aaa;font-size:0.75rem;text-transform:uppercase;letter-spacing:1px">
            <th style="padding:10px;text-align:left;min-width:180px">Farmer</th>
            <th style="padding:10px;text-align:center">Churn</th>
            <th style="padding:10px;text-align:center">MD</th>
            <th style="padding:10px;text-align:center">MD Pro</th>
            <th style="padding:10px;text-align:center">Ads Rev</th>
            <th style="padding:10px;text-align:center">Net Rev</th>
            <th style="padding:10px;text-align:center">Pitch</th>
            <th style="padding:10px;text-align:center">No Cont.</th>
            <th style="padding:10px;text-align:center">Productividad</th>
            <th style="padding:10px;text-align:center">Variable</th>
        </tr>
    </thead>
    <tbody>{rows_html}</tbody>
</table>
""", unsafe_allow_html=True)

st.markdown("""
<div style="margin-top:0.8rem;font-size:0.75rem;color:#666;display:flex;gap:1.5rem;flex-wrap:wrap">
    <span>🏆 <b>Q1</b> Top performers</span>
    <span>✅ <b>Q2</b> En camino</span>
    <span>⚠️ <b>Q3</b> Seguimiento activo</span>
    <span>🚨 <b>Q4</b> Intervención urgente</span>
    <span>⛔ = Pierde variable (productividad &lt; 90%)</span>
    <span>Color: <span style="color:#4CAF50">≥95%</span> / <span style="color:#8BC34A">90-95%</span> / <span style="color:#FFA726">80-90%</span> / <span style="color:#FF4B4B">&lt;80%</span></span>
</div>
""", unsafe_allow_html=True)
