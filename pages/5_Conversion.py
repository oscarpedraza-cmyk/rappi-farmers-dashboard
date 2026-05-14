import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.loader import FARMER_NAMES, FARMERS_EMAILS, EXCLUDED_EMAILS
from core.metrics import QUARTILE_COLOR, QUARTILE_LABEL, score_farmer, assign_quartiles, get_all_semaforos, calcular_compensacion_completa

st.set_page_config(page_title="Conversión", page_icon="🎯", layout="wide")

st.markdown("# 🎯 Conversión Comercial")
st.caption("Embudo por palanca: Oportunidades → Contactados → Contrataciones. Promedio de conversión por farmer y por métrica.")

if "farmers_data" not in st.session_state:
    st.warning("Carga el Sheet Maestro en la página principal primero.")
    st.stop()

# ── Load raw Productividad ────────────────────────────────────────────────────
uploaded = st.session_state.get("_last_uploaded_file")

# We re-read the file from session if available
raw_prod = st.session_state.get("_productividad_raw")

if raw_prod is None:
    st.info("Vuelve a subir el Sheet Maestro para ver la conversión detallada.")
    st.stop()

df = raw_prod.copy()

# ── Conversion logic ──────────────────────────────────────────────────────────
# MD:    col 26 == SI,  contrato = col 32 == "Si"
# Ads:   col 35 == SI,  contrato = col 36 in positive Ads types
# Churn: col 40 == SI,  contrato = col 46 not NaN (Fecha Reactivación)

FARMER_COL   = 14
CONTACT_COL  = 4
MD_COL       = 26
MD_ACEPT_COL = 32   # ¿Se aceptó lo ofrecido?
ADS_COL      = 35
ADS_TIPO_COL = 36   # Tipo Ads
ADS_NEVER_COL= 39   # Tipo Never Ads
CHURN_COL    = 40
CHURN_REAC_COL = 46 # Fecha Reactivación

ADS_POSITIVE = {"upselling", "reactivación", "retention"}
ADS_NEVER_POS = {"activo con coinversión", "activo sin coinversión"}

ACTIVE_FARMERS = set(FARMERS_EMAILS) - EXCLUDED_EMAILS

def is_contacted(row):
    return str(row[CONTACT_COL]).strip().upper() != "NO"

def is_md_contrato(row):
    return str(row[MD_ACEPT_COL]).strip().lower() == "si"

def is_ads_contrato(row):
    tipo = str(row[ADS_TIPO_COL]).strip().lower()
    never = str(row[ADS_NEVER_COL]).strip().lower()
    if tipo in ADS_POSITIVE:
        return True
    if tipo == "never ads" and never in ADS_NEVER_POS:
        return True
    return False

def is_churn_retencion(row):
    val = row[CHURN_REAC_COL]
    return pd.notna(val) and str(val).strip() not in ("", "nan", "NaT")

# ── Build conversion table ────────────────────────────────────────────────────
results = []
for farmer_email, sub in df.groupby(FARMER_COL):
    farmer_email = str(farmer_email).strip().lower()
    if farmer_email not in ACTIVE_FARMERS:
        continue

    name = FARMER_NAMES.get(farmer_email, farmer_email.split("@")[0].title())

    for palanca_name, palanca_col, contrato_fn in [
        ("MD",    MD_COL,    is_md_contrato),
        ("Ads",   ADS_COL,   is_ads_contrato),
        ("Churn", CHURN_COL, is_churn_retencion),
    ]:
        p_sub = sub[sub[palanca_col].astype(str).str.upper() == "SI"]
        oportunidades = len(p_sub)
        contactados   = p_sub.apply(is_contacted, axis=1).sum()
        contratos     = p_sub.apply(contrato_fn, axis=1).sum()

        conv_total    = round(contratos / oportunidades * 100, 1) if oportunidades > 0 else 0
        conv_efectiva = round(contratos / contactados * 100, 1)   if contactados > 0 else 0

        results.append({
            "email":          farmer_email,
            "Farmer":         name,
            "Palanca":        palanca_name,
            "Oportunidades":  int(oportunidades),
            "Contactados":    int(contactados),
            "No contactados": int(oportunidades - contactados),
            "Contratos":      int(contratos),
            "Conv. total %":  conv_total,
            "Conv. efectiva %": conv_efectiva,
        })

