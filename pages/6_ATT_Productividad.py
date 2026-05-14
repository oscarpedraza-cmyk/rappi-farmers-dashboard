import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.loader import FARMER_NAMES, FARMERS_EMAILS, EXCLUDED_EMAILS
from core.auth import require_auth

st.set_page_config(page_title="ATT Productividad", page_icon="📋", layout="wide")
email, is_supervisor = require_auth()

st.markdown("# 📋 ATT Productividad")
st.caption("Attainment de productividad por farmer considerando descuentos y ajustes del período.")

if "farmers_data" not in st.session_state:
    st.warning("Carga el Sheet Maestro en la página principal primero.")
    st.stop()

# ── Check if new sheet data was loaded ───────────────────────────────────────
farmers_data = st.session_state["farmers_data"]
dia_corte    = st.session_state.get("dia_corte", 13)

# Collect ATT Prod Sheet data from farmers_data
att_rows = []
for email, data in farmers_data.items():
    if data.get("ATT_Prod_Sheet") is not None:
        att_rows.append({
            "email": email,
            "Farmer": data.get("name", email),
            "ATT Productividad": data["ATT_Prod_Sheet"],
        })

# ── Also try to read the raw sheet from the uploaded file ─────────────────────
# Re-read directly from session so we get full sheet content
raw_file = st.session_state.get("_productividad_raw")

has_att_sheet = len(att_rows) > 0

