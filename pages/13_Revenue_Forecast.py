import streamlit as st
import io
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.loader import FARMER_NAMES, FARMERS_EMAILS, refresh_net_rev_adj
from core.auth import require_auth, render_topbar
from core.style import inject_global_css
from core.db import load_latest_state

st.set_page_config(
    page_title="Revenue Forecast — Rappi Farmers",
    page_icon="🚀",
    layout="wide",
)
st.markdown(inject_global_css(), unsafe_allow_html=True)
email, is_supervisor = require_auth()
render_topbar()

# ── Data bootstrap ────────────────────────────────────────────────────────────
if "farmers_data" not in st.session_state:
    latest = load_latest_state()
    if latest:
        st.session_state["farmers_data"] = latest["farmers_data"]
        st.session_state["dia_corte"]    = latest["dia_corte"]
        st.session_state["dias_mes"]     = latest["dias_mes"]
    else:
        st.warning("⏳ El supervisor aún no ha cargado datos. Vuelve más tarde o contacta a Oscar Pedraza.")
        st.stop()

farmers_data = st.session_state["farmers_data"]
dia_corte    = st.session_state.get("dia_corte", 13)
dias_mes     = st.session_state.get("dias_mes", 31)

try:
    refresh_net_rev_adj(farmers_data, dias_mes)
except Exception:
    pass

# Pace del mes: % del mes ya transcurrido al día de corte
progreso_pct = round((dia_corte - 1) / dias_mes * 100, 1)
dias_restantes = max(1, dias_mes - dia_corte + 1)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="rb-page-header">
    <h1>📈 Revenue Forecast — ADS</h1>
    <p>Proyección de cierre de mes para ADS Revenue. Día de corte: {dia_corte}/{dias_mes}
       · {progreso_pct:.0f}% del mes transcurrido · {dias_restantes} días restantes.</p>