df_conv = pd.DataFrame(results)

if df_conv.empty:
    st.error("No se encontraron datos de conversión en el archivo.")
    st.stop()

# ── Quartiles from session ────────────────────────────────────────────────────
farmers_data = st.session_state["farmers_data"]
all_scores = {}
for farmer, data in farmers_data.items():
    sems = get_all_semaforos(data)
    comp = calcular_compensacion_completa(data)
    all_scores[farmer] = score_farmer(sems, comp)
quartiles = assign_quartiles(all_scores)

df_conv["Quartil"] = df_conv["email"].map(lambda e: quartiles.get(e, "Q4"))

# ── Team averages ─────────────────────────────────────────────────────────────
st.markdown("## Promedio de conversión del equipo")

for palanca in ["MD", "Ads", "Churn"]:
    sub = df_conv[df_conv["Palanca"] == palanca]
    avg_total    = sub["Conv. total %"].mean()
    avg_efectiva = sub["Conv. efectiva %"].mean()
    total_ops    = sub["Oportunidades"].sum()
    total_cont   = sub["Contratos"].sum()
    st.session_state[f"avg_conv_{palanca}"] = avg_total

col_md, col_ads, col_churn = st.columns(3)
for col, palanca, icon in [(col_md, "MD", "💰"), (col_ads, "Ads", "📢"), (col_churn, "Churn", "🔄")]:
    sub = df_conv[df_conv["Palanca"] == palanca]
    avg_t  = sub["Conv. total %"].mean()
    avg_e  = sub["Conv. efectiva %"].mean()
    ops    = sub["Oportunidades"].sum()
    contr  = sub["Contratos"].sum()
    c      = "#4CAF50" if avg_t >= 30 else "#FFA726" if avg_t >= 15 else "#FF4B4B"

    with col:
        st.markdown(f"""
        <div style="background:#1E1E2E;border-radius:12px;padding:1.2rem;border-top:4px solid {c}">
            <div style="font-size:0.85rem;color:#aaa">{icon} {palanca} — Promedio equipo</div>
            <div style="font-size:2.2rem;font-weight:bold;color:{c};margin:0.3rem 0">{avg_t:.1f}%</div>
            <div style="font-size:0.8rem;color:#ccc">Conv. sobre contactados: <b>{avg_e:.1f}%</b></div>
            <div style="font-size:0.75rem;color:#888;margin-top:4px">{int(contr)} contratos / {int(ops)} oportunidades</div>
        </div>
        """, unsafe_allow_html=True)

# ── Funnel charts by palanca ──────────────────────────────────────────────────
st.markdown("---")
st.markdown("## Embudo por palanca")

tabs = st.tabs(["💰 MD (Markdown)", "📢 Ads", "🔄 Churn (Retención)"])

