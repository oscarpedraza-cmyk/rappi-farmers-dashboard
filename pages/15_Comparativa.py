from __future__ import annotations
import streamlit as st
import io
import calendar
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.loader import FARMER_NAMES, FARMERS_EMAILS, EXCLUDED_EMAILS, refresh_net_rev_adj
from core.auth import require_auth, render_topbar
from core.style import inject_global_css
from core.db import load_latest_state

st.set_page_config(
    page_title="Comparativa Semanal — Rappi Farmers",
    page_icon="🚀",
    layout="wide", initial_sidebar_state="expanded",
)
st.markdown(inject_global_css(), unsafe_allow_html=True)
email, is_supervisor = require_auth()
render_topbar()

ACTIVE_FARMERS = set(FARMERS_EMAILS) - EXCLUDED_EMAILS

# ── Bootstrap ─────────────────────────────────────────────────────────────────
if "farmers_data" not in st.session_state:
    latest = load_latest_state()
    if latest:
        st.session_state["farmers_data"] = latest.get("farmers_data")
        st.session_state["dia_corte"]    = latest.get("dia_corte", date.today().day - 1)
        st.session_state["dias_mes"]     = latest.get("dias_mes", 31)
        if latest.get("productividad_raw"):
            try:
                df_raw = pd.read_json(io.StringIO(latest["productividad_raw"]))
                df_raw.columns = [int(c) for c in df_raw.columns]
                st.session_state["_productividad_raw"] = df_raw
            except Exception:
                pass

df_prod = st.session_state.get("_productividad_raw")

st.markdown("""
<div class="rb-page-header">
    <h1>📊 Comparativa Semanal</h1>
    <p>Esta semana vs. la anterior: follows, contactos efectivos, palancas y marcas únicas por farmer.</p>
</div>
""", unsafe_allow_html=True)

if df_prod is None:
    st.error("""
    **Sin datos de Productividad.**
    Para ver la comparativa, cargá el Sheet Maestro con la pestaña **Productividad**.
    """)
    st.stop()

# ── Validar columnas ──────────────────────────────────────────────────────────
required = {4, 14, 15}
if not required.issubset(set(df_prod.columns)):
    st.error(f"Columnas faltantes en Productividad. Disponibles: {list(df_prod.columns[:20])}")
    st.stop()

date_col = 10 if 10 in df_prod.columns else (9 if 9 in df_prod.columns else None)
if date_col is None:
    st.error("No se encontró columna de fecha (col 9 o 10) en Productividad.")
    st.stop()

# Columnas de palanca
MD_COL    = 26 if 26 in df_prod.columns else None
ADS_COL   = 35 if 35 in df_prod.columns else None
CHURN_COL = 40 if 40 in df_prod.columns else None

# ── Parsear y limpiar ─────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def parse_prod(df_json: str, date_col: int) -> pd.DataFrame:
    df = pd.read_json(io.StringIO(df_json))
    df.columns = [int(c) if str(c).isdigit() else c for c in df.columns]

    # Capture raw numeric date BEFORE column renaming to avoid a second read_json call
    num = pd.to_numeric(df[date_col], errors="coerce") if date_col in df.columns else pd.Series(dtype=float)

    cols = {4: "contactado", 14: "farmer", 15: "code", date_col: "date"}
    if MD_COL    and MD_COL    in df.columns: cols[MD_COL]    = "md"
    if ADS_COL   and ADS_COL   in df.columns: cols[ADS_COL]   = "ads"
    if CHURN_COL and CHURN_COL in df.columns: cols[CHURN_COL] = "churn"

    df = df[list(cols.keys())].copy()
    df = df.rename(columns=cols)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Fallback epoch-ms
    bad = df["date"].notna() & (df["date"].dt.year < 2000)
    if bad.any() and len(num) == len(df):
        df.loc[bad, "date"] = pd.to_datetime(num[bad], unit="ms", errors="coerce")

    # Fallback Excel serial
    nat = df["date"].isna() & num.between(20_000, 60_000)
    if nat.any() and len(num) == len(df):
        df.loc[nat, "date"] = pd.to_datetime(
            num[nat].astype(int), unit="D", origin="1899-12-30", errors="coerce"
        )

    df["farmer"]     = df["farmer"].astype(str).str.strip().str.lower()
    df["contactado"] = df["contactado"].astype(str).str.strip().str.upper()
    df["code"]       = df["code"].astype(str)

    for pal in ["md", "ads", "churn"]:
        if pal in df.columns:
            df[pal] = df[pal].astype(str).str.strip().str.upper() == "SI"

    return df.dropna(subset=["date", "farmer"])