if not has_att_sheet:
    st.info("""
    **La pestaña 'ATT productividad' no fue encontrada en el archivo subido**,
    o no contiene emails de farmers reconocidos.

    💡 Asegúrate de que:
    - La pestaña se llama exactamente **ATT productividad**
    - Contiene correos `@rappi.com` en alguna columna
    - El archivo fue subido **después** de crear esta nueva pestaña en el Excel

    Sube el archivo actualizado en la página principal y regresa aquí.
    """)

    # Show productividad_pct from loader as fallback
    st.markdown("---")
    st.markdown("## Productividad actual (desde hoja Productividad)")
    st.caption("Datos de contactos efectivos: Zoho Voice + Treble + Meets — qualifier para variable")

    prod_rows = []
    for email, data in farmers_data.items():
        p = data.get("productividad_pct")
        prod_rows.append({
            "Farmer": data.get("name", email),
            "Productividad %": round(p * 100, 1) if p is not None else None,
            "Qualifier": "✅ OK" if (p is not None and p >= 0.90) else ("⛔ PIERDE VARIABLE" if p is not None else "⚪ Sin dato"),
            "Follows totales": data.get("total_follows"),
            "Sin contactar": data.get("no_contactados"),
            "% Sin contactar": data.get("pct_no_contactados"),
        })

    df_prod = pd.DataFrame(prod_rows).sort_values("Productividad %", ascending=False, na_position="last")

    def color_prod(val):
        try:
            v = float(val)
            if v >= 90: return "color:#2E7D32;font-weight:bold"
            if v >= 80: return "color:#E65100;font-weight:bold"
            return "color:#C62828;font-weight:bold"
        except: return ""

    st.dataframe(
        df_prod.style.applymap(color_prod, subset=["Productividad %"]),
        use_container_width=True, hide_index=True
    )

    # Bar chart
    df_plot = df_prod.dropna(subset=["Productividad %"]).copy()
    colors = ["#2E7D32" if v >= 90 else "#E65100" if v >= 80 else "#C62828" for v in df_plot["Productividad %"]]

    fig = go.Figure(go.Bar(
        y=df_plot["Farmer"], x=df_plot["Productividad %"],
        orientation="h",
        marker_color=colors,
        text=df_plot["Productividad %"].apply(lambda v: f"{v:.1f}%"),
        textposition="outside",
    ))
    fig.add_vline(x=90, line_dash="dash", line_color="#FF6B00", opacity=0.7,
                  annotation_text="Qualifier 90%")
    fig.update_layout(
        height=max(300, len(df_plot) * 32),
        margin=dict(l=10, r=60, t=20, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Productividad %",
        xaxis=dict(range=[0, max(115, df_plot["Productividad %"].max() + 5)]),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.stop()

# ── Has ATT sheet data ────────────────────────────────────────────────────────
df_att = pd.DataFrame(att_rows).sort_values("ATT Productividad", ascending=False)
df_att["ATT %"] = (df_att["ATT Productividad"] * 100).round(1)
df_att["Qualifier"] = df_att["ATT Productividad"].apply(
    lambda v: "✅ OK" if v >= 0.90 else "⛔ PIERDE VARIABLE"
)

# ── Summary metrics ───────────────────────────────────────────────────────────
total = len(df_att)
qualifiers = (df_att["ATT Productividad"] >= 0.90).sum()
no_qualif  = total - qualifiers
avg_att    = df_att["ATT Productividad"].mean() * 100

col1, col2, col3, col4 = st.columns(4)
with col1: st.metric("👥 Farmers con dato", total)
with col2: st.metric("✅ Con qualifier", int(qualifiers), help="ATT productividad ≥ 90%")
with col3: st.metric("⛔ Sin qualifier", int(no_qualif), help="Pierde variable completo")
with col4: st.metric("📊 ATT promedio", f"{avg_att:.1f}%")

st.markdown("---")

# ── Bar chart ─────────────────────────────────────────────────────────────────
colors = ["#2E7D32" if v >= 90 else "#E65100" if v >= 80 else "#C62828" for v in df_att["ATT %"]]

fig = go.Figure(go.Bar(
    y=df_att["Farmer"], x=df_att["ATT %"],
    orientation="h",
    marker_color=colors,
    text=df_att["ATT %"].apply(lambda v: f"{v:.1f}%"),
    textposition="outside",
))
fig.add_vline(x=90, line_dash="dash", line_color="#FF6B00", opacity=0.8,
              annotation_text="Qualifier 90%", annotation_position="top")
fig.update_layout(
    height=max(300, len(df_att) * 35),
    margin=dict(l=10, r=60, t=30, b=10),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    xaxis_title="ATT Productividad %",
    xaxis=dict(range=[0, max(115, df_att["ATT %"].max() + 5)]),
)
st.plotly_chart(fig, use_container_width=True)

# ── Table ─────────────────────────────────────────────────────────────────────
st.markdown("### Detalle por farmer")

# Also merge with productividad_pct from loader
extra = []
for email, data in farmers_data.items():
    p = data.get("productividad_pct")
    extra.append({"email": email, "Prod. Zoho/Treble/Meets": round(p * 100, 1) if p is not None else None})
df_extra = pd.DataFrame(extra)

df_display = df_att.merge(df_extra, on="email", how="left")
df_display = df_display[["Farmer", "ATT %", "Qualifier", "Prod. Zoho/Treble/Meets"]].copy()

def color_att(val):
    try:
        v = float(val)
        if v >= 90: return "color:#2E7D32;font-weight:bold"
        if v >= 80: return "color:#E65100;font-weight:bold"
        return "color:#C62828;font-weight:bold"
    except: return ""

st.dataframe(
    df_display.style.applymap(color_att, subset=["ATT %"]),
    use_container_width=True, hide_index=True
)

# ── Farmers in risk ───────────────────────────────────────────────────────────
at_risk = df_att[df_att["ATT Productividad"] < 0.90]
if not at_risk.empty:
    st.markdown("---")
    st.error(f"### 🚨 {len(at_risk)} farmers bajo el qualifier (< 90%)")
    for _, row in at_risk.iterrows():
        diff = (0.90 - row["ATT Productividad"]) * 100
        st.markdown(f"- **{row['Farmer']}**: {row['ATT %']:.1f}% — faltan **{diff:.1f} pp** para no perder el variable")
else:
    st.success("✅ Todo el equipo supera el qualifier de productividad (≥ 90%)")