for tab, palanca in zip(tabs, ["MD", "Ads", "Churn"]):
    with tab:
        sub = df_conv[df_conv["Palanca"] == palanca].copy()
        sub = sub.sort_values("Conv. total %", ascending=False)

        # Bar chart — funnel per farmer
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Oportunidades",
            x=sub["Farmer"], y=sub["Oportunidades"],
            marker_color="#37474F", opacity=0.7,
        ))
        fig.add_trace(go.Bar(
            name="Contactados",
            x=sub["Farmer"], y=sub["Contactados"],
            marker_color="#1565C0", opacity=0.85,
        ))
        fig.add_trace(go.Bar(
            name="Contratos",
            x=sub["Farmer"], y=sub["Contratos"],
            marker_color="#4CAF50",
            text=sub["Conv. total %"].apply(lambda v: f"{v:.0f}%"),
            textposition="outside",
        ))

        fig.update_layout(
            barmode="overlay",
            height=380,
            margin=dict(l=10, r=10, t=30, b=80),
            plot_bgcolor="#0F0F1A",
            paper_bgcolor="#0F0F1A",
            font=dict(color="white"),
            legend=dict(orientation="h", y=1.1),
            xaxis_tickangle=-35,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Conversion rate chart
        avg_t = sub["Conv. total %"].mean()
        colors = ["#4CAF50" if v >= avg_t else "#FF4B4B" for v in sub["Conv. total %"]]

        fig2 = go.Figure(go.Bar(
            x=sub["Farmer"],
            y=sub["Conv. total %"],
            marker_color=colors,
            text=sub["Conv. total %"].apply(lambda v: f"{v:.1f}%"),
            textposition="outside",
        ))
        fig2.add_hline(y=avg_t, line_dash="dash", line_color="white",
                       opacity=0.5, annotation_text=f"Promedio {avg_t:.1f}%")
        fig2.update_layout(
            title="% Conversión total (contratos / oportunidades)",
            height=320,
            margin=dict(l=10, r=10, t=40, b=80),
            plot_bgcolor="#0F0F1A", paper_bgcolor="#0F0F1A",
            font=dict(color="white"),
            xaxis_tickangle=-35,
        )
        st.plotly_chart(fig2, use_container_width=True)

        # Detail table
        st.markdown(f"#### Tabla detalle — {palanca}")
        display = sub[["Quartil", "Farmer", "Oportunidades", "Contactados",
                        "No contactados", "Contratos", "Conv. total %", "Conv. efectiva %"]].copy()
        display = display.rename(columns={
            "Conv. total %": "Conv. Total %",
            "Conv. efectiva %": "Conv. Efectiva %"
        })

        def color_conv(val):
            try:
                v = float(val)
                if v >= 30: return "color: #4CAF50; font-weight: bold"
                if v >= 15: return "color: #FFA726; font-weight: bold"
                return "color: #FF4B4B; font-weight: bold"
            except: return ""

        st.dataframe(
            display.style.applymap(color_conv, subset=["Conv. Total %", "Conv. Efectiva %"]),
            use_container_width=True, hide_index=True
        )

# ── Ranking global de conversión ──────────────────────────────────────────────
st.markdown("---")
st.markdown("## 🏆 Ranking global de conversión")
st.caption("Score compuesto: MD (40%) + Ads (35%) + Churn (25%) — pesos según impacto en variable")

pivot = df_conv.pivot_table(
    index=["email", "Farmer", "Quartil"],
    columns="Palanca",
    values="Conv. total %",
    aggfunc="first"
).reset_index()

# Fill missing
for p in ["MD", "Ads", "Churn"]:
    if p not in pivot.columns:
        pivot[p] = 0
    pivot[p] = pivot[p].fillna(0)

pivot["Score Conversión"] = (
    pivot["MD"]    * 0.40 +
    pivot["Ads"]   * 0.35 +
    pivot["Churn"] * 0.25
).round(1)

pivot = pivot.sort_values("Score Conversión", ascending=False)
pivot["Rank"] = range(1, len(pivot) + 1)

# Radar chart — top vs bottom
st.markdown("#### Radar de conversión — Top 3 vs Bottom 3")
top3    = pivot.head(3)
bottom3 = pivot.tail(3)
categories = ["MD %", "Ads %", "Churn %"]

fig_radar = go.Figure()
for _, row in top3.iterrows():
    vals = [row["MD"], row["Ads"], row["Churn"]]
    fig_radar.add_trace(go.Scatterpolar(
        r=vals + [vals[0]], theta=categories + [categories[0]],
        fill="toself", name=row["Farmer"],
        opacity=0.7, line=dict(width=2),
    ))
for _, row in bottom3.iterrows():
    vals = [row["MD"], row["Ads"], row["Churn"]]
    fig_radar.add_trace(go.Scatterpolar(
        r=vals + [vals[0]], theta=categories + [categories[0]],
        fill="toself", name=f"⚠️ {row['Farmer']}",
        opacity=0.4, line=dict(width=1, dash="dot"),
    ))

fig_radar.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 60])),
    height=420,
    paper_bgcolor="#0F0F1A",
    plot_bgcolor="#0F0F1A",
    font=dict(color="white"),
    legend=dict(orientation="h", y=-0.15),
)
st.plotly_chart(fig_radar, use_container_width=True)

