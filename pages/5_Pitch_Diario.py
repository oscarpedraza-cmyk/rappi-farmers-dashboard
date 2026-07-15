"""
8_Pitch_Diario.py â€” Actividad diaria de pitches y conversiÃ³n por palanca.

Fuente: pestaÃ±a ConversiÃ³n / DETALLE del Sheet Maestro.
Columnas clave:
  DATE      â†’ fecha del seguimiento / pitch
  FARMER    â†’ email del farmer
  MARKDOWN  â†’ tipificÃ³ pitch MD (SI/NO)   | MD  â†’ cierre real (1/0)
  ADS       â†’ tipificÃ³ pitch ADS (SI/NO)  | BN  â†’ cierre real (1/0)
  CHURN     â†’ tipificÃ³ pitch CHURN (SI/NO)| ORD â†’ cierre real (1/0)
"""
from __future__ import annotations
import streamlit as st
import io
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.loader import FARMER_NAMES, FARMERS_EMAILS, EXCLUDED_EMAILS
from core.auth import require_auth, render_topbar
from core.style import inject_global_css

st.set_page_config(page_title="Pitch Diario â€” Rappi Farmers", page_icon="🌍", layout="wide", initial_sidebar_state="expanded")
st.markdown(inject_global_css(), unsafe_allow_html=True)
email_auth, is_supervisor = require_auth()
render_topbar()

ACTIVE_FARMERS = set(FARMERS_EMAILS) - EXCLUDED_EMAILS

# â”€â”€ Palanca config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
PALANCAS = [
    {"name": "MD",    "tip_col": "MARKDOWN", "real_col": "MD",  "color": "#4A6CF7", "fill": "rgba(74,108,247,0.09)",  "icon": "ðŸ’°"},
    {"name": "ADS",   "tip_col": "ADS",      "real_col": "BN",  "color": "#9333EA", "fill": "rgba(147,51,234,0.09)", "icon": "ðŸ“¢"},
    {"name": "Churn", "tip_col": "CHURN",    "real_col": "ORD", "color": "#F59E0B", "fill": "rgba(245,158,11,0.09)", "icon": "ðŸ”„"},
]

# â”€â”€ Auto-load â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if "farmers_data" not in st.session_state or "_conversion_raw" not in st.session_state:
    from core.db import load_latest_state
    latest = load_latest_state()
    if latest:
        st.session_state.setdefault("farmers_data", latest["farmers_data"])
        st.session_state.setdefault("dia_corte",    latest["dia_corte"])
        st.session_state.setdefault("dias_mes",     latest["dias_mes"])
        if latest.get("conversion_raw"):
            st.session_state["_conversion_raw"] = latest["conversion_raw"]
    else:
        st.warning("â³ El supervisor aÃºn no ha cargado datos. Vuelve mÃ¡s tarde.")
        st.stop()

# â”€â”€ Page header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
st.markdown("""
<div class="rb-page-header">
    <h1>ðŸ“… Pitch Diario</h1>
    <p>Pitches generados y conversiÃ³n real por palanca, dÃ­a a dÃ­a.</p>
</div>
""", unsafe_allow_html=True)

# â”€â”€ Load DETALLE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
raw = st.session_state.get("_conversion_raw")
if not raw:
    st.info("""
    ðŸ“‚ **Sin datos de DETALLE disponibles.**
    AÃ±ade una pestaÃ±a **`ConversiÃ³n`** en el Sheet Maestro con el contenido del DETALLE
    (columnas: FARMER, DATE, MARKDOWN, MD, ADS, BN, CHURN, ORDâ€¦) y vuelve a subir el archivo.
    """)
    st.stop()

try:
    df_raw = pd.read_json(io.StringIO(raw))
except Exception as e:
    st.error(f"Error leyendo datos: {e}")
    st.stop()

if "FARMER" not in df_raw.columns or "DATE" not in df_raw.columns:
    st.error("El DETALLE no tiene las columnas FARMER o DATE. Verifica el archivo.")
    st.stop()

# â”€â”€ Normalize â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
df = df_raw.copy()
df["FARMER"] = df["FARMER"].astype(str).str.strip().str.lower()
df = df[df["FARMER"].isin(ACTIVE_FARMERS)].copy()

