import streamlit as st
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.metrics import (
    get_all_semaforos, tier_farmer, EMOJI, COLOR_HEX,
    calcular_compensacion_completa, calcular_revenue_share_ads,
    generar_recomendaciones
)
from core.db import get_consecutive_red_weeks
from core.auth import require_auth, render_sidebar_user_badge

st.set_page_config(page_title="Vista Farmer — Rappi Farmers", page_icon="🚀", layout="wide")
email, is_supervisor = require_auth()

st.markdown("# 👤 Vista Farmer — Supervisión Individual")
st.caption("Análisis micro: métricas, productividad cruzada, compensación y caminos de mejora")

if "farmers_data" not in st.session_state:
    st.warning("El supervisor aún no ha cargado datos. Vuelve a la página principal.")
    st.stop()

farmers_data = st.session_state["farmers_data"]
dia_corte = st.session_state.get("dia_corte", 15)

# ── Farmer selector (supervisor sees all; farmer sees only themselves) ─────────
names = {data.get("name", em): em for em, data in farmers_data.items()}
sorted_names = sorted(names.keys())

if is_supervisor:
    selected_name = st.selectbox("Selecciona un farmer", sorted_names)
else:
    # Pre-select the logged-in farmer; hide selector if they're in the list
    my_name = next((data.get("name", em) for em, data in farmers_data.items() if em == email), None)
    if my_name and my_name in sorted_names:
        selected_name = st.selectbox("Farmer", sorted_names, index=sorted_names.index(my_name))
    else:
        selected_name = st.selectbox("Selecciona un farmer", sorted_names)
email = names[selected_name]
data = farmers_data[email]

sems = get_all_semaforos(data)
tier = tier_farmer(sems)
comp = calcular_compensacion_completa(data)
rs_ads = comp.get("rs_ads", {})

# ── Header card ───────────────────────────────────────────────────────────────
tier_color = COLOR_HEX.get(tier, "#9E9E9E")
qualifier_badge = "" if comp.get("qualifies", True) else " ⛔ SIN QUALIFIER"

st.markdown(f"""
<div style="background:linear-gradient(135deg,{tier_color}18,#FFF8F4);
            border-left:6px solid {tier_color};border-radius:12px;padding:1.2rem 1.5rem;margin-bottom:1rem">
    <h2 style="margin:0;color:#1A1A1A">{EMOJI.get(tier,'⚪')} {selected_name}{qualifier_badge}</h2>
    <p style="margin:0.3rem 0 0;color:#555;font-size:0.9rem">{email} | Corte día {dia_corte}</p>
</div>
""", unsafe_allow_html=True)

# ── Metric badges ─────────────────────────────────────────────────────────────
st.markdown("### Métricas del período")
cols = st.columns(9)

metric_defs = [
    ("Churn ATT",       "ATT_Churn",              "decimal"),
    ("MD Total",        "ATT_MD_Total",            "decimal"),
    ("MD Pro",          "ATT_MD_Pro",              "decimal"),
    ("Ads Bookings",    "ATT_Book",                "decimal"),
    ("Ads Revenue",     "ATT_Rev_real",            "decimal"),
    ("Net Rev Adj",     "Net_Rev_Adj",             "pp"),
    ("Pitch Integral",  "Pitch_Pct",               "decimal"),
    ("No Contactados",  "pct_no_contactados",      "pct_raw"),
    ("Reactivaciones",  "Reactivaciones",          "count"),
]

sem_keys = ["Churn", "MD Total", "MD Pro", "Ads Bookings", "Ads Revenue",
            "Net Rev Adj", "Pitch Integral", "No Contactados", "Reactivaciones"]

for col, (label, key, fmt), sem_key in zip(cols, metric_defs, sem_keys):
    val = data.get(key)
    sem = sems.get(sem_key, "gray")
    color = COLOR_HEX.get(sem, "#9E9E9E")

    if val is None:
        display = "S/D"
    elif fmt == "decimal":
        display = f"{val*100:.1f}%"
    elif fmt == "pp":
        display = f"{val:+.1f} pp"
    elif fmt == "pct_raw":
        display = f"{val:.1f}%"
    else:
        display = str(int(val))

    # Weeks in red
    metric_map = {"Churn": "ATT_Churn", "MD Total": "ATT_MD_Total",
                  "MD Pro": "ATT_MD_Pro", "Ads Revenue": "ATT_Rev_real"}
    consec = get_consecutive_red_weeks(email, metric_map[sem_key]) if sem_key in metric_map else 0
    consec_label = f"({consec}w 🔴)" if consec >= 2 else ""

    with col:
        st.markdown(f"""
        <div style="background:#F8F9FA;border-radius:10px;padding:0.7rem;
                    border-top:4px solid {color};text-align:center;height:100px;border:1px solid #E0E0E0">
            <div style="font-size:0.65rem;color:#666;margin-bottom:4px">{label}</div>
            <div style="font-size:1.3rem;font-weight:bold;color:{color}">{display}</div>
            <div style="font-size:0.7rem;color:#555">{EMOJI.get(sem,'⚪')} {consec_label}</div>
        </div>
        """, unsafe_allow_html=True)

