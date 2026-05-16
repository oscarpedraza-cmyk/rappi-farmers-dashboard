"""
8_Pitch_Diario.py — Actividad diaria de pitches y conversión por palanca.

Fuente: pestaña Conversión / DETALLE del Sheet Maestro.
Columnas clave:
  DATE      → fecha del seguimiento / pitch
  FARMER    → email del farmer
  MARKDOWN  → tipificó pitch MD (SI/NO)   | MD  → cierre real (1/0)
  ADS       → tipificó pitch ADS (SI/NO)  | BN  → cierre real (1/0)
  CHURN     → tipificó pitch CHURN (SI/NO)| ORD → cierre real (1/0)
"""
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

st.set_page_config(page_title="Pitch Diario — Rappi Farmers", page_icon="🚀", layout="wide")
st.markdown(inject_global_css(), unsafe_allow_html=True)
email_auth, is_supervisor = require_auth()
render_topbar()

ACTIVE_FARMERS = set(FARMERS_EMAILS) - EXCLUDED_EMAILS

# ── Palanca config ────────────────────────────────────────────────────────────
PALANCAS = [
    {"name": "MD",    "tip_col": "MARKDOWN", "real_col": "MD",  "color": "#4A6CF7", "fill": "rgba(74,108,247,0.09)",  "icon": "💰"},
    {"name": "ADS",   "tip_col": "ADS",      "real_col": "BN",  "color": "#9333EA", "fill": "rgba(147,51,234,0.09)", "icon": "📢"},
    {"name": "Churn", "tip_col": "CHURN",    "real_col": "ORD", "color": "#F59E0B", "fill": "rgba(245,158,11,0.09)", "icon": "🔄"},
]

# ── Auto-load ─────────────────────────────────────────────────────────────────
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
        st.warning("⏳ El supervisor aún no ha cargado datos. Vuelve más tarde.")
        st.stop()

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="rb-page-header">
    <h1>📅 Pitch Diario</h1>
    <p>Pitches generados y conversión real por palanca, día a día.</p>
</div>
""", unsafe_allow_html=True)

# ── Load DETALLE ──────────────────────────────────────────────────────────────
raw = st.session_state.get("_conversion_raw")
if not raw:
    st.info("""
    📂 **Sin datos de DETALLE disponibles.**
    Añade una pestaña **`Conversión`** en el Sheet Maestro con el contenido del DETALLE
    (columnas: FARMER, DATE, MARKDOWN, MD, ADS, BN, CHURN, ORD…) y vuelve a subir el archivo.
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

# ── Normalize ─────────────────────────────────────────────────────────────────
df = df_raw.copy()
df["FARMER"] = df["FARMER"].astype(str).str.strip().str.lower()
df = df[df["FARMER"].isin(ACTIVE_FARMERS)].copy()

# Parse date
df["_fecha"] = pd.to_datetime(df["DATE"], errors="coerce", dayfirst=True)
df = df.dropna(subset=["_fecha"]).copy()
df["_dia"] = df["_fecha"].dt.date

if df.empty:
    st.warning("No hay filas con fechas válidas en el DETALLE.")
    st.stop()

# Normalize boolean / numeric cols
def _is_si(series):
    return series.astype(str).str.upper().str.strip() == "SI"

def _is_one(series):
    return pd.to_numeric(series, errors="coerce") == 1

for p in PALANCAS:
    df[f"_tip_{p['name']}"]  = _is_si(df[p["tip_col"]]) if p["tip_col"] in df.columns else False
    df[f"_real_{p['name']}"] = _is_one(df[p["real_col"]]) if p["real_col"] in df.columns else False

# ── Farmer filter ─────────────────────────────────────────────────────────────
all_names  = {FARMER_NAMES.get(e, e): e for e in sorted(ACTIVE_FARMERS) if e in df["FARMER"].values}

if is_supervisor:
    col_f, col_p = st.columns([3, 6])
    with col_f:
        sel_farmer = st.selectbox(
            "Farmer", ["Todo el equipo"] + list(all_names.keys()),
            key="pd_farmer_sel"
        )
    selected_emails = set(all_names.values()) if sel_farmer == "Todo el equipo" else {all_names[sel_farmer]}
else:
    email_me = email_auth.strip().lower()
    selected_emails = {email_me}
    sel_farmer = FARMER_NAMES.get(email_me, email_me)
    st.markdown(f"""
    <div style="background:rgba(74,108,247,0.08);border-left:4px solid #4A6CF7;
                border-radius:8px;padding:0.6rem 1rem;margin-bottom:0.8rem;
                font-size:0.88rem;color:#1E3A8A">
        👤 <b>Mostrando tu actividad — {sel_farmer}</b>
    </div>""", unsafe_allow_html=True)

df_sel = df[df["FARMER"].isin(selected_emails)].copy()

if df_sel.empty:
    st.warning("Sin datos para el filtro seleccionado.")
    st.stop()

fecha_min = df_sel["_dia"].min()
fecha_max = df_sel["_dia"].max()
n_dias    = (pd.Timestamp(fecha_max) - pd.Timestamp(fecha_min)).days + 1