# Parse date
df["_fecha"] = pd.to_datetime(df["DATE"], errors="coerce", dayfirst=True)
df = df.dropna(subset=["_fecha"]).copy()
df["_dia"] = df["_fecha"].dt.date

if df.empty:
    st.warning("No hay filas con fechas vÃ¡lidas en el DETALLE.")
    st.stop()

# â”€â”€ DeduplicaciÃ³n de calidad â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Drop exact duplicate rows (misma fila repetida en el Sheet)
_rows_antes = len(df)
df = df.drop_duplicates()
_rows_despues = len(df)
_duplicados_exactos = _rows_antes - _rows_despues

# Check for suspicious daily pitch counts per farmer:
# If a farmer has more pitches/day than their typical follow capacity, flag it
_pitch_cols = [p["tip_col"] for p in PALANCAS if p["tip_col"] in df.columns]

if _duplicados_exactos > 0:
    st.caption(
        f"â„¹ï¸ Se removieron **{_duplicados_exactos} filas duplicadas exactas** del DETALLE "
        f"(misma fila repetida). Los conteos a continuaciÃ³n ya usan datos limpios."
    )

# Normalize boolean / numeric cols
def _is_si(series):
    return series.astype(str).str.upper().str.strip() == "SI"

def _is_one(series):
    return pd.to_numeric(series, errors="coerce") == 1

for p in PALANCAS:
    df[f"_tip_{p['name']}"]  = _is_si(df[p["tip_col"]]) if p["tip_col"] in df.columns else False
    df[f"_real_{p['name']}"] = _is_one(df[p["real_col"]]) if p["real_col"] in df.columns else False

# â”€â”€ Farmer filter â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
all_names  = {FARMER_NAMES.get(e, e): e for e in sorted(ACTIVE_FARMERS) if e in df["FARMER"].values}

if is_supervisor:
    col_f, col_ct = st.columns([3, 3])
    with col_f:
        sel_farmer = st.selectbox(
            "Farmer", ["Todo el equipo"] + list(all_names.keys()),
            key="pd_farmer_sel"
        )
    with col_ct:
        sel_contacto = st.radio(
            "Contacto", ["Todos", "Contacto=SÃ­", "Contacto=No"],
            horizontal=True, key="pd_contacto_sel"
        )
    selected_emails = set(all_names.values()) if sel_farmer == "Todo el equipo" else {all_names[sel_farmer]}
else:
    email_me = email_auth.strip().lower()
    selected_emails = {email_me}
    sel_farmer = FARMER_NAMES.get(email_me, email_me)
    sel_contacto = st.radio(
        "Contacto", ["Todos", "Contacto=SÃ­", "Contacto=No"],
        horizontal=True, key="pd_contacto_sel"
    )
    st.markdown(f"""
    <div style="background:rgba(74,108,247,0.08);border-left:4px solid #4A6CF7;
                border-radius:8px;padding:0.6rem 1rem;margin-bottom:0.8rem;
                font-size:0.88rem;color:#1E3A8A">
        ðŸ‘¤ <b>Mostrando tu actividad â€” {sel_farmer}</b>
    </div>""", unsafe_allow_html=True)

df_sel = df[df["FARMER"].isin(selected_emails)].copy()

# Apply Contacto filter
_any_pitch_mask = (
    df_sel["_tip_MD"] | df_sel["_tip_ADS"] | df_sel["_tip_Churn"]
)
if sel_contacto == "Contacto=SÃ­":
    df_sel = df_sel[_any_pitch_mask].copy()
elif sel_contacto == "Contacto=No":
    df_sel = df_sel[~_any_pitch_mask].copy()

if df_sel.empty:
    st.warning("Sin datos para el filtro seleccionado.")
    st.stop()

fecha_min = df_sel["_dia"].min()
fecha_max = df_sel["_dia"].max()
n_dias    = (pd.Timestamp(fecha_max) - pd.Timestamp(fecha_min)).days + 1

