import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.auth import require_auth
from core.style import inject_global_css

st.set_page_config(page_title="ATT Productividad — Rappi Farmers", page_icon="🚀", layout="wide")
st.markdown(inject_global_css(), unsafe_allow_html=True)
email_auth, is_supervisor = require_auth()

st.markdown("""
<div class="rb-page-header">
    <h1>📋 ATT Productividad</h1>
    <p>Contactos efectivos por farmer: Zoho Voice + Treble + Videoconferencia — qualifier para variable.</p>
</div>
""", unsafe_allow_html=True)

# ── Auto-load si session_state está vacío ─────────────────────────────────────
if "farmers_data" not in st.session_state:
    from core.db import load_latest_state
    latest = load_latest_state()
    if latest:
        st.session_state["farmers_data"] = latest["farmers_data"]
        st.session_state["dia_corte"]    = latest["dia_corte"]
        st.session_state["dias_mes"]     = latest["dias_mes"]
    else:
        st.warning("⏳ El supervisor aún no ha cargado datos para este período. Vuelve más tarde o contacta a Oscar Pedraza.")
        st.stop()

farmers_data = st.session_state["farmers_data"]

# ── Build table ───────────────────────────────────────────────────────────────
prod_rows = []
for em, data in farmers_data.items():
    p = data.get("productividad_pct")
    pct_nc = data.get("pct_no_contactados")
    prod_rows.append({
        "Farmer":          data.get("name", em),
        "Productividad %": f"{p*100:.1f}" if p is not None else None,
        "Qualifier":       "✅ OK" if (p is not None and p >= 0.90)
                           else ("⛔ PIERDE VARIABLE" if p is not None else "⚪ Sin dato"),
        "Follows totales": int(data.get("total_follows") or 0),
        "Sin contactar":   int(data.get("no_contactados") or 0),
        "% Sin contactar": f"{pct_nc:.1f}" if pct_nc is not None else None,
        "_prod_num":       round(p * 100, 1) if p is not None else None,  # para ordenar y graficar
    })

df = pd.DataFrame(prod_rows).sort_values("_prod_num", ascending=False, na_position="last")

# ── Summary metrics ───────────────────────────────────────────────────────────
df_valid   = df.dropna(subset=["_prod_num"])
qualifiers = (df_valid["_prod_num"] >= 90).sum()
no_qualif  = (df_valid["_prod_num"] < 90).sum()
avg_prod   = df_valid["_prod_num"].mean() if not df_valid.empty else 0
sin_dato   = df["_prod_num"].isna().sum()

col1, col2, col3, col4, col5 = st.columns(5)
with col1: st.metric("👥 Total farmers",    len(df))
with col2: st.metric("✅ Con qualifier",    int(qualifiers), help="Productividad ≥ 90%")
with col3: st.metric("⛔ Sin qualifier",    int(no_qualif),  help="Pierde variable completo")
with col4: st.metric("📊 Promedio equipo", f"{avg_prod:.1f}%")
with col5: st.metric("⚪ Sin dato",        int(sin_dato))

st.markdown("---")

# ── Bar chart ─────────────────────────────────────────────────────────────────
df_plot = df_valid.copy()
colors = ["#00C9A7" if v >= 90 else "#F59E0B" if v >= 80 else "#EF4444"
          for v in df_plot["_prod_num"]]

fig = go.Figure(go.Bar(
    y=df_plot["Farmer"],
    x=df_plot["_prod_num"],
    orientation="h",
    marker_color=colors,
    text=df_plot["_prod_num"].apply(lambda v: f"{v:.1f}%"),
    textposition="outside",
    hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
))
fig.add_vline(x=90, line_dash="dash", line_color="#E8281F", opacity=0.8,
              annotation_text="Qualifier 90%", annotation_position="top")
fig.update_layout(
    height=max(300, len(df_plot) * 36),
    margin=dict(l=10, r=70, t=20, b=10),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    xaxis_title="Productividad %",
    xaxis=dict(range=[0, max(115, df_plot["_prod_num"].max() + 10)]),
    showlegend=False,
)
st.plotly_chart(fig, use_container_width=True)

# ── Detail table ──────────────────────────────────────────────────────────────
st.markdown("### Detalle por farmer")

def color_prod(val):
    try:
        v = float(val)
        if v >= 90: return "color:#00B341;font-weight:bold"
        if v >= 80: return "color:#F59E0B;font-weight:bold"
        return "color:#EF4444;font-weight:bold"
    except:
        return ""

def color_pct_nc(val):
    try:
        v = float(val)
        if v <= 20: return "color:#00B341;font-weight:bold"
        if v <= 35: return "color:#F59E0B;font-weight:bold"
        return "color:#EF4444;font-weight:bold"
    except:
        return ""

display_cols = ["Farmer", "Productividad %", "Qualifier", "Follows totales", "Sin contactar", "% Sin contactar"]
st.dataframe(
    df[display_cols].style
      .map(color_prod,   subset=["Productividad %"])
      .map(color_pct_nc, subset=["% Sin contactar"]),
    use_container_width=True,
    hide_index=True,
)

# ── Farmers at risk ───────────────────────────────────────────────────────────
at_risk = df_valid[df_valid["_prod_num"] < 90].sort_values("_prod_num")
if not at_risk.empty:
    st.markdown("---")
    st.error(f"### 🚨 {len(at_risk)} farmers bajo el qualifier (< 90%)")
    for _, row in at_risk.iterrows():
        diff = 90 - row["_prod_num"]
        st.markdown(
            f"- **{row['Farmer']}**: {row['_prod_num']:.1f}% "
            f"— faltan **{diff:.1f} pp** para no perder el variable"
        )
else:
    st.success("✅ Todo el equipo supera el qualifier de productividad (≥ 90%)")
