from __future__ import annotations
import streamlit as st
import io
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.metrics import (get_all_semaforos, tier_farmer, EMOJI, COLOR_HEX,
                          calcular_compensacion_completa, score_farmer,
                          assign_quartiles, QUARTILE_COLOR, QUARTILE_LABEL,
                          generar_recomendaciones)
from core.loader import refresh_net_rev_adj
from core.auth import require_auth, render_topbar
from core.style import inject_global_css

st.set_page_config(page_title="Vista General — Rappi Farmers", page_icon="🚀", layout="wide", initial_sidebar_state="expanded")
st.markdown(inject_global_css(), unsafe_allow_html=True)
email, is_supervisor = require_auth()
render_topbar()

# ── Acceso restringido al supervisor ─────────────────────────────────────────
if not is_supervisor:
    st.markdown("""
    <div style="background:#FEF2F2;border:1px solid #FCA5A5;border-left:4px solid #EF4444;
                border-radius:12px;padding:1.5rem 1.8rem;margin-top:2rem;text-align:center">
        <div style="font-size:2rem;margin-bottom:0.5rem">🔒</div>
        <div style="font-size:1.1rem;font-weight:700;color:#991B1B;margin-bottom:0.3rem">
            Acceso restringido
        </div>
        <div style="color:#7F1D1D;font-size:0.88rem">
            Esta sección es exclusiva del supervisor.<br>
            Si crees que esto es un error, contacta a Oscar Pedraza.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


st.markdown("""
<div class="rb-page-header">
    <h1>📊 Vista General — Gerencia Comercial</h1>
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

# Recalculate Net_Rev_Adj with today's date (not the upload date)
try:
    refresh_net_rev_adj(farmers_data, dias_mes)
except Exception:
    pass

# Heatmap shows: ADS Revenue colored by Net_Rev_Adj pace (not raw ATT)
# Net Rev Adj colum shows same value but labeled differently
METRICS_DISPLAY = {
    "Churn":          ("ATT_Churn",          "decimal"),
    "MD Total":       ("ATT_MD_Total",        "decimal"),
    "MD Pro":         ("ATT_MD_Pro",          "decimal"),
    "Ads Bookings":   ("ATT_Book",            "decimal"),
    "Ads Revenue":    ("ATT_Rev_real",        "decimal"),
    "Net Rev Adj":    ("Net_Rev_Adj",         "pp"),
    "Pitch Integral": ("Pitch_Pct",           "decimal"),
    "No Contactados": ("pct_no_contactados",  "pct_raw"),
}

# ── Build team dataframe ──────────────────────────────────────────────────────
rows = []
for farmer, data in farmers_data.items():
    sems = get_all_semaforos(data)
    comp = calcular_compensacion_completa(data)
    tier = tier_farmer(sems)
    score = score_farmer(sems, comp)
    row = {
        "email":        farmer,
        "name":         data.get("name", farmer),
        "tier":         tier,
        "score":        score,
        "variable_pct": comp.get("variable_pct", 0),
        "qualifies":    comp.get("qualifies", True),
        "net_rev_adj":  data.get("Net_Rev_Adj"),
    }
    for metric, (key, _) in METRICS_DISPLAY.items():
        row[f"val_{metric}"] = data.get(key)
        row[f"sem_{metric}"] = sems.get(metric, "gray")
    rows.append(row)

df = pd.DataFrame(rows).sort_values("name")

# Quartile assignment
scores_dict = {r["email"]: r["score"] for r in rows}
quartiles = assign_quartiles(scores_dict)
df["quartile"] = df["email"].map(quartiles)

# ── Scoreboard ────────────────────────────────────────────────────────────────
st.markdown("## Scoreboard del equipo")
col1, col2, col3, col4, col5 = st.columns(5)

reds_count    = (df["tier"] == "red").sum()
yellows_count = (df["tier"] == "yellow").sum()
greens_count  = (df["tier"] == "green").sum()
no_qualifier  = (~df["qualifies"]).sum()
avg_variable  = df["variable_pct"].mean()

with col1: st.metric("🔴 En rojo",       int(reds_count))
with col2: st.metric("🟡 En amarillo",   int(yellows_count))
with col3: st.metric("🟢 En verde",      int(greens_count))
with col4: st.metric("⛔ Sin qualifier", int(no_qualifier),
                     help="Productividad < 90% → pierden variable")
with col5: st.metric("💰 Variable promedio", f"{avg_variable:.0f}%")

# ── Heatmap por métrica ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown("## Mapa de calor del equipo")
st.caption(
    "🟢 Ads Revenue = verde cuando va al ritmo o por encima del mes (Net Rev Adj ≥ 0). "
    "🟡/🔴 si el pace actual no llegaría al 100% a fin de mes."
)

metrics_list = list(METRICS_DISPLAY.keys())
farmers_list = df["name"].tolist()

color_map = {"red": 0, "yellow": 1, "green": 2, "gray": -1}
z = []
text = []
for row in df.to_dict("records"):
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

# Discrete colorscale for z in {-1=gray, 0=red, 1=yellow, 2=green}.
# With zmin=-1, zmax=2 (range=3) the normalised positions of the midpoints
# between adjacent z-values are: (-1,0)→0.167, (0,1)→0.500, (1,2)→0.833.
# The old scale had the yellow→green boundary at 0.66/0.67 but z=1 maps to
# exactly 0.667 → it fell in the green band. Fixed below with exact midpoints.
colorscale = [
    [0.000, "#9CA3AF"],  # z=-1 → gray  (no data)
    [0.166, "#9CA3AF"],
    [0.167, "#EF4444"],  # z=0  → red
    [0.499, "#EF4444"],
    [0.500, "#F59E0B"],  # z=1  → yellow  (≥ 0.500, safely covers 0.667)
    [0.832, "#F59E0B"],
    [0.833, "#00B341"],  # z=2  → green
    [1.000, "#00B341"],
]

fig = go.Figure(data=go.Heatmap(
    z=z, x=metrics_list, y=farmers_list,
    text=text, texttemplate="%{text}",
    textfont={"size": 11, "color": "white", "family": "sans-serif"},
    colorscale=colorscale, showscale=False,
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

def _fmt_metric(v, f: str) -> str:
    if v is None: return "S/D"
    if f == "decimal": return f"{v*100:.1f}%"
    if f == "pp":      return f"{v:+.1f} pp"
    return f"{v:.1f}%"


metric_tabs = st.tabs(list(METRICS_DISPLAY.keys()))
for tab, (metric, (key, fmt)) in zip(metric_tabs, METRICS_DISPLAY.items()):
    with tab:
        sub = df[["name", f"val_{metric}", f"sem_{metric}"]].copy()
        sub.columns = ["Farmer", "Valor", "Semáforo"]
        sub = sub.dropna(subset=["Valor"]).sort_values("Valor",
              ascending=(metric == "No Contactados"))

        sub["Display"] = sub.apply(
            lambda r: EMOJI.get(r["Semáforo"], "⚪") + " " + _fmt_metric(r["Valor"], fmt), axis=1)

        colors = [COLOR_HEX.get(s, "#9CA3AF") for s in sub["Semáforo"]]
        vals = sub["Valor"].tolist()
        if fmt == "decimal":
            vals_display = [v * 100 for v in vals]
            xlabel = "ATT (%)"
            xline  = 90
        elif fmt == "pp":
            vals_display = vals
            xlabel = "pp vs ritmo"
            xline  = 0
        else:
            vals_display = vals
            xlabel = "% No Contactados"
            xline  = 30

        fig2 = go.Figure(go.Bar(
            y=sub["Farmer"].tolist(), x=vals_display,
            orientation="h", marker_color=colors,
            text=sub["Display"].tolist(), textposition="outside",
        ))
        fig2.add_vline(x=xline, line_dash="dash", line_color="#E8281F", opacity=0.5)
        fig2.update_layout(
            height=max(300, len(sub) * 30),
            margin=dict(l=10, r=10, t=10, b=10),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis_title=xlabel, showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)

# ── 🧠 Diagnóstico + acción inmediata (sección unificada) ────────────────────
st.markdown("---")
st.markdown("## 🧠 Diagnóstico gerencial y acción inmediata")

metric_reds_count = {m: int((df[f"sem_{m}"] == "red").sum()) for m in metrics_list}
worst_metric = max(metric_reds_count, key=metric_reds_count.get)
worst_count  = metric_reds_count[worst_metric]
total_f      = len(df)

q4_names = df[df["quartile"] == "Q4"]["name"].tolist()
q4_rows  = df[df["quartile"] == "Q4"].sort_values("score")

# ── Contexto macro ────────────────────────────────────────────────────────────
st.markdown(
    f"**Progreso del mes:** {progreso_pct:.1f}% · día {dia_corte}/{dias_mes} &nbsp;|&nbsp; "
    f"**Palanca más crítica:** {worst_metric} ({worst_count}/{total_f} en 🔴) &nbsp;|&nbsp; "
    f"**Cuartiles:** 🏆 Q1 {(df['quartile']=='Q1').sum()} · "
    f"✅ Q2 {(df['quartile']=='Q2').sum()} · "
    f"⚠️ Q3 {(df['quartile']=='Q3').sum()} · "
    f"🚨 Q4 {(df['quartile']=='Q4').sum()}"
)

st.markdown("---")

# ── Señales a nivel equipo ────────────────────────────────────────────────────
signals = []
if metric_reds_count.get("No Contactados", 0) >= total_f * 0.4:
    signals.append("⚠️ Más del 40% del equipo con contactabilidad crítica — posible problema estructural de gestión de tiempo o calidad de base de aliados.")
if metric_reds_count.get("Churn", 0) >= total_f * 0.5:
    signals.append("⚠️ Churn crítico en más de la mitad del equipo — revisar si es problema de mercado o de seguimiento de retención.")
if metric_reds_count.get("Ads Revenue", 0) >= total_f * 0.5:
    signals.append("⚠️ ADS Revenue por debajo del pace en la mayoría — evaluar pipeline de inversión y calidad del pitch ADS.")
if no_qualifier >= 3:
    signals.append(f"🚨 {no_qualifier} farmers sin qualifier de productividad — en riesgo de perder variable completo. Intervención urgente.")

behind_pace = df[df["net_rev_adj"].notna() & (df["net_rev_adj"] < -5)]
if not behind_pace.empty:
    signals.append(f"📉 ADS Revenue crítico (>5pp bajo pace): {', '.join(behind_pace['name'].tolist())} — no llegarían al 100% a fin de mes.")

if signals:
    st.markdown("**Señales a nivel equipo:**")
    for s in signals:
        st.markdown(f"- {s}")
else:
    st.markdown("✅ No hay señales de alerta críticas a nivel equipo esta semana.")

# ── Farmers Q4: diagnóstico individual en texto ───────────────────────────────
st.markdown("---")
st.markdown("**🚨 Farmers en Q4 — acción inmediata esta semana:**")
st.caption("Peor cuartil del equipo por score compuesto KPIs + variable. Requieren seguimiento 1:1.")

if q4_rows.empty:
    st.markdown("✅ Ningún farmer en Q4 esta corrida.")
else:
    for row in q4_rows.to_dict("records"):
        farmer_email = row["email"]
        farmer_data  = farmers_data.get(farmer_email, {})
        sems_f       = get_all_semaforos(farmer_data)

        var_pct   = row["variable_pct"]
        qualifies = row["qualifies"]
        net_rev   = farmer_data.get("Net_Rev_Adj")
        net_rev_str = f"{net_rev:+.1f}pp" if net_rev is not None else "S/D"

        kpis_rojos     = [m for m in metrics_list if row.get(f"sem_{m}") == "red"]
        kpis_amarillos = [m for m in metrics_list if row.get(f"sem_{m}") == "yellow"]

        recs = generar_recomendaciones(farmer_data, sems_f)
        rec_txt = " · ".join(
            r.split("—")[0].strip().lstrip("🎯📞💰⭐📢🎤📵📉⚠️✅").strip()
            for r in recs[:3]
        )

        qualifier_txt = "⛔ SIN QUALIFIER (pierde variable)" if not qualifies else f"Variable {var_pct:.0f}%"
        rojos_txt  = ", ".join(kpis_rojos)  if kpis_rojos  else "ninguno"
        amarillos_txt = ", ".join(kpis_amarillos) if kpis_amarillos else "—"

        st.markdown(
            f"**{row['name']}** — Score {row['score']:.0f}/100 · {qualifier_txt} · "
            f"Net Rev {net_rev_str}  \n"
            f"🔴 {rojos_txt}  ·  🟡 {amarillos_txt}  \n"
            f"_Acciones: {rec_txt}_"
        )
        st.markdown("")   # blank line between farmers
