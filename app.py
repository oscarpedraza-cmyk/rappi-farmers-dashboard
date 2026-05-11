import streamlit as st
from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.loader import load_sheet_maestro
from core.metrics import get_all_semaforos, tier_farmer, EMOJI, COLOR_HEX, calcular_compensacion_completa
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

# Quick table
rows_html = ""
for farmer, data in sorted(farmers_data.items(), key=lambda x: x[1].get("name", "")):
    sems = get_all_semaforos(data)
    tier = tier_farmer(sems)
    name = data.get("name", farmer)

    comp = calcular_compensacion_completa(data)
    var_pct = comp.get("variable_pct", 0)

    badges = "".join([EMOJI.get(s, "⚪") for s in sems.values()])
    qualifier = "" if comp.get("qualifies", True) else " ⛔"

    rows_html += f"""
    <tr style="border-bottom:1px solid #333">
        <td style="padding:8px;font-weight:bold">{EMOJI.get(tier,'⚪')} {name}{qualifier}</td>
        <td style="padding:8px;letter-spacing:4px">{badges}</td>
        <td style="padding:8px;color:{'#4CAF50' if var_pct >= 80 else '#FFA726' if var_pct >= 50 else '#FF4B4B'};font-weight:bold">{var_pct:.0f}%</td>
    </tr>"""

st.markdown(f"""
<table style="width:100%;border-collapse:collapse;font-size:0.9rem">
    <thead>
        <tr style="background:#1E1E2E;color:white">
            <th style="padding:10px;text-align:left">Farmer</th>
            <th style="padding:10px;text-align:left">Churn | MD | MDPro | AdsBook | AdsRev | NetRev | Pitch | NoCont | Reactiv</th>
            <th style="padding:10px;text-align:left">Variable %</th>
        </tr>
    </thead>
    <tbody>{rows_html}</tbody>
</table>
""", unsafe_allow_html=True)

st.caption("⛔ = Pierde variable (productividad < 90%) | Navega por las páginas del menú izquierdo para el análisis detallado")
