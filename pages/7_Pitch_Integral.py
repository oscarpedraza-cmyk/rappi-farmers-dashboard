import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.auth import require_auth
from core.metrics import COLOR_HEX, EMOJI
from core.style import inject_global_css

st.set_page_config(
    page_title="Pitch Integral — Rappi Farmers",
    page_icon="🚀",
    layout="wide",
)
st.markdown(inject_global_css(), unsafe_allow_html=True)
email, is_supervisor = require_auth()

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
    st.warning("El supervisor aún no ha cargado datos. Vuelve a la página principal.")
    st.stop()

farmers_data = st.session_state["farmers_data"]
dia_corte    = st.session_state.get("dia_corte", 13)
dias_mes     = st.session_state.get("dias_mes", 31)
progreso_pct = ((dia_corte - 1) / dias_mes) * 100

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

# Semana count for context
df_display = df.copy()
df_display["Pitch %"] = df_display["Pitch %"].apply(
    lambda v: f"{v:.1f}%" if v is not None else "Sin dato"
)

rows_html = ""
for _, row in df.sort_values("Pitch %", ascending=False, na_position="last").iterrows():
    p      = row["_pitch_dec"]
    pct    = p * 100 if p is not None else None
    color  = pi_color(pct)
    status = pi_status(pct)
    disp   = f"{pct:.1f}%" if pct is not None else "Sin dato"
    n_sem  = int(row["Semanas con dato"])

    # Mini weekly sparkline as colored dots
    pi_r = row["_pi_rows"]
    dots = ""
    if pi_r:
        for v in pi_r[-8:]:   # last 8 weeks
            dc = pi_color(v * 100 if v is not None else None)
            dots += f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{dc};margin:1px" title="{v*100:.0f}%" ></span>'

    rows_html += f"""
    <tr style="border-bottom:1px solid #F3F4F6">
        <td style="padding:10px 14px;font-weight:600;color:#1A1A1A">{row['Farmer']}</td>
        <td style="padding:10px 8px;text-align:center;font-size:1.1rem;font-weight:700;color:{color}">{disp}</td>
        <td style="padding:10px 8px;text-align:center">{status}</td>
        <td style="padding:10px 8px;text-align:center;font-size:0.8rem;color:#666">{n_sem} semana{'s' if n_sem != 1 else ''}</td>
        <td style="padding:10px 8px;text-align:center">{dots if dots else '<span style="color:#aaa">—</span>'}</td>
    </tr>"""

st.markdown(f"""
<table style="width:100%;border-collapse:collapse;font-size:0.88rem;background:#FFFFFF;
              border:1px solid #E5E7EB;border-radius:12px;overflow:hidden;
              box-shadow:0 2px 8px rgba(0,0,0,0.06)">
    <thead>
        <tr style="background:#F9FAFB;color:#6B7280;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.8px">
            <th style="padding:10px 14px;text-align:left">Farmer</th>
            <th style="padding:10px;text-align:center">Pitch %</th>
            <th style="padding:10px;text-align:center">Estado</th>
            <th style="padding:10px;text-align:center">Datos</th>
            <th style="padding:10px;text-align:center">Semanas (últimas 8) →</th>
        </tr>
    </thead>
    <tbody>{rows_html}</tbody>
</table>
""", unsafe_allow_html=True)

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
    for _, row in below.iterrows():
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
