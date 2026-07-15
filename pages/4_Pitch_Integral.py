from __future__ import annotations
import streamlit as st
import io
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.loader import refresh_net_rev_adj
from core.auth import require_auth, render_topbar
from core.metrics import COLOR_HEX, EMOJI
from core.style import inject_global_css

st.set_page_config(
    page_title="Pitch Integral — Rappi Farmers",
    page_icon="🌍",
    layout="wide", initial_sidebar_state="expanded",
)
st.markdown(inject_global_css(), unsafe_allow_html=True)
email, is_supervisor = require_auth()
render_topbar()


# ── Semáforo helpers ──────────────────────────────────────────────────────────
def pi_color(pct):
    if pct is None: return "#9CA3AF"
    if pct >= 65:   return "#00B341"
    if pct >= 50:   return "#F59E0B"
    return "#EF4444"

def pi_status(pct):
    if pct is None: return "⚪ Sin dato"
    if pct >= 65:   return "🟢 En meta"
    if pct >= 50:   return "🟡 En seguimiento"
    return "🔴 Crítico"

# ── Data check ────────────────────────────────────────────────────────────────
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
dia_corte    = st.session_state.get("dia_corte", 13)
dias_mes     = st.session_state.get("dias_mes", 31)
progreso_pct = ((dia_corte - 1) / dias_mes) * 100
try:
    refresh_net_rev_adj(farmers_data, dias_mes)
except Exception:
    pass

# ── Build PI table ────────────────────────────────────────────────────────────
rows = []
for em, data in farmers_data.items():
    pitch = data.get("Pitch_Pct")
    pi_rows = data.get("_pi_rows", [])   # list of weekly float values

    rows.append({
        "email":      em,
        "Farmer":     data.get("name", em),
        "Pitch %":    round(pitch * 100, 1) if pitch is not None else None,
        "_pitch_dec": pitch,
        "_pi_rows":   pi_rows,
        "Status":     pi_status(pitch * 100 if pitch is not None else None),
        "Semanas con dato": len(pi_rows),
    })

df = pd.DataFrame(rows)
has_data = df["Pitch %"].notna().any()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="rb-page-header">
    <h1>🎤 Pitch Integral</h1>
    <p>% visitas con pitch completo (todas palancas). Meta: ≥ 65% | Seguimiento: 50–65% | Crítico: &lt; 50%</p>