# ── Productividad cruzada ─────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Productividad cruzada por palanca")
st.caption("Oportunidades identificadas vs pitches efectivos — el cruce que revela si el problema es cartera o gestión")

palancas = [
    ("Churn", "churn_follows", "churn_contactados", "Churn"),
    ("MD Total", "md_follows", "md_contactados", "MD Total"),
    ("Ads", "ads_follows", "ads_contactados", "Ads Revenue"),
]

prod_cols = st.columns(3)
for col, (label, follows_key, cont_key, sem_key) in zip(prod_cols, palancas):
    follows = data.get(follows_key) or 0
    contactados = data.get(cont_key) or 0
    sem = sems.get(sem_key, "gray")
    color = COLOR_HEX.get(sem, "#9E9E9E")

    no_cont = follows - contactados
    pct_cont = round(contactados / follows * 100, 1) if follows > 0 else 0

    with col:
        st.markdown(f"""
        <div style="background:#F8F9FA;border-radius:10px;padding:1rem;border-left:4px solid {color};border:1px solid #E0E0E0">
            <div style="font-size:0.8rem;color:#555;margin-bottom:6px">{EMOJI.get(sem,'⚪')} <b style="color:#1A1A1A">{label}</b></div>
            <div style="display:flex;justify-content:space-between">
                <span style="color:#555;font-size:0.85rem">Oportunidades</span>
                <span style="color:#1A1A1A;font-weight:bold">{int(follows)}</span>
            </div>
            <div style="display:flex;justify-content:space-between">
                <span style="color:#555;font-size:0.85rem">Contactados</span>
                <span style="color:#2E7D32;font-weight:bold">{int(contactados)}</span>
            </div>
            <div style="display:flex;justify-content:space-between">
                <span style="color:#555;font-size:0.85rem">Sin contactar</span>
                <span style="color:#C62828;font-weight:bold">{int(no_cont)}</span>
            </div>
            <div style="margin-top:8px;background:#E0E0E0;border-radius:4px;height:6px">
                <div style="background:{color};width:{pct_cont}%;height:6px;border-radius:4px"></div>
            </div>
            <div style="font-size:0.75rem;color:#666;margin-top:3px">{pct_cont:.1f}% efectividad</div>
        </div>
        """, unsafe_allow_html=True)

# Diagnosis
total_f = data.get("total_follows") or 0
no_cont_total = data.get("no_contactados") or 0
pct_nc = data.get("pct_no_contactados") or 0

st.markdown(f"""
**Total follows:** {int(total_f)} | **Sin contactar:** {int(no_cont_total)} ({pct_nc:.1f}%)
""")

if pct_nc > 40:
    st.error(f"🔴 Contactabilidad crítica ({pct_nc:.1f}%) — el problema no es la cartera, es la gestión del tiempo o calidad de datos de contacto.")
elif pct_nc > 30:
    st.warning(f"🟡 Contactabilidad baja ({pct_nc:.1f}%) — revisar agenda y estrategia de contacto.")

# ── Brands en riesgo ──────────────────────────────────────────────────────────
brands = data.get("brands_riesgo", [])
if brands:
    st.markdown("---")
    st.markdown("### 🏪 Brands con penetración > 70% (riesgo ADS)")
    brand_cols = st.columns(min(len(brands), 5))
    for col, brand in zip(brand_cols, brands[:5]):
        with col:
            st.markdown(f"""
            <div style="background:#FF4B4B22;border:1px solid #FF4B4B;border-radius:8px;
                        padding:0.5rem;text-align:center;font-size:0.8rem;color:#FF4B4B">
                ⚠️ {brand}
            </div>
            """, unsafe_allow_html=True)
    if len(brands) > 5:
        st.caption(f"+ {len(brands)-5} brands más en riesgo")

# ── Compensación ──────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 💰 Estado de compensación variable")