# Final ranking table
st.markdown("#### Tabla ranking")
ranking = pivot[["Rank", "Quartil", "Farmer", "MD", "Ads", "Churn", "Score Conversión"]].copy()
ranking.columns = ["#", "Q", "Farmer", "MD %", "Ads %", "Churn %", "Score Conv."]

def color_score(val):
    try:
        v = float(val)
        if v >= 25: return "color:#4CAF50;font-weight:bold"
        if v >= 12: return "color:#FFA726;font-weight:bold"
        return "color:#FF4B4B;font-weight:bold"
    except: return ""

st.dataframe(
    ranking.style.applymap(color_score, subset=["MD %", "Ads %", "Churn %", "Score Conv."]),
    use_container_width=True, hide_index=True
)

# ── Insights automáticos ──────────────────────────────────────────────────────
st.markdown("---")
st.markdown("## 🧠 Insights de conversión")

best_md    = df_conv[df_conv["Palanca"]=="MD"].nlargest(1,"Conv. total %").iloc[0]
worst_md   = df_conv[df_conv["Palanca"]=="MD"].nsmallest(1,"Conv. total %").iloc[0]
best_ads   = df_conv[df_conv["Palanca"]=="Ads"].nlargest(1,"Conv. total %").iloc[0]
worst_ads  = df_conv[df_conv["Palanca"]=="Ads"].nsmallest(1,"Conv. total %").iloc[0]
best_churn = df_conv[df_conv["Palanca"]=="Churn"].nlargest(1,"Conv. total %").iloc[0]

avg_md    = df_conv[df_conv["Palanca"]=="MD"]["Conv. total %"].mean()
avg_ads   = df_conv[df_conv["Palanca"]=="Ads"]["Conv. total %"].mean()
avg_churn = df_conv[df_conv["Palanca"]=="Churn"]["Conv. total %"].mean()

gap_md  = best_md["Conv. total %"] - worst_md["Conv. total %"]
gap_ads = best_ads["Conv. total %"] - worst_ads["Conv. total %"]

col1, col2 = st.columns(2)
with col1:
    st.markdown(f"""
    **💰 MD — Mejor vs Peor conversión:**
    - 🏆 **{best_md['Farmer']}**: {best_md['Conv. total %']:.1f}%
    - 🚨 **{worst_md['Farmer']}**: {worst_md['Conv. total %']:.1f}%
    - Brecha: **{gap_md:.1f} pp** — oportunidad de acompañamiento pitch MD

    **📢 Ads — Mejor vs Peor:**
    - 🏆 **{best_ads['Farmer']}**: {best_ads['Conv. total %']:.1f}%
    - 🚨 **{worst_ads['Farmer']}**: {worst_ads['Conv. total %']:.1f}%
    - Brecha: **{gap_ads:.1f} pp** — revisar propuesta de valor ADS
    """)

with col2:
    low_conv_md = df_conv[(df_conv["Palanca"]=="MD") & (df_conv["Conv. total %"] < avg_md)]
    low_conv_ads = df_conv[(df_conv["Palanca"]=="Ads") & (df_conv["Conv. total %"] < avg_ads)]

    st.markdown(f"""
    **Farmers bajo el promedio en MD ({avg_md:.1f}%):**
    {", ".join(f"**{r['Farmer']}** ({r['Conv. total %']:.0f}%)" for _, r in low_conv_md.iterrows()) or "Ninguno"}

    **Farmers bajo el promedio en Ads ({avg_ads:.1f}%):**
    {", ".join(f"**{r['Farmer']}** ({r['Conv. total %']:.0f}%)" for _, r in low_conv_ads.iterrows()) or "Ninguno"}

    **🔄 Churn — Mejor retención:** {best_churn['Farmer']} ({best_churn['Conv. total %']:.1f}% de aliados reactivados)
    """)