</div>
""", unsafe_allow_html=True)

# ── Build forecast table ──────────────────────────────────────────────────────
rows = []
for em, data in farmers_data.items():
    att = data.get("ATT_Rev_real")
    if att is None:
        continue
    try:
        att_f = float(att)
    except (TypeError, ValueError):
        continue

    att_pct    = round(att_f * 100, 1)                        # actual % logrado
    paced_pct  = round(att_f / max(0.01, progreso_pct / 100) * 100, 1)  # ritmo actual al 100% del mes
    gap_pp     = round(max(0.0, 100.0 - att_pct), 1)          # pp que faltan para llegar a 100%
    net_adj    = data.get("Net_Rev_Adj")                       # pp por encima/debajo del pace
    net_adj_f  = round(float(net_adj), 1) if net_adj is not None else None

    # Status basado en pace proyectado
    if paced_pct >= 95:
        status = "🟢 On Track"
    elif paced_pct >= 80:
        status = "🟡 At Risk"
    else:
        status = "🔴 Crítico"

    rows.append({
        "email":       em,
        "Farmer":      data.get("name", FARMER_NAMES.get(em, em.split("@")[0].title())),
        "ATT Actual %":  att_pct,
        "Pace al 100% →": paced_pct,
        "Gap pp":      gap_pp,
        "Net Rev Adj": net_adj_f,
        "Estado":      status,
    })

if not rows:
    st.error("""
    **Sin datos de ADS Revenue.**

    Posibles causas:
    - La hoja **Ads** no existe en el Excel o está vacía
    - La columna de ATT Revenue Real (col 14) no tiene datos
    """)
    st.stop()

df = pd.DataFrame(rows).sort_values("Pace al 100% →", ascending=False)

# ── KPIs del equipo ───────────────────────────────────────────────────────────
avg_att   = df["ATT Actual %"].mean()
avg_pace  = df["Pace al 100% →"].mean()
on_track  = (df["Pace al 100% →"] >= 95).sum()
at_risk   = ((df["Pace al 100% →"] >= 80) & (df["Pace al 100% →"] < 95)).sum()
critical  = (df["Pace al 100% →"] < 80).sum()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📊 ATT promedio equipo",  f"{avg_att:.1f}%")
c2.metric("🎯 Pace proyectado",      f"{avg_pace:.1f}%")
c3.metric("🟢 On Track (≥95%)",      int(on_track))
c4.metric("🟡 At Risk (80–95%)",     int(at_risk))
c5.metric("🔴 Críticos (<80%)",      int(critical))

st.markdown("---")

# ── Bullet/gauge chart — ATT actual vs pace proyectado ───────────────────────
st.markdown("## Forecast por farmer")

df_chart = df.sort_values("ATT Actual %", ascending=True)

fig = go.Figure()

# Pace (barra fantasma, siempre detrás)
fig.add_trace(go.Bar(
    name="Pace proyectado al cierre",
    y=df_chart["Farmer"],
    x=df_chart["Pace al 100% →"],
    orientation="h",
    marker_color=[
        "#D1FAE5" if v >= 95 else "#FEF3C7" if v >= 80 else "#FEE2E2"
        for v in df_chart["Pace al 100% →"]
    ],
    opacity=0.5,
    hovertemplate="%{y}: pace %{x:.1f}%<extra>Pace proyectado</extra>",
))

# ATT real (barra sólida encima)
fig.add_trace(go.Bar(
    name="ATT actual",
    y=df_chart["Farmer"],
    x=df_chart["ATT Actual %"],
    orientation="h",
    marker_color=[
        "#00B341" if v >= 95 else "#F59E0B" if v >= 80 else "#EF4444"
        for v in df_chart["Pace al 100% →"]
    ],
    text=df_chart["ATT Actual %"].apply(lambda v: f"{v:.1f}%"),
    textposition="outside",
    hovertemplate="%{y}: ATT real %{x:.1f}%<extra>ATT actual</extra>",
))

fig.add_vline(x=100, line_dash="dash", line_color="#1A1A1A",
              opacity=0.4, annotation_text="Meta 100%", annotation_position="top")
fig.add_vline(x=progreso_pct, line_dash="dot", line_color="#4A6CF7",
              opacity=0.6,
              annotation_text=f"Pace día {dia_corte} ({progreso_pct:.0f}%)",
              annotation_position="bottom right")

fig.update_layout(
    barmode="overlay",
    height=max(320, len(df_chart) * 42),
    margin=dict(l=10, r=80, t=20, b=20),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(title="% Attainment ADS Revenue", range=[0, max(115, df_chart["Pace al 100% →"].max() + 12)]),
    legend=dict(orientation="h", y=1.06),
    showlegend=True,
)
st.plotly_chart(fig, use_container_width=True)

# ── Tabla detalle ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("## Detalle por farmer")

df_tbl = df[["Farmer", "ATT Actual %", "Pace al 100% →", "Gap pp", "Net Rev Adj", "Estado"]].copy()

st.data_editor(
    df_tbl,
    use_container_width=True,
    hide_index=True,
    disabled=True,
    column_config={
        "Farmer":          st.column_config.TextColumn("Farmer", width="medium"),
        "ATT Actual %":    st.column_config.ProgressColumn(
                               f"ATT actual (día {dia_corte})",
                               format="%.1f%%", min_value=0, max_value=120),
        "Pace al 100% →":  st.column_config.ProgressColumn(
                               "Pace → cierre mes",
                               format="%.1f%%", min_value=0, max_value=150),
        "Gap pp":          st.column_config.NumberColumn(
                               "Gap a 100%", format="%.1f pp", width="small"),
        "Net Rev Adj":     st.column_config.NumberColumn(
                               "Net Rev Adj (pp)", format="%+.1f",
                               help="ATT - pace del mes. Positivo = por encima del ritmo."),
        "Estado":          st.column_config.TextColumn("Estado", width="medium"),
    },
)

st.caption(
    f"Pace = ATT actual ÷ progreso del mes ({progreso_pct:.0f}%) × 100. "
    "Gap = pp que faltan para 100%. Net Rev Adj = ATT - pace día de corte."
)

# ── Callouts críticos ─────────────────────────────────────────────────────────
st.markdown("---")
df_crit = df[df["Pace al 100% →"] < 80].sort_values("Pace al 100% →")
df_risk_zone = df[(df["Pace al 100% →"] >= 80) & (df["Pace al 100% →"] < 95)].sort_values("Pace al 100% →")

if not df_crit.empty:
    st.markdown("### 🔴 Farmers críticos — acción urgente")
    for _, row in df_crit.iterrows():
        gap   = row["Gap pp"]
        pace  = row["Pace al 100% →"]
        st.error(
            f"**{row['Farmer']}** — ATT actual: {row['ATT Actual %']:.1f}% · "
            f"Pace proyectado: {pace:.1f}% · "
            f"Necesita cerrar **{gap:.1f} pp más** en {dias_restantes} días "
            f"para alcanzar el 100%"
        )

if not df_risk_zone.empty:
    st.markdown("### 🟡 Farmers en zona de riesgo")
    for _, row in df_risk_zone.iterrows():
        gap  = row["Gap pp"]
        pace = row["Pace al 100% →"]
        st.warning(
            f"**{row['Farmer']}** — ATT actual: {row['ATT Actual %']:.1f}% · "
            f"Pace proyectado: {pace:.1f}% · "
            f"Faltan **{gap:.1f} pp** en {dias_restantes} días"
        )

if df_crit.empty and df_risk_zone.empty:
    st.success("✅ Todo el equipo está en pace para cerrar el mes ≥ 95% de ADS Revenue.")