# â”€â”€ KPI cards â€” totales del perÃ­odo â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
st.markdown(f"""
<div style="font-size:0.75rem;font-weight:600;color:#64748B;text-transform:uppercase;
            letter-spacing:0.7px;margin-bottom:0.6rem">
    PerÃ­odo: {fecha_min.strftime('%d %b')} â†’ {fecha_max.strftime('%d %b %Y')} Â· {n_dias} dÃ­as con actividad
</div>""", unsafe_allow_html=True)

kpi_cols = st.columns(3)
for col, p in zip(kpi_cols, PALANCAS):
    tip_total  = int(df_sel[f"_tip_{p['name']}"].sum())
    real_total = int(df_sel[f"_real_{p['name']}"].sum())
    conv_pct   = round(real_total / tip_total * 100, 1) if tip_total > 0 else 0
    avg_dia    = round(tip_total / n_dias, 1)
    c = "#00B341" if conv_pct >= 30 else "#F59E0B" if conv_pct >= 15 else "#EF4444"
    with col:
        st.markdown(f"""
        <div style="background:#FFFFFF;border-radius:12px;padding:1.1rem 1.3rem;
                    border-top:4px solid {p['color']};border:1px solid #E5E7EB;
                    box-shadow:0 2px 8px rgba(0,0,0,0.06)">
            <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;
                        letter-spacing:0.5px;font-weight:600;margin-bottom:0.3rem">
                {p['icon']} {p['name']}
            </div>
            <div style="display:flex;align-items:flex-end;gap:0.8rem">
                <div>
                    <div style="font-size:1.8rem;font-weight:800;color:{p['color']}">{tip_total}</div>
                    <div style="font-size:0.72rem;color:#9CA3AF">pitches totales Â· {avg_dia}/dÃ­a</div>
                </div>
                <div style="margin-bottom:0.25rem">
                    <div style="font-size:1.3rem;font-weight:700;color:{c}">{conv_pct}%</div>
                    <div style="font-size:0.72rem;color:#9CA3AF">{real_total} cierres reales</div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)

# â”€â”€ Build daily aggregation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
agg_dict = {}
for p in PALANCAS:
    agg_dict[f"tip_{p['name']}"]  = (f"_tip_{p['name']}",  "sum")
    agg_dict[f"real_{p['name']}"] = (f"_real_{p['name']}", "sum")

df_daily = (df_sel.groupby("_dia")
            .agg(**agg_dict)
            .reset_index()
            .sort_values("_dia"))
df_daily["_dia_ts"] = pd.to_datetime(df_daily["_dia"])

# â”€â”€ Calidad de datos: alertar si pitches diarios parecen anÃ³malos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Get typical follow capacity from farmers_data for cross-check
_farmers_data = st.session_state.get("farmers_data", {})
_anomalous_days = []
for p in PALANCAS:
    _col = f"tip_{p['name']}"
    _max_day = df_daily[_col].max() if not df_daily.empty else 0
    # Flag if any single day exceeds 30 pitches of a given type for a single farmer
    if sel_farmer != "Todo el equipo" and _max_day > 30:
        _bad_days = df_daily[df_daily[_col] > 30]["_dia"].tolist()
        for _d in _bad_days:
            _anomalous_days.append(f"{p['name']} â€” {_max_day:.0f} pitches el {_d}")

if _anomalous_days:
    with st.expander("âš ï¸ Posibles anomalÃ­as en el DETALLE â€” revisar", expanded=False):
        st.warning(
            "Se detectaron dÃ­as con un nÃºmero muy alto de pitches para un solo farmer. "
            "Esto puede indicar **filas duplicadas** en el Sheet Maestro (mismo aliado "
            "cargado varias veces el mismo dÃ­a) o **error de tipificaciÃ³n**. "
            "Verifica en el Sheet Maestro que no haya filas repetidas por fecha y aliado."
        )
        for msg in _anomalous_days:
            st.markdown(f"- {msg}")

# Conversion rates
for p in PALANCAS:
    tip  = df_daily[f"tip_{p['name']}"]
    real = df_daily[f"real_{p['name']}"]
    df_daily[f"conv_{p['name']}"] = (real / tip.replace(0, float("nan")) * 100).round(1)

# â”€â”€ Chart 1: Pitches per day â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
st.markdown("""
<div style="font-size:1rem;font-weight:800;color:#0F172A;letter-spacing:-0.2px;
            margin-bottom:0.5rem">
    Pitches generados por dÃ­a
</div>""", unsafe_allow_html=True)

fig_pitches = go.Figure()
for p in PALANCAS:
    col_name = f"tip_{p['name']}"
    fig_pitches.add_trace(go.Scatter(
        x=df_daily["_dia_ts"],
        y=df_daily[col_name],
        name=f"{p['icon']} {p['name']}",
        mode="lines+markers",
        line=dict(color=p["color"], width=2.5),
        marker=dict(size=6, color=p["color"]),
        fill="tozeroy",
        fillcolor=p["fill"],
        hovertemplate=f"<b>{p['name']}</b><br>%{{x|%d %b}}<br>%{{y}} pitches<extra></extra>",
    ))

fig_pitches.update_layout(
    height=320,
    margin=dict(l=10, r=10, t=10, b=10),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    hovermode="x unified",
    legend=dict(orientation="h", y=1.08, x=0, font=dict(size=12)),
    xaxis=dict(
        gridcolor="#F3F4F6", showgrid=True,
        tickformat="%d %b", tickangle=-30,
    ),
    yaxis=dict(gridcolor="#F3F4F6", showgrid=True, title="# Pitches"),
)
st.plotly_chart(fig_pitches, use_container_width=True)

# â”€â”€ Chart 2: Conversion rate per day â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
st.markdown("""
<div style="font-size:1rem;font-weight:800;color:#0F172A;letter-spacing:-0.2px;
            margin:0.5rem 0">
    ConversiÃ³n real diaria (%) por palanca
</div>""", unsafe_allow_html=True)

fig_conv = go.Figure()
for p in PALANCAS:
    col_name = f"conv_{p['name']}"
    fig_conv.add_trace(go.Scatter(
        x=df_daily["_dia_ts"],
        y=df_daily[col_name],
        name=f"{p['icon']} {p['name']}",
        mode="lines+markers",
        line=dict(color=p["color"], width=2.5, dash="solid"),
        marker=dict(size=6, color=p["color"],
                    symbol="circle",
                    line=dict(color="white", width=1.5)),
        hovertemplate=f"<b>{p['name']}</b><br>%{{x|%d %b}}<br>%{{y:.1f}}% conversiÃ³n<extra></extra>",
    ))

# Reference line at 30%
fig_conv.add_hline(
    y=30, line_dash="dash", line_color="#00B341", line_width=1.5,
    annotation_text="Meta 30%", annotation_position="top right",
    annotation_font=dict(color="#00B341", size=11),
)

fig_conv.update_layout(
    height=300,
    margin=dict(l=10, r=10, t=10, b=10),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    hovermode="x unified",
    legend=dict(orientation="h", y=1.08, x=0, font=dict(size=12)),
    xaxis=dict(
        gridcolor="#F3F4F6", showgrid=True,
        tickformat="%d %b", tickangle=-30,
    ),
    yaxis=dict(
        gridcolor="#F3F4F6", showgrid=True,
        title="ConversiÃ³n %",
        ticksuffix="%",
        rangemode="tozero",
    ),
)
st.plotly_chart(fig_conv, use_container_width=True)

# â”€â”€ Chart 3: Heatmap de pitches (solo supervisor con todo el equipo) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if is_supervisor and len(selected_emails) > 1:
    st.markdown("""
    <div style="font-size:1rem;font-weight:800;color:#0F172A;letter-spacing:-0.2px;
                margin:0.5rem 0">
        Pitches por farmer y dÃ­a
    </div>""", unsafe_allow_html=True)

    tab_md, tab_ads, tab_churn = st.tabs(["ðŸ’° MD", "ðŸ“¢ ADS", "ðŸ”„ Churn"])
    for tab, p in zip([tab_md, tab_ads, tab_churn], PALANCAS):
        with tab:
            heat_df = (df_sel[df_sel[f"_tip_{p['name']}"]]
                       .assign(Farmer=lambda x: x["FARMER"].map(
                           lambda e: FARMER_NAMES.get(e, e.split("@")[0].title())))
                       .groupby(["Farmer", "_dia"])
                       .size()
                       .reset_index(name="Pitches"))
            if heat_df.empty:
                st.info(f"Sin pitches de {p['name']} para el perÃ­odo.")
                continue
            heat_pivot = heat_df.pivot(index="Farmer", columns="_dia", values="Pitches").fillna(0)

            # Format column labels as "dd mmm"
            col_labels = [
                pd.Timestamp(c).strftime("%d %b") if not isinstance(c, str) else c
                for c in heat_pivot.columns
            ]

            # Build text matrix: show number if > 0, blank if 0
            text_matrix = heat_pivot.values.astype(int).astype(str)
            text_matrix[heat_pivot.values == 0] = ""

            cell_h = max(38, min(55, 420 // max(len(heat_pivot), 1)))
            fig_heat = go.Figure(go.Heatmap(
                z=heat_pivot.values,
                x=col_labels,
                y=list(heat_pivot.index),
                text=text_matrix,
                texttemplate="%{text}",
                textfont=dict(
                    size=max(9, min(13, 120 // max(len(col_labels), 1))),
                    color="white",
                ),
                colorscale=[
                    [0,    "#F1F5F9"],
                    [0.01, "#EEF2FF"],
                    [0.3,  p["fill"]],
                    [1,    p["color"]],
                ],
                showscale=False,
                hovertemplate="<b>%{y}</b><br>%{x}<br>%{z} pitches<extra></extra>",
                xgap=2,
                ygap=2,
            ))
            fig_heat.update_layout(
                height=max(180, len(heat_pivot) * cell_h + 80),
                margin=dict(l=10, r=10, t=10, b=60),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(tickangle=-30, side="bottom"),
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_heat, use_container_width=True)

# â”€â”€ Tabla detalle diario â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
st.markdown("""
<div style="font-size:1rem;font-weight:800;color:#0F172A;letter-spacing:-0.2px;
            margin:0.5rem 0 0.3rem">
    Detalle diario
</div>""", unsafe_allow_html=True)

# Build display table
display_rows = []
for row in df_daily.sort_values("_dia", ascending=False).to_dict("records"):
    display_rows.append({
        "Fecha":            row["_dia"].strftime("%d %b %Y") if hasattr(row["_dia"], "strftime") else str(row["_dia"]),
        "MD pitches":       int(row["tip_MD"]),
        "MD real":          int(row["real_MD"]),
        "MD conv%":         f"{row['conv_MD']:.1f}%" if pd.notna(row["conv_MD"]) else "â€”",
        "ADS pitches":      int(row["tip_ADS"]),
        "ADS real":         int(row["real_ADS"]),
        "ADS conv%":        f"{row['conv_ADS']:.1f}%" if pd.notna(row["conv_ADS"]) else "â€”",
        "Churn pitches":    int(row["tip_Churn"]),
        "Churn real":       int(row["real_Churn"]),
        "Churn conv%":      f"{row['conv_Churn']:.1f}%" if pd.notna(row["conv_Churn"]) else "â€”",
        "Total pitches":    int(row["tip_MD"] + row["tip_ADS"] + row["tip_Churn"]),
    })

df_display = pd.DataFrame(display_rows)

def _color_conv(val):
    try:
        v = float(str(val).replace("%", "").strip())
        if v >= 30: return "color:#00B341;font-weight:700"
        if v >= 15: return "color:#F59E0B;font-weight:700"
        return "color:#EF4444;font-weight:700"
    except Exception:
        return ""

conv_cols = ["MD conv%", "ADS conv%", "Churn conv%"]
st.dataframe(
    df_display.style.map(_color_conv, subset=conv_cols),
    use_container_width=True,
    hide_index=True,
    height=min(450, (len(df_display) + 1) * 36),
)

# â”€â”€ Footer note â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
st.markdown("""
<div style="font-size:0.73rem;color:#9CA3AF;margin-top:0.5rem">
    Pitches = seguimientos tipificados con palanca activa (MARKDOWN=SI / ADS=SI / CHURN=SI) Â·
    ConversiÃ³n = cierres efectivos confirmados por sistema (MD=1 / BN=1 / ORD=1) Â·
    Meta de conversiÃ³n referencial: 30%
</div>
""", unsafe_allow_html=True)