# ── KPI cards — totales del período ──────────────────────────────────────────
st.markdown(f"""
<div style="font-size:0.75rem;font-weight:600;color:#64748B;text-transform:uppercase;
            letter-spacing:0.7px;margin-bottom:0.6rem">
    Período: {fecha_min.strftime('%d %b')} → {fecha_max.strftime('%d %b %Y')} · {n_dias} días con actividad
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
                    <div style="font-size:0.72rem;color:#9CA3AF">pitches totales · {avg_dia}/día</div>
                </div>
                <div style="margin-bottom:0.25rem">
                    <div style="font-size:1.3rem;font-weight:700;color:{c}">{conv_pct}%</div>
                    <div style="font-size:0.72rem;color:#9CA3AF">{real_total} cierres reales</div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)

# ── Build daily aggregation ───────────────────────────────────────────────────
agg_dict = {}
for p in PALANCAS:
    agg_dict[f"tip_{p['name']}"]  = (f"_tip_{p['name']}",  "sum")
    agg_dict[f"real_{p['name']}"] = (f"_real_{p['name']}", "sum")

df_daily = (df_sel.groupby("_dia")
            .agg(**agg_dict)
            .reset_index()
            .sort_values("_dia"))
df_daily["_dia_ts"] = pd.to_datetime(df_daily["_dia"])

# Conversion rates
for p in PALANCAS:
    tip  = df_daily[f"tip_{p['name']}"]
    real = df_daily[f"real_{p['name']}"]
    df_daily[f"conv_{p['name']}"] = (real / tip.replace(0, float("nan")) * 100).round(1)

# ── Chart 1: Pitches per day ──────────────────────────────────────────────────
st.markdown("""
<div style="font-size:1rem;font-weight:800;color:#0F172A;letter-spacing:-0.2px;
            margin-bottom:0.5rem">
    Pitches generados por día
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

# ── Chart 2: Conversion rate per day ─────────────────────────────────────────
st.markdown("""
<div style="font-size:1rem;font-weight:800;color:#0F172A;letter-spacing:-0.2px;
            margin:0.5rem 0">
    Conversión real diaria (%) por palanca
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
        hovertemplate=f"<b>{p['name']}</b><br>%{{x|%d %b}}<br>%{{y:.1f}}% conversión<extra></extra>",
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
        title="Conversión %",
        ticksuffix="%",
        rangemode="tozero",
    ),
)
st.plotly_chart(fig_conv, use_container_width=True)

# ── Chart 3: Heatmap de pitches (solo supervisor con todo el equipo) ──────────
if is_supervisor and len(selected_emails) > 1:
    st.markdown("""
    <div style="font-size:1rem;font-weight:800;color:#0F172A;letter-spacing:-0.2px;
                margin:0.5rem 0">
        Pitches por farmer y día
    </div>""", unsafe_allow_html=True)

    tab_md, tab_ads, tab_churn = st.tabs(["💰 MD", "📢 ADS", "🔄 Churn"])
    for tab, p in zip([tab_md, tab_ads, tab_churn], PALANCAS):
        with tab:
            heat_df = (df_sel[df_sel[f"_tip_{p['name']}"]]
                       .assign(Farmer=lambda x: x["FARMER"].map(
                           lambda e: FARMER_NAMES.get(e, e.split("@")[0].title())))
                       .groupby(["Farmer", "_dia"])
                       .size()
                       .reset_index(name="Pitches"))
            if heat_df.empty:
                st.info(f"Sin pitches de {p['name']} para el período.")
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

# ── Tabla detalle diario ──────────────────────────────────────────────────────
st.markdown("""
<div style="font-size:1rem;font-weight:800;color:#0F172A;letter-spacing:-0.2px;
            margin:0.5rem 0 0.3rem">
    Detalle diario
</div>""", unsafe_allow_html=True)

# Build display table
display_rows = []
for _, row in df_daily.sort_values("_dia", ascending=False).iterrows():
    display_rows.append({
        "Fecha":            row["_dia"].strftime("%d %b %Y") if hasattr(row["_dia"], "strftime") else str(row["_dia"]),
        "MD pitches":       int(row["tip_MD"]),
        "MD real":          int(row["real_MD"]),
        "MD conv%":         f"{row['conv_MD']:.1f}%" if pd.notna(row["conv_MD"]) else "—",
        "ADS pitches":      int(row["tip_ADS"]),
        "ADS real":         int(row["real_ADS"]),
        "ADS conv%":        f"{row['conv_ADS']:.1f}%" if pd.notna(row["conv_ADS"]) else "—",
        "Churn pitches":    int(row["tip_Churn"]),
        "Churn real":       int(row["real_Churn"]),
        "Churn conv%":      f"{row['conv_Churn']:.1f}%" if pd.notna(row["conv_Churn"]) else "—",
        "Total pitches":    int(row["tip_MD"] + row["tip_ADS"] + row["tip_Churn"]),
    })

df_display = pd.DataFrame(display_rows)

def _color_conv(val):
    try:
        v = float(str(val).replace("%", "").strip())
        if v >= 30: return "color:#00B341;font-weight:700"
        if v >= 15: return "color:#F59E0B;font-weight:700"
        return "color:#EF4444;font-weight:700"
    except:
        return ""

conv_cols = ["MD conv%", "ADS conv%", "Churn conv%"]
st.dataframe(
    df_display.style.map(_color_conv, subset=conv_cols),
    use_container_width=True,
    hide_index=True,
    height=min(450, (len(df_display) + 1) * 36),
)

# ── Footer note ───────────────────────────────────────────────────────────────
st.markdown("""
<div style="font-size:0.73rem;color:#9CA3AF;margin-top:0.5rem">
    Pitches = seguimientos tipificados con palanca activa (MARKDOWN=SI / ADS=SI / CHURN=SI) ·
    Conversión = cierres efectivos confirmados por sistema (MD=1 / BN=1 / ORD=1) ·
    Meta de conversión referencial: 30%
</div>
""", unsafe_allow_html=True)