</div>
""", unsafe_allow_html=True)

if not has_data:
    st.error("""
    **Sin datos de Pitch Integral en este archivo.**

    Posibles causas:
    - La hoja **PI** no existe en el Excel o está vacía
    - El nombre de la hoja difiere (verificar mayúsculas: debe ser exactamente `PI`)
    - La columna de emails no contiene direcciones `@rappi.com` reconocidas

    **Diagnóstico:** abre el expander abajo para ver qué encontró el loader.
    """)

    with st.expander("🔍 Diagnóstico PI (expandir)", expanded=True):
        raw = st.session_state.get("_productividad_raw")
        if raw is not None:
            st.markdown(f"- Hoja Productividad cargada: ✅ ({len(raw)} filas)")
        else:
            st.markdown("- Hoja Productividad: ❌ no cargada")

        st.markdown("**Farmers y sus valores Pitch_Pct:**")
        debug_rows = [(data.get("name", em), data.get("Pitch_Pct")) for em, data in farmers_data.items()]
        st.dataframe(pd.DataFrame(debug_rows, columns=["Farmer", "Pitch_Pct"]), hide_index=True)
    st.stop()

# ── KPI summary ───────────────────────────────────────────────────────────────
df_valid = df.dropna(subset=["Pitch %"])
avg_pi   = df_valid["Pitch %"].mean()
en_meta  = (df_valid["Pitch %"] >= 65).sum()
seguim   = ((df_valid["Pitch %"] >= 50) & (df_valid["Pitch %"] < 65)).sum()
criticos = (df_valid["Pitch %"] < 50).sum()
sin_dato = df["Pitch %"].isna().sum()

col1, col2, col3, col4, col5 = st.columns(5)
with col1: st.metric("📊 Promedio equipo", f"{avg_pi:.1f}%",
                      help="Promedio de % Palancas del período")
with col2: st.metric("🟢 En meta (≥65%)", int(en_meta))
with col3: st.metric("🟡 Seguimiento (50-65%)", int(seguim))
with col4: st.metric("🔴 Críticos (<50%)", int(criticos))
with col5: st.metric("⚪ Sin dato", int(sin_dato))

st.markdown("---")

# ── Bar chart — ranking por Pitch % ──────────────────────────────────────────
st.markdown("## Ranking de Pitch Integral")

df_sorted = df_valid.sort_values("Pitch %", ascending=True)
colors = [pi_color(v) for v in df_sorted["Pitch %"]]

fig = go.Figure(go.Bar(
    y=df_sorted["Farmer"],
    x=df_sorted["Pitch %"],
    orientation="h",
    marker_color=colors,
    text=df_sorted["Pitch %"].apply(lambda v: f"{v:.1f}%"),
    textposition="outside",
    hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
))

fig.add_vline(x=65, line_dash="dash", line_color="#00B341", opacity=0.7,
              annotation_text="Meta 65%", annotation_position="top")
fig.add_vline(x=50, line_dash="dot",  line_color="#F59E0B", opacity=0.6,
              annotation_text="Mínimo 50%")

fig.update_layout(
    height=max(300, len(df_sorted) * 36),
    margin=dict(l=10, r=60, t=20, b=10),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(range=[0, min(105, df_sorted["Pitch %"].max() + 12)],
               title="% Pitch Integral"),
    showlegend=False,
)
st.plotly_chart(fig, use_container_width=True)

# ── Semaphore table ───────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("## Detalle por farmer")

def _sparkline_text(pi_rows):
    """Convert last 8 weekly values to emoji sparkline string."""
    if not pi_rows:
        return "—"
    return "".join(
        "🟢" if v is not None and v * 100 >= 65 else
        "🟡" if v is not None and v * 100 >= 50 else
        "🔴" if v is not None else "⚪"
        for v in pi_rows[-8:]
    )

df_tbl = (
    df.sort_values("Pitch %", ascending=False, na_position="last")
    .copy()
    .reset_index(drop=True)
)
df_tbl["Estado"]         = df_tbl["Pitch %"].apply(pi_status)
df_tbl["Últimas 8 sem."] = df_tbl["_pi_rows"].apply(_sparkline_text)
df_tbl["Pitch %"]        = df_tbl["Pitch %"].apply(lambda v: v if v is not None else float("nan"))

st.data_editor(
    df_tbl[["Farmer", "Pitch %", "Estado", "Semanas con dato", "Últimas 8 sem."]],
    use_container_width=True,
    hide_index=True,
    disabled=True,
    column_config={
        "Farmer":          st.column_config.TextColumn("Farmer", width="medium"),
        "Pitch %":         st.column_config.ProgressColumn("Pitch %", format="%.1f%%",
                               min_value=0, max_value=100),
        "Estado":          st.column_config.TextColumn("Estado", width="medium"),
        "Semanas con dato":st.column_config.NumberColumn("Semanas", format="%d", width="small"),
        "Últimas 8 sem.":  st.column_config.TextColumn("← últimas 8 semanas →", width="large"),
    },
)

# ── Weekly trend if data available ───────────────────────────────────────────
farmers_with_weekly = [(em, data) for em, data in farmers_data.items()
                       if data.get("_pi_rows") and len(data["_pi_rows"]) > 1]

if farmers_with_weekly:
    st.markdown("---")
    st.markdown("## Tendencia semanal del equipo")
    st.caption("Evolución de Pitch % semana a semana (las columnas del archivo PI representan semanas)")

    fig2 = go.Figure()
    for em, data in farmers_with_weekly:
        name    = data.get("name", em)
        pi_vals = [v * 100 for v in data["_pi_rows"]]
        n       = len(pi_vals)
        x_vals  = list(range(1, n + 1))
        pct_fin = pi_vals[-1] if pi_vals else 0
        color   = pi_color(pct_fin)

        fig2.add_trace(go.Scatter(
            x=x_vals, y=pi_vals,
            name=name,
            mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=6, color=color),
            hovertemplate=f"{name} — semana %{{x}}: %{{y:.1f}}<extra></extra>",
        ))

    fig2.add_hline(y=65, line_dash="dash", line_color="#00B341", opacity=0.5,
                   annotation_text="Meta 65%")
    fig2.add_hline(y=50, line_dash="dot",  line_color="#F59E0B", opacity=0.4,
                   annotation_text="Mín 50%")

    max_weeks = max(len(d.get("_pi_rows", [])) for _, d in farmers_with_weekly)
    fig2.update_layout(
        height=400,
        margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="Semana del mes", tickmode="linear", dtick=1,
                   range=[0.5, max_weeks + 0.5]),
        yaxis=dict(title="Pitch Integral %", range=[0, 105]),
        hovermode="x unified",
        legend=dict(orientation="h", y=-0.2),
    )
    st.plotly_chart(fig2, use_container_width=True)

# ── Farmers below meta ────────────────────────────────────────────────────────
st.markdown("---")
below = df_valid[df_valid["Pitch %"] < 65].sort_values("Pitch %")
if not below.empty:
    st.markdown("## 🚨 Farmers bajo la meta (< 65%)")
    for row in below.to_dict("records"):
        p = row["Pitch %"]
        gap = 65 - p
        color = pi_color(p)
        st.markdown(
            f"- **{row['Farmer']}**: "
            f"<span style='color:{color};font-weight:700'>{p:.1f}%</span> "
            f"— faltan **{gap:.1f} pp** para la meta",
            unsafe_allow_html=True
        )
    st.markdown("")
    st.info("💡 **Acción recomendada:** en la próxima 1:1 revisar grabaciones de visitas y reforzar estructura del pitch integral (MD + Ads + Churn en cada contacto).")
else:
    st.success("✅ Todo el equipo supera la meta de Pitch Integral (≥ 65%)")
