import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.metrics import (
    calcular_compensacion_completa, calcular_variable_score,
    calcular_revenue_share_ads, EMOJI, COLOR_HEX, REVENUE_SHARE_CAP_MONTHLY
)
from core.auth import require_auth

st.set_page_config(page_title="Compensación", page_icon="💰", layout="wide")
email, is_supervisor = require_auth()

st.markdown("# 💰 Compensación Variable — Calculadora en tiempo real")
st.caption("""
**Estructura:** ADS Revenue 35% | Markdown Total 20% | Markdown Pro 20% | Churn x AVA 25%
**Qualifier:** Productividad ≥ 90% (Zoho Voice + Treble + Meets). Si <90% → pierde TODO el variable.
**Revenue Share ADS:** 10% (90–100%) / 20% (100–120%) / 30% (>120%) — cap $2k/mes, $5k/trim.
**Penalidad ADS:** No cuenta revenue de aliados con inversión ADS ≥ 70% de su GMV.
""")

if "farmers_data" not in st.session_state:
    st.warning("Carga el Sheet Maestro en la página principal primero.")
    st.stop()

farmers_data = st.session_state["farmers_data"]

# ── Build compensation table ──────────────────────────────────────────────────
st.markdown("## Ranking de compensación del equipo")

rows = []
for email, data in farmers_data.items():
    comp = calcular_compensacion_completa(data)
    rs = comp.get("rs_ads", {})
    name = data.get("name", email)

    att_churn = data.get("ATT_Churn")
    att_md = data.get("ATT_MD_Total")
    att_md_pro = data.get("ATT_MD_Pro")
    att_ads = data.get("ATT_Rev_real")

    def fmt_att(v):
        return f"{v*100:.1f}%" if v is not None else "S/D"

    rows.append({
        "_email": email,
        "Farmer": name,
        "Churn (25%)": fmt_att(att_churn),
        "MD Total (20%)": fmt_att(att_md),
        "MD Pro (20%)": fmt_att(att_md_pro),
        "ADS Rev (35%)": fmt_att(att_ads),
        "Qualifier": "✅" if comp.get("qualifies", True) else "⛔ NO",
        "Variable %": comp.get("variable_pct", 0),
        "RS ADS": rs.get("pct", 0),
        "RS Label": rs.get("label", "—"),
        "_qualifies": comp.get("qualifies", True),
    })

df = pd.DataFrame(rows).sort_values("Variable %", ascending=False)

# Color rows
def color_variable(val):
    if val >= 80:
        return "color: #4CAF50; font-weight: bold"
    elif val >= 50:
        return "color: #FFA726; font-weight: bold"
    return "color: #FF4B4B; font-weight: bold"

display_cols = ["Farmer", "Churn (25%)", "MD Total (20%)", "MD Pro (20%)",
                "ADS Rev (35%)", "Qualifier", "Variable %", "RS ADS", "RS Label"]

st.dataframe(
    df[display_cols].style.applymap(color_variable, subset=["Variable %"]),
    use_container_width=True, hide_index=True
)

# ── Summary metrics ───────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
with col1:
    max_rs = df[df["RS ADS"] == 30]
    st.metric("🔥 En tier 30% RS ADS", len(max_rs))
with col2:
    no_qual = (~df["_qualifies"]).sum()
    st.metric("⛔ Sin qualifier", int(no_qual), help="Pierden TODO el variable")
with col3:
    avg_var = df["Variable %"].mean()
    st.metric("📊 Variable promedio equipo", f"{avg_var:.0f}%")
with col4:
    full_var = (df["Variable %"] >= 90).sum()
    st.metric("💯 Variable ≥ 90%", int(full_var))

# ── Revenue Share ADS distribution ───────────────────────────────────────────
st.markdown("---")
st.markdown("## Distribución Revenue Share ADS")

