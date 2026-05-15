import streamlit as st
import io
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.metrics import (get_all_semaforos, tier_farmer, EMOJI, COLOR_HEX,
                          calcular_compensacion_completa, score_farmer,
                          assign_quartiles, QUARTILE_COLOR, QUARTILE_LABEL)
from core.auth import require_auth, render_sidebar_user_badge
from core.style import inject_global_css

st.set_page_config(page_title="Vista Equipo — Rappi Farmers", page_icon="🚀", layout="wide")
st.markdown(inject_global_css(), unsafe_allow_html=True)
email, is_supervisor = require_auth()

st.markdown("""
<div class="rb-page-header">
    <h1>📊 Vista Equipo — Gerencia Comercial</h1>
    <p>Análisis macro: ¿dónde está roto el equipo y qué palanca duele más?</p>
</div>
""", unsafe_allow_html=True)

if "farmers_data" not in st.session_state:
    from core.db import load_latest_state
    latest = load_latest_state()
    if latest:
        st.session_state["farmers_data"]  = latest["farmers_data"]
        st.session_state["dia_corte"]     = latest["dia_corte"]
        st.session_state["dias_mes"]      = latest["dias_mes"]
        if latest.get("productividad_raw"):
            try:
                df_raw = pd.read_json(io.StringIO(latest["productividad_raw"]))
                df_raw.columns = [int(c) for c in df_raw.columns]
                st.session_state["_productividad_raw"] = df_raw
            except Exception:
                pass
    else:
        st.warning("⏳ El supervisor aún no ha cargado datos para este período. Vuelve más tarde o contacta a Oscar Pedraza.")
        st.stop()

farmers_data = st.session_state["farmers_data"]
dia_corte = st.session_state.get("dia_corte", 15)
dias_mes = st.session_state.get("dias_mes", 30)
progreso_pct = ((dia_corte - 1) / dias_mes) * 100

METRICS_DISPLAY = {
    "Churn":          ("ATT_Churn",     "decimal"),
    "MD Total":       ("ATT_MD_Total",  "decimal"),
    "MD Pro":         ("ATT_MD_Pro",    "decimal"),
    "Ads Bookings":   ("ATT_Book",      "decimal"),
    "Ads Revenue":    ("ATT_Rev_real",  "decimal"),
    "Net Rev Adj":    ("Net_Rev_Adj",   "pp"),
    "Pitch Integral": ("Pitch_Pct",     "decimal"),
    "No Contactados": ("pct_no_contactados", "pct_raw"),
}

# ── Build team dataframe ──────────────────────────────────────────────────────
rows = []
for farmer, data in farmers_data.items():
    sems = get_all_semaforos(data)
    comp = calcular_compensacion_completa(data)
    tier = tier_farmer(sems)
    row = {
        "email": farmer,
        "name": data.get("name", farmer),
        "tier": tier,
        "variable_pct": comp.get("variable_pct", 0),
        "qualifies": comp.get("qualifies", True),
    }
    for metric, (key, _) in METRICS_DISPLAY.items():
        row[f"val_{metric}"] = data.get(key)
        row[f"sem_{metric}"] = sems.get(metric, "gray")
    rows.append(row)

df = pd.DataFrame(rows).sort_values("name")

# ── Scoreboard ────────────────────────────────────────────────────────────────
st.markdown("## Scoreboard del equipo")
col1, col2, col3, col4, col5 = st.columns(5)

reds = (df["tier"] == "red").sum()
yellows = (df["tier"] == "yellow").sum()
greens = (df["tier"] == "green").sum()
no_qualifier = (~df["qualifies"]).sum()
avg_variable = df["variable_pct"].mean()

with col1: st.metric("🔴 En rojo", int(reds))
with col2: st.metric("🟡 En amarillo", int(yellows))
with col3: st.metric("🟢 En verde", int(greens))
with col4: st.metric("⛔ Sin qualifier", int(no_qualifier), help="Productividad < 90% → pierden variable")
with col5: st.metric("💰 Variable promedio", f"{avg_variable:.0f}%")

# ── Heatmap por métrica ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown("## Mapa de calor del equipo")

metrics_list = list(METRICS_DISPLAY.keys())
farmers_list = df["name"].tolist()

# Build color matrix
color_map = {"red": 0, "yellow": 1, "green": 2, "gray": -1}
z = []
text = []
for _, row in df.iterrows():
    z_row = []
    t_row = []
    for metric in metrics_list:
        sem = row[f"sem_{metric}"]
        val = row[f"val_{metric}"]
        z_row.append(color_map.get(sem, -1))
        if val is None:
            t_row.append("S/D")
        elif METRICS_DISPLAY[metric][1] == "decimal":
            t_row.append(f"{val*100:.1f}%")
        elif METRICS_DISPLAY[metric][1] == "pp":
            t_row.append(f"{val:+.1f}pp")
        else:
            t_row.append(f"{val:.1f}%")
    z.append(z_row)
    text.append(t_row)

colorscale = [
    [0.0, "#EF4444"],
    [0.33, "#EF4444"],
    [0.34, "#F59E0B"],
    [0.66, "#F59E0B"],
    [0.67, "#00B341"],
    [1.0, "#00B341"],
]