comp_cols = st.columns(3)
with comp_cols[0]:
    var_pct = comp.get("variable_pct", 0)
    var_color = "#4CAF50" if var_pct >= 80 else "#FFA726" if var_pct >= 50 else "#FF4B4B"
    st.markdown(f"""
    <div style="background:#F8F9FA;border-radius:10px;padding:1.2rem;text-align:center;border:1px solid #E0E0E0">
        <div style="font-size:0.8rem;color:#666">% Variable ganado</div>
        <div style="font-size:2.5rem;font-weight:bold;color:{var_color}">{var_pct:.0f}%</div>
        <div style="font-size:0.75rem;color:#555">{'⛔ PIERDE VARIABLE' if not comp.get('qualifies',True) else '✅ Qualificado'}</div>
    </div>
    """, unsafe_allow_html=True)

with comp_cols[1]:
    rs = comp.get("rs_ads", {})
    rs_pct = rs.get("pct", 0)
    rs_color = "#4CAF50" if rs_pct >= 20 else "#FFA726" if rs_pct > 0 else "#FF4B4B"
    st.markdown(f"""
    <div style="background:#F8F9FA;border-radius:10px;padding:1.2rem;text-align:center;border:1px solid #E0E0E0">
        <div style="font-size:0.8rem;color:#666">Revenue Share ADS</div>
        <div style="font-size:2.5rem;font-weight:bold;color:{rs_color}">{rs_pct}%</div>
        <div style="font-size:0.75rem;color:#555">{rs.get('label','')}</div>
    </div>
    """, unsafe_allow_html=True)

with comp_cols[2]:
    contribs = comp.get("contributions", {})
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=var_pct,
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": var_color},
            "steps": [
                {"range": [0, 50], "color": "#FF4B4B33"},
                {"range": [50, 80], "color": "#FFA72633"},
                {"range": [80, 100], "color": "#4CAF5033"},
            ],
            "threshold": {"line": {"color": "white", "width": 2}, "thickness": 0.75, "value": 80},
        },
        number={"suffix": "%"},
        title={"text": "Variable Score"},
    ))
    fig_gauge.update_layout(
        height=200, margin=dict(l=20, r=20, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

# Contribution breakdown
st.markdown("#### Contribución por KPI al variable")
kpi_labels = {"ADS_Rev": "ADS Revenue (35%)", "MD_Total": "MD Total (20%)",
              "MD_Pro": "MD Pro (20%)", "Churn": "Churn (25%)"}
kpi_statuses = comp.get("kpi_statuses", {})

contrib_cols = st.columns(4)
kpi_att_map = {
    "ADS_Rev": data.get("ATT_Rev_real"),
    "MD_Total": data.get("ATT_MD_Total"),
    "MD_Pro": data.get("ATT_MD_Pro"),
    "Churn": data.get("ATT_Churn"),
}

for col, (kpi, label) in zip(contrib_cols, kpi_labels.items()):
    status = kpi_statuses.get(kpi, "sin_dato")
    contrib = contribs.get(kpi)
    att_val = kpi_att_map.get(kpi)

    status_map = {
        "gana": ("🟢", "#4CAF50"),
        "parcial": ("🟡", "#FFA726"),
        "no_gana": ("🔴", "#FF4B4B"),
        "sin_dato": ("⚪", "#9E9E9E"),
    }
    icon, color = status_map.get(status, ("⚪", "#9E9E9E"))

    att_str = f"{att_val*100:.1f}%" if att_val is not None else "S/D"
    contrib_str = f"+{contrib:.1f}pp" if contrib is not None else "—"

    with col:
        st.markdown(f"""
        <div style="background:#F8F9FA;border-radius:8px;padding:0.8rem;border-top:3px solid {color};border:1px solid #E0E0E0">
            <div style="font-size:0.7rem;color:#666">{label}</div>
            <div style="font-size:1.1rem;color:{color};font-weight:bold">{icon} {att_str}</div>
            <div style="font-size:0.75rem;color:#555">Contribuye: {contrib_str}</div>
        </div>
        """, unsafe_allow_html=True)

# ── Recomendaciones ───────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🎯 Plan de acción recomendado")
st.caption("Basado en el cruce entre métricas, productividad y compensación")

recs = generar_recomendaciones(data, sems)
for rec in recs:
    st.markdown(f"- {rec}")

# Net Revenue context
net_rev = data.get("Net_Rev_Adj")
progreso_pct = data.get("progreso_pct", 0)
if net_rev is not None:
    if net_rev >= 0:
        st.success(f"✅ Net Revenue adelantado {net_rev:+.1f} pp del ritmo esperado ({progreso_pct:.1f}%). Mantener el paso.")
    else:
        weeks_left = (30 - dia_corte) // 7
        st.error(f"📉 Net Revenue {net_rev:+.1f} pp vs ritmo. Quedan aprox. {weeks_left} semanas — necesita acelerar para no penalizar el Revenue Share ADS.")