rs_counts = df["RS ADS"].value_counts().reset_index()
rs_counts.columns = ["RS %", "Farmers"]
rs_label_map = {0: "No aplica (< 90%)", 10: "10% (90–100%)", 20: "20% (100–120%)", 30: "30% (> 120%)"}
rs_color_map = {0: "#FF4B4B", 10: "#FFA726", 20: "#4CAF50", 30: "#00E676"}

fig_rs = go.Figure(go.Bar(
    x=[rs_label_map.get(r, str(r)) for r in rs_counts["RS %"]],
    y=rs_counts["Farmers"],
    marker_color=[rs_color_map.get(r, "#9E9E9E") for r in rs_counts["RS %"]],
    text=rs_counts["Farmers"],
    textposition="outside",
))
fig_rs.update_layout(
    height=300,
    margin=dict(l=10, r=10, t=30, b=10),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    showlegend=False,
    yaxis_title="# Farmers",
)
st.plotly_chart(fig_rs, use_container_width=True)

# ── Variable waterfall per farmer ─────────────────────────────────────────────
st.markdown("---")
st.markdown("## Simulador individual de variable")
st.caption("Ajusta los ATTs para proyectar el efecto en la compensación")

names_map = {data.get("name", e): e for e, data in farmers_data.items()}
selected_name = st.selectbox("Farmer a simular", sorted(names_map.keys()))
email_sim = names_map[selected_name]
data_sim = farmers_data[email_sim]

c1, c2, c3, c4, c5 = st.columns(5)

def att_slider(col, label, key_val, current_data_key):
    current = current_data_key and data_sim.get(current_data_key)
    default = round(current * 100) if current else 85
    with col:
        return st.slider(label, 0, 150, default, 1, help=f"Actual: {default}%") / 100

att_churn_sim = att_slider(c1, "Churn ATT %", "churn_sim", "ATT_Churn")
att_md_sim    = att_slider(c2, "MD Total ATT %", "md_sim", "ATT_MD_Total")
att_md_pro_sim = att_slider(c3, "MD Pro ATT %", "mdpro_sim", "ATT_MD_Pro")
att_ads_sim   = att_slider(c4, "ADS Rev ATT %", "ads_sim", "ATT_Rev_real")

prod_pct_sim = None
with c5:
    total_f = data_sim.get("total_follows") or 0
    no_c = data_sim.get("no_contactados") or 0
    prod_actual = round((total_f - no_c) / total_f * 100) if total_f > 0 else 85
    prod_pct_sim = st.slider("Productividad %", 0, 100, prod_actual, 1,
                              help="Solo contactos efectivos: Zoho Voice + Treble + Meets") / 100

comp_sim = calcular_variable_score(att_ads_sim, att_md_sim, att_md_pro_sim, att_churn_sim, prod_pct_sim)
rs_sim = calcular_revenue_share_ads(att_ads_sim)

sim_cols = st.columns(4)
var_pct_sim = comp_sim["variable_pct"]
var_color = "#4CAF50" if var_pct_sim >= 80 else "#FFA726" if var_pct_sim >= 50 else "#FF4B4B"

with sim_cols[0]:
    st.markdown(f"""
    <div style="background:#F8F9FA;border-radius:10px;padding:1.2rem;text-align:center;border-top:4px solid {var_color};border:1px solid #E0E0E0">
        <div style="font-size:0.8rem;color:#666">Variable simulado</div>
        <div style="font-size:2.5rem;font-weight:bold;color:{var_color}">{var_pct_sim:.0f}%</div>
        <div style="font-size:0.8rem;color:#555">{'⛔ SIN QUALIFIER' if not comp_sim['qualifies'] else '✅ Qualificado'}</div>
    </div>
    """, unsafe_allow_html=True)