try:
    df = parse_prod(df_prod.to_json(), date_col)
except Exception as e:
    st.error(f"Error procesando Productividad: {e}")
    st.stop()

df = df[df["farmer"].isin(ACTIVE_FARMERS)].copy()
if df.empty:
    st.warning("No hay datos de farmers activos en Productividad.")
    st.stop()

# ── Sidebar: ventana de tiempo ────────────────────────────────────────────────
today = date.today()
with st.sidebar:
    st.markdown("### ⚙️ Ventana de tiempo")
    ventana = st.radio(
        "Comparar",
        ["Esta sem. vs. anterior", "Últimos 7 días vs. 7-14 días", "Este mes vs. mes anterior"],
        key="comp_ventana",
    )
    st.markdown("---")
    if is_supervisor:
        farmer_opts = ["Todos"] + [
            FARMER_NAMES.get(e, e.split("@")[0].title())
            for e in sorted(ACTIVE_FARMERS)
            if e in df["farmer"].values
        ]
        sel_farmer = st.selectbox("Farmer", farmer_opts, key="comp_farmer")
    else:
        sel_farmer = FARMER_NAMES.get(email.strip().lower(), email)

# ── Calcular ventanas ─────────────────────────────────────────────────────────
ts_today = pd.Timestamp(today)

if ventana == "Esta sem. vs. anterior":
    # Lunes de esta semana y la anterior
    lunes_this = pd.Timestamp(today - timedelta(days=today.weekday()))
    lunes_prev = lunes_this - timedelta(weeks=1)
    end_this   = lunes_this + timedelta(weeks=1)
    label_this = f"Sem. actual ({lunes_this.strftime('%d/%m')} →)"
    label_prev = f"Sem. anterior ({lunes_prev.strftime('%d/%m')} – {(lunes_this - timedelta(days=1)).strftime('%d/%m')})"
elif ventana == "Últimos 7 días vs. 7-14 días":
    lunes_this = ts_today - timedelta(days=7)
    lunes_prev = ts_today - timedelta(days=14)
    end_this   = ts_today + timedelta(days=1)
    label_this = f"Últimos 7 días ({lunes_this.strftime('%d/%m')} – {today.strftime('%d/%m')})"
    label_prev = f"7-14 días atrás ({lunes_prev.strftime('%d/%m')} – {lunes_this.strftime('%d/%m')})"
else:
    first_this = pd.Timestamp(today.replace(day=1))
    last_month_last = first_this - timedelta(days=1)
    first_prev = pd.Timestamp(last_month_last.replace(day=1))
    lunes_this = first_this
    lunes_prev = first_prev
    end_this   = ts_today + timedelta(days=1)
    label_this = f"Este mes ({first_this.strftime('%B')})"
    label_prev = f"Mes anterior ({first_prev.strftime('%B')})"

df_this = df[(df["date"] >= lunes_this) & (df["date"] < end_this)]
df_prev = df[(df["date"] >= lunes_prev) & (df["date"] < lunes_this)]

# Filtro por farmer (no supervisor ve solo el suyo)
if not is_supervisor:
    df_this = df_this[df_this["farmer"] == email.strip().lower()]
    df_prev = df_prev[df_prev["farmer"] == email.strip().lower()]
elif sel_farmer != "Todos":
    fe = next((e for e, n in FARMER_NAMES.items() if n == sel_farmer), None)
    if fe:
        df_this = df_this[df_this["farmer"] == fe]
        df_prev = df_prev[df_prev["farmer"] == fe]

# ── KPIs del equipo ───────────────────────────────────────────────────────────
total_this  = len(df_this)
total_prev  = len(df_prev)
cont_this   = int((df_this["contactado"] == "SI").sum()) if not df_this.empty else 0
cont_prev   = int((df_prev["contactado"] == "SI").sum()) if not df_prev.empty else 0
brands_this = df_this["code"].nunique()
brands_prev = df_prev["code"].nunique()
rate_this   = round(cont_this / max(1, total_this) * 100, 1)
rate_prev   = round(cont_prev / max(1, total_prev) * 100, 1)