fig = go.Figure(data=go.Heatmap(
    z=z,
    x=metrics_list,
    y=farmers_list,
    text=text,
    texttemplate="%{text}",
    textfont={"size": 11, "color": "white", "family": "sans-serif"},
    colorscale=colorscale,
    showscale=False,
    hovertemplate="%{y} | %{x}: %{text}<extra></extra>",
    zmin=-1, zmax=2,
))

fig.update_layout(
    height=max(400, len(farmers_list) * 35),
    margin=dict(l=10, r=10, t=30, b=10),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(side="top"),
)

st.plotly_chart(fig, use_container_width=True)

# ── Ranking por métrica ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown("## Rankings por palanca")

metric_tabs = st.tabs(list(METRICS_DISPLAY.keys()))
for tab, (metric, (key, fmt)) in zip(metric_tabs, METRICS_DISPLAY.items()):
    with tab:
        sub = df[["name", f"val_{metric}", f"sem_{metric}"]].copy()
        sub.columns = ["Farmer", "Valor", "Semáforo"]
        sub = sub.dropna(subset=["Valor"]).sort_values("Valor", ascending=(metric == "No Contactados"))

        def fmt_val(v, f):
            if v is None: return "S/D"
            if f == "decimal": return f"{v*100:.1f}%"
            if f == "pp": return f"{v:+.1f} pp"
            return f"{v:.1f}%"

        sub["Display"] = sub.apply(lambda r: EMOJI.get(r["Semáforo"], "⚪") + " " + fmt_val(r["Valor"], fmt), axis=1)

        # Bar chart
        colors = [COLOR_HEX.get(s, "#9CA3AF") for s in sub["Semáforo"]]
        vals = sub["Valor"].tolist()
        if fmt == "decimal":
            vals_display = [v * 100 for v in vals]
            xlabel = "ATT (%)"
            xline = 90
        elif fmt == "pp":
            vals_display = vals
            xlabel = "pp vs ritmo"
            xline = 0
        else:
            vals_display = vals
            xlabel = "% No Contactados"
            xline = 30

        fig2 = go.Figure(go.Bar(
            y=sub["Farmer"].tolist(),
            x=vals_display,
            orientation="h",
            marker_color=colors,
            text=sub["Display"].tolist(),
            textposition="outside",
        ))
        fig2.add_vline(x=xline, line_dash="dash", line_color="#E8281F", opacity=0.5)
        fig2.update_layout(
            height=max(300, len(sub) * 30),
            margin=dict(l=10, r=10, t=10, b=10),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis_title=xlabel,
            showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)

# ── Farmers más críticos ──────────────────────────────────────────────────────
st.markdown("---")
st.markdown("## 🚨 Farmers que requieren acción inmediata")
st.caption("Criterio: ≥ 3 métricas en rojo o productividad < 90%")

critical = []
for _, row in df.iterrows():
    reds_count = sum(1 for m in metrics_list if row[f"sem_{m}"] == "red")
    if reds_count >= 3 or not row["qualifies"]:
        critical.append({
            "Farmer": row["name"],
            "KPIs en 🔴": reds_count,
            "Variable %": f"{row['variable_pct']:.0f}%",
            "Qualifier": "⛔ PIERDE VARIABLE" if not row["qualifies"] else "✅",
        })

if critical:
    st.dataframe(pd.DataFrame(critical).sort_values("KPIs en 🔴", ascending=False),
                 use_container_width=True, hide_index=True)
else:
    st.success("Ningún farmer con ≥ 3 métricas en rojo esta corrida.")

# ── Diagnóstico comercial gerencial ──────────────────────────────────────────
st.markdown("---")
st.markdown("## 🧠 Diagnóstico gerencial")

# Which metric has most reds?
metric_reds = {m: int((df[f"sem_{m}"] == "red").sum()) for m in metrics_list}
worst_metric = max(metric_reds, key=metric_reds.get)
worst_count = metric_reds[worst_metric]

total_f = len(df)
st.markdown(f"""
**Palanca más crítica del equipo:** `{worst_metric}` — **{worst_count}/{total_f} farmers en rojo**

**Progreso del mes:** {progreso_pct:.1f}% (día de corte {dia_corte}/30)

**Señales a escalar a liderazgo:**
""")

signals = []
if metric_reds.get("No Contactados", 0) >= total_f * 0.4:
    signals.append("⚠️ Más del 40% del equipo tiene contactabilidad crítica — posible problema estructural de gestión de tiempo o calidad de la base de aliados.")
if metric_reds.get("Churn", 0) >= total_f * 0.5:
    signals.append("⚠️ Churn crítico en más de la mitad del equipo — revisar si es problema de mercado (aliados cerrando) o de gestión (falta de seguimiento de retención).")
if metric_reds.get("Ads Revenue", 0) >= total_f * 0.5:
    signals.append("⚠️ ADS Revenue bajo en la mayoría — evaluar si el producto ADS está competitivo o si hay brecha de skill en el pitch de ADS.")
if no_qualifier >= 3:
    signals.append(f"🚨 {no_qualifier} farmers sin qualifier de productividad — en riesgo de perder variable completo. Requiere intervención urgente.")

if signals:
    for s in signals:
        st.markdown(s)
else:
    st.markdown("✅ No hay señales de alerta a nivel equipo esta semana.")