with sim_cols[1]:
    rs_pct_sim = rs_sim["pct"]
    rs_color_sim = "#4CAF50" if rs_pct_sim >= 20 else "#FFA726" if rs_pct_sim > 0 else "#FF4B4B"
    st.markdown(f"""
    <div style="background:#F8F9FA;border-radius:10px;padding:1.2rem;text-align:center;border-top:4px solid {rs_color_sim};border:1px solid #E0E0E0">
        <div style="font-size:0.8rem;color:#666">Revenue Share ADS</div>
        <div style="font-size:2.5rem;font-weight:bold;color:{rs_color_sim}">{rs_pct_sim}%</div>
        <div style="font-size:0.75rem;color:#555">{rs_sim['label']}</div>
    </div>
    """, unsafe_allow_html=True)

with sim_cols[2]:
    # Gap to next RS tier
    if att_ads_sim < 0.90:
        gap = (0.90 - att_ads_sim) * 100
        msg = f"Faltan {gap:.1f}pp para ganar RS ADS (10%)"
        mc = "#FFA726"
    elif att_ads_sim < 1.00:
        gap = (1.00 - att_ads_sim) * 100
        msg = f"Faltan {gap:.1f}pp para tier 20%"
        mc = "#FFA726"
    elif att_ads_sim < 1.20:
        gap = (1.20 - att_ads_sim) * 100
        msg = f"Faltan {gap:.1f}pp para tier 30% 🔥"
        mc = "#4CAF50"
    else:
        msg = "🔥 En tier máximo 30%"
        mc = "#00E676"

    st.markdown(f"""
    <div style="background:#F8F9FA;border-radius:10px;padding:1.2rem;text-align:center;border-top:4px solid {mc};border:1px solid #E0E0E0">
        <div style="font-size:0.8rem;color:#666">Gap al próximo tier</div>
        <div style="font-size:1rem;font-weight:bold;color:{mc};margin-top:0.5rem">{msg}</div>
    </div>
    """, unsafe_allow_html=True)

with sim_cols[3]:
    # Contribution waterfall
    contribs = comp_sim.get("contributions", {})
    total_contrib = sum(v for v in contribs.values() if v is not None)
    kpi_names = {"ADS_Rev": "ADS", "MD_Total": "MD", "MD_Pro": "MD Pro", "Churn": "Churn"}
    labels = [kpi_names.get(k, k) for k in contribs]
    values = [v if v is not None else 0 for v in contribs.values()]
    colors_bar = ["#4CAF50" if v > 0 else "#FF4B4B" for v in values]

    fig_w = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=colors_bar,
        text=[f"{v:.1f}pp" for v in values],
        textposition="outside",
    ))
    fig_w.update_layout(
        height=180, margin=dict(l=5, r=5, t=20, b=5),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=10),
        title=dict(text="Contribución por KPI", font=dict(size=10)),
        showlegend=False, yaxis_title="pp al variable",
    )
    st.plotly_chart(fig_w, use_container_width=True)

# ── Key rules callout ─────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📋 Reglas clave de compensación")

col_r1, col_r2 = st.columns(2)
with col_r1:
    st.markdown("""
    **Qualifier de productividad:**
    - Mide **solo** contactos efectivos de Zoho Voice, Treble y Videoconferencia (Meets)
    - Si < 90% → pierde el **100% del variable**, sin importar sus ATTs
    - Es la palanca de mayor riesgo para el farmer

    **Caps ADS Revenue:**
    - Máximo **$2,000 USD/mes** en Revenue Share
    - Máximo **$5,000 USD/trimestre**
    """)
with col_r2:
    st.markdown("""
    **Penalidad RS ADS:**
    - No suma el revenue de aliados con inversión ADS ≥ 70% de su GMV
    - Impacta directamente el ATT de ADS Revenue

    **Pesos y límites:**
    | KPI | Peso | Mín | Máx |
    |---|---|---|---|
    | ADS Revenue | 35% | 80% | 100% |
    | MD Total | 20% | 80% | 150% |
    | MD Pro | 20% | 80% | 150% |
    | Churn x AVA | 25% | 80% | 150% |
    """)