st.markdown(f"**{label_this}** vs. **{label_prev}**")

c1, c2, c3, c4 = st.columns(4)
c1.metric("📋 Follows totales",      total_this, delta=total_this - total_prev,
          delta_color="normal")
c2.metric("✅ Contactos efectivos",   cont_this,  delta=cont_this - cont_prev,
          delta_color="normal")
c3.metric("📊 Tasa de contacto",     f"{rate_this}%",
          delta=f"{rate_this - rate_prev:+.1f}pp", delta_color="normal")
c4.metric("🏪 Marcas únicas",        brands_this, delta=brands_this - brands_prev,
          delta_color="normal")

st.markdown("---")

# ── Tabla por farmer ──────────────────────────────────────────────────────────
st.markdown("## Por farmer")


def farmer_stats(df_w: pd.DataFrame) -> pd.DataFrame:
    if df_w.empty:
        return pd.DataFrame(columns=["farmer", "follows", "contactados", "tasa", "marcas"])
    g = df_w.groupby("farmer")
    follows  = g.size().rename("follows")
    contactd = (df_w[df_w["contactado"] == "SI"].groupby("farmer").size()).rename("contactados")
    marcas   = g["code"].nunique().rename("marcas")
    out = pd.concat([follows, contactd, marcas], axis=1).fillna(0)
    out["tasa"] = (out["contactados"] / out["follows"] * 100).round(1)
    return out.reset_index()


stats_this = farmer_stats(df_this).set_index("farmer")
stats_prev = farmer_stats(df_prev).set_index("farmer")

rows = []
for fe in sorted(ACTIVE_FARMERS):
    if fe not in df["farmer"].values:
        continue
    name = FARMER_NAMES.get(fe, fe.split("@")[0].title())
    f_this = stats_this.loc[fe] if fe in stats_this.index else pd.Series({"follows": 0, "contactados": 0, "tasa": 0.0, "marcas": 0})
    f_prev = stats_prev.loc[fe] if fe in stats_prev.index else pd.Series({"follows": 0, "contactados": 0, "tasa": 0.0, "marcas": 0})

    delta_f = int(f_this["follows"]) - int(f_prev["follows"])
    delta_t = round(float(f_this["tasa"]) - float(f_prev["tasa"]), 1)

    rows.append({
        "Farmer":           name,
        "Follows (actual)": int(f_this["follows"]),
        "Follows (anterior)":int(f_prev["follows"]),
        "Δ Follows":        delta_f,
        "Tasa % (actual)":  float(f_this["tasa"]),
        "Tasa % (anterior)":float(f_prev["tasa"]),
        "Δ Tasa (pp)":      delta_t,
        "Marcas únicas":    int(f_this["marcas"]),
        "Tendencia":        "↑" if delta_f > 0 else ("↓" if delta_f < 0 else "→"),
    })

df_tbl = pd.DataFrame(rows)
if not df_tbl.empty:
    st.data_editor(
        df_tbl,
        use_container_width=True,
        hide_index=True,
        disabled=True,
        column_config={
            "Farmer":            st.column_config.TextColumn("Farmer", width="medium"),
            "Follows (actual)":  st.column_config.NumberColumn(label_this[:18], format="%d"),
            "Follows (anterior)":st.column_config.NumberColumn(label_prev[:18], format="%d"),
            "Δ Follows":         st.column_config.NumberColumn("Δ Follows", format="%+d"),
            "Tasa % (actual)":   st.column_config.ProgressColumn("Tasa actual", format="%.1f%%",
                                     min_value=0, max_value=100),
            "Tasa % (anterior)": st.column_config.ProgressColumn("Tasa anterior", format="%.1f%%",
                                     min_value=0, max_value=100),
            "Δ Tasa (pp)":       st.column_config.NumberColumn("Δ Tasa (pp)", format="%+.1f"),
            "Marcas únicas":     st.column_config.NumberColumn("Marcas únicas", format="%d"),
            "Tendencia":         st.column_config.TextColumn("Tend.", width="small"),
        },
    )

# ── Gráfico — Follows por farmer (agrupado) ───────────────────────────────────
st.markdown("---")
st.markdown("## Follows: esta semana vs. anterior")

if not df_tbl.empty:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name=label_prev,
        x=df_tbl["Farmer"],
        y=df_tbl["Follows (anterior)"],
        marker_color="#CBD5E1",
        opacity=0.8,
        text=df_tbl["Follows (anterior)"].apply(lambda v: str(v) if v > 0 else ""),
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name=label_this,
        x=df_tbl["Farmer"],
        y=df_tbl["Follows (actual)"],
        marker_color=[
            "#00B341" if d > 0 else "#EF4444" if d < 0 else "#F59E0B"
            for d in df_tbl["Δ Follows"]
        ],
        text=df_tbl["Follows (actual)"].apply(lambda v: str(v) if v > 0 else ""),
        textposition="outside",
    ))
    fig.update_layout(
        barmode="group",
        height=360,
        margin=dict(l=10, r=10, t=30, b=80),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.12),
        xaxis_tickangle=-35,
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Palancas: esta semana vs. anterior ───────────────────────────────────────
has_palancas = any(c in df.columns for c in ["md", "ads", "churn"])
if has_palancas:
    st.markdown("---")
    st.markdown("## Palancas pitcheadas")
    st.caption("Cantidad de follows donde se pitcheó cada palanca (columna = SI)")

    pal_rows = []
    for label, col in [("💰 MD", "md"), ("📢 ADS", "ads"), ("🔄 Churn", "churn")]:
        if col not in df.columns:
            continue
        n_this = int(df_this[col].sum()) if not df_this.empty and col in df_this.columns else 0
        n_prev = int(df_prev[col].sum()) if not df_prev.empty and col in df_prev.columns else 0
        pal_rows.append({
            "Palanca": label,
            label_this[:20]: n_this,
            label_prev[:20]: n_prev,
            "Δ": n_this - n_prev,
        })

    df_pal = pd.DataFrame(pal_rows)
    if not df_pal.empty:
        # Bar chart
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            name=label_prev,
            x=df_pal["Palanca"],
            y=df_pal[label_prev[:20]],
            marker_color="#CBD5E1",
            opacity=0.8,
            text=df_pal[label_prev[:20]],
            textposition="outside",
        ))
        fig2.add_trace(go.Bar(
            name=label_this,
            x=df_pal["Palanca"],
            y=df_pal[label_this[:20]],
            marker_color=["#4A6CF7", "#9333EA", "#F59E0B"],
            text=df_pal[label_this[:20]],
            textposition="outside",
        ))
        fig2.update_layout(
            barmode="group",
            height=300,
            margin=dict(l=10, r=10, t=30, b=30),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=1.12),
        )
        st.plotly_chart(fig2, use_container_width=True)

# ── Actividad por día ─────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("## Actividad por día")

if not df_this.empty:
    df_days = df_this.copy()
    df_days["dia"] = df_days["date"].dt.date
    by_day = df_days.groupby("dia").size().reset_index(name="follows")
    by_day["dia"] = pd.to_datetime(by_day["dia"])

    df_days_prev = df_prev.copy()
    if not df_days_prev.empty:
        df_days_prev["dia"] = df_days_prev["date"].dt.date
        by_day_prev = df_days_prev.groupby("dia").size().reset_index(name="follows")
        by_day_prev["dia"] = pd.to_datetime(by_day_prev["dia"])
    else:
        by_day_prev = pd.DataFrame(columns=["dia", "follows"])

    fig3 = go.Figure()
    if not by_day_prev.empty:
        fig3.add_trace(go.Scatter(
            x=by_day_prev["dia"],
            y=by_day_prev["follows"],
            name=label_prev,
            mode="lines+markers",
            line=dict(color="#CBD5E1", width=2, dash="dash"),
            marker=dict(size=6),
        ))
    fig3.add_trace(go.Scatter(
        x=by_day["dia"],
        y=by_day["follows"],
        name=label_this,
        mode="lines+markers",
        line=dict(color="#E8281F", width=2.5),
        marker=dict(size=8),
        fill="tozeroy",
        fillcolor="rgba(232,40,31,0.08)",
    ))
    fig3.update_layout(
        height=280,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.1),
        hovermode="x unified",
        xaxis=dict(tickformat="%a %d/%m"),
    )
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("Sin datos de follows para el período seleccionado.")
