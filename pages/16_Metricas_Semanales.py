"""
Métricas Semanales del Equipo
Upload semanal del export 'Metrics Weekly by Hierarchy Level'.
Alarmas automáticas por caída >10% (rojo) y 5-10% (amarillo) vs semana anterior.
"""
from __future__ import annotations
import sys
import io
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.auth import require_auth, render_topbar
from core.style import inject_global_css
from core.loader import FARMER_NAMES
from core.db import save_metricas_weekly, load_metricas_weekly

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Métricas Semanales — Rappi Farmers",
    page_icon="📊",
    layout="wide", initial_sidebar_state="expanded",
)
st.markdown(inject_global_css(), unsafe_allow_html=True)
email, is_supervisor = require_auth()
render_topbar()

# ── Constants ─────────────────────────────────────────────────────────────────
ALARM_RED    = -0.10
ALARM_YELLOW = -0.05

METRIC_ICONS = {
    "Orders": "🛒", "GMV": "💰", "AOV": "📦", "Markdown": "🏷️",
    "Bookings": "📅", "Traffic": "👥", "Revenue": "💵",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _farmer_name(email_str: str) -> str:
    return FARMER_NAMES.get(email_str, email_str.split("@")[0].replace(".", " ").title())


def _sema(vs) -> str:
    if vs is None or (isinstance(vs, float) and pd.isna(vs)):
        return "⚪"
    try:
        v = float(vs)
    except (TypeError, ValueError):
        return "⚪"
    if v <= ALARM_RED:
        return "🔴"
    if v <= ALARM_YELLOW:
        return "🟡"
    if v >= 0.05:
        return "🟢"
    return "⚪"


def _fmt_pct(vs) -> str:
    if vs is None or (isinstance(vs, float) and pd.isna(vs)):
        return "—"
    try:
        return f"{float(vs)*100:+.1f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_val(metric: str, v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return str(v)
    name = metric.upper()
    if "GMV" in name or "REVENUE" in name or "MARKDOWN" in name or "AOV" in name:
        if "AOV" in name:
            return f"${fv:,.2f}"
        return f"${fv:,.0f}"
    if "CVR" in name or "%" in metric:
        # Determine scale: if abs value ≤ 1 treat as decimal ratio
        if abs(fv) <= 1:
            return f"{fv:.2%}"
        return f"{fv:.2f}%"
    return f"{fv:,.0f}"


# ── Excel parser ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _parse_excel(file_bytes: bytes):
    """
    Returns (farmer_records, brand_records) as lists of dicts.
    Wide-format Excel → long format.
    Hierarchy: level 3 = farmer aggregate, level 4 = brand.
    """
    df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None)

    # Extract week dates from row 0, cols 4+ every 2 columns
    weeks = []
    c = 4
    while c < df_raw.shape[1]:
        v = df_raw.iloc[0, c]
        if pd.notna(v):
            try:
                weeks.append(str(pd.Timestamp(v).date()))
            except Exception:
                pass
        c += 2

    farmer_recs = []
    brand_recs  = []

    for ri in range(2, df_raw.shape[0]):
        row = df_raw.iloc[ri]
        metric = row.iloc[0]
        if not isinstance(metric, str) or not metric.strip():
            continue

        metric = metric.strip()
        country = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
        f_raw   = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
        b_raw   = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""

        # Skip global totals (no farmer) and country-level aggregates
        if not f_raw or f_raw in ("Total", "nan", ""):
            continue

        is_farmer_row = b_raw in ("Total", "nan", "")
        is_brand_row  = b_raw not in ("Total", "nan", "")

        for i, week in enumerate(weeks):
            vc  = 4 + i * 2
            vlc = 5 + i * 2
            if vc >= df_raw.shape[1]:
                break

            rv  = row.iloc[vc]
            rvl = row.iloc[vlc] if vlc < df_raw.shape[1] else None

            val  = float(rv)  if pd.notna(rv)  else None
            vslw = float(rvl) if pd.notna(rvl) else None

            rec = {
                "week":    week,
                "metric":  metric,
                "country": country,
                "farmer":  f_raw,
                "brand":   b_raw if is_brand_row else "Total",
                "value":   val,
                "vs_lw":   vslw,
            }
            if is_farmer_row:
                farmer_recs.append(rec)
            elif is_brand_row:
                brand_recs.append(rec)

    return farmer_recs, brand_recs


# ── Merge accumulated weeks ───────────────────────────────────────────────────

def _merge(new_recs: list, stored_recs: list) -> list:
    """Keep stored records for weeks not in new file; use new file for its weeks."""
    if not stored_recs:
        return new_recs
    new_weeks = {r["week"] for r in new_recs}
    old_only  = [r for r in stored_recs if r["week"] not in new_weeks]
    return old_only + new_recs


# ── Bootstrap ─────────────────────────────────────────────────────────────────

if "met_farmer_recs" not in st.session_state:
    stored = load_metricas_weekly()
    st.session_state["met_farmer_recs"] = stored or []

if "met_brand_recs" not in st.session_state:
    st.session_state["met_brand_recs"] = []

farmer_recs: list = st.session_state["met_farmer_recs"]
brand_recs:  list = st.session_state["met_brand_recs"]

# Build DataFrame views
farmer_df = pd.DataFrame(farmer_recs) if farmer_recs else pd.DataFrame()
brand_df  = pd.DataFrame(brand_recs)  if brand_recs  else pd.DataFrame()

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="rb-page-header">
    <h1>📊 Métricas Semanales del Equipo</h1>
    <p>Monitoreo semanal de Orders · GMV · CVR · Revenue y más.
       Alarmas automáticas por caída >10% vs semana anterior.</p>
</div>
""", unsafe_allow_html=True)

# ── Upload (supervisor only) ──────────────────────────────────────────────────

if is_supervisor:
    weeks_loaded = sorted(farmer_df["week"].unique()) if not farmer_df.empty else []
    with st.expander(
        f"⬆️ Cargar archivo semanal ({len(weeks_loaded)} semanas en DB)",
        expanded=(not farmer_recs),
    ):
        st.caption(
            "Subí el export 'Metrics Weekly by Hierarchy Level' — "
            "mismo formato de todos los lunes. Las semanas nuevas se acumulan automáticamente."
        )
        uploaded = st.file_uploader(
            "Metrics Weekly (.xlsx)", type=["xlsx"], key="met_upload"
        )
        if uploaded is not None:
            with st.spinner("Procesando y acumulando semanas..."):
                try:
                    raw_bytes = uploaded.read()
                    new_farmer, new_brand = _parse_excel(raw_bytes)
                    merged = _merge(new_farmer, farmer_recs)

                    save_metricas_weekly(merged)
                    st.session_state["met_farmer_recs"] = merged
                    st.session_state["met_brand_recs"]  = new_brand
                    farmer_recs = merged
                    brand_recs  = new_brand
                    farmer_df   = pd.DataFrame(farmer_recs)
                    brand_df    = pd.DataFrame(brand_recs)

                    new_weeks = sorted({r["week"] for r in new_farmer})
                    total_weeks = sorted({r["week"] for r in merged})
                    st.success(
                        f"✅ Archivo procesado · {len(new_weeks)} semanas nuevas · "
                        f"Total acumulado: **{len(total_weeks)} semanas** · "
                        f"{len(new_farmer):,} registros de farmers"
                    )
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error al procesar el archivo: {ex}")

if farmer_df.empty:
    st.info(
        "⬆️ Aún no hay datos cargados. "
        "Subí el archivo de Métricas Semanales para comenzar el monitoreo."
    )
    st.stop()

# ── Sidebar filters ───────────────────────────────────────────────────────────

all_weeks   = sorted(farmer_df["week"].unique(), reverse=True)
all_metrics = sorted(farmer_df["metric"].unique())
latest_week = all_weeks[0]

with st.sidebar:
    st.markdown("### 📊 Filtros")
    sel_week = st.selectbox(
        "Semana de análisis", all_weeks, key="met_week",
        format_func=lambda w: f"Sem. {w}",
    )
    sel_country = st.radio("País", ["Todos", "AR", "UY"], key="met_country")
    sel_metrics = st.multiselect(
        "Métricas a mostrar", all_metrics,
        default=[m for m in ["Orders", "GMV", "CVR (%)", "Revenue"] if m in all_metrics]
                or all_metrics[:4],
        key="met_metrics",
    )
    if not sel_metrics:
        sel_metrics = all_metrics[:4]

    st.markdown("---")
    st.markdown("##### Leyenda")
    st.markdown("🔴 Caída >10% vs LW  \n🟡 Caída 5-10% vs LW  \n⚪ Sin cambio significativo  \n🟢 Mejora >5% vs LW")


def _apply_country(df: pd.DataFrame) -> pd.DataFrame:
    if sel_country == "Todos":
        return df[df["country"].isin(["AR", "UY"])]
    return df[df["country"] == sel_country]


week_df = _apply_country(farmer_df[farmer_df["week"] == sel_week])

# ── KPI summary row ───────────────────────────────────────────────────────────

red_mask  = week_df["vs_lw"] <= ALARM_RED
yell_mask = (week_df["vs_lw"] > ALARM_RED) & (week_df["vs_lw"] <= ALARM_YELLOW)
red_count  = int(red_mask.sum())
yell_count = int(yell_mask.sum())

worst_row = None
valid_vs = week_df["vs_lw"].dropna()
if not valid_vs.empty:
    worst_idx = valid_vs.idxmin()
    worst_row = week_df.loc[worst_idx]

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("📅 Semana analizada", sel_week)
with c2:
    st.metric("🔴 Alarmas críticas", red_count,
              help="Métricas con caída >10% vs semana anterior")
with c3:
    st.metric("🟡 En seguimiento", yell_count,
              help="Métricas con caída 5-10% vs semana anterior")
with c4:
    if worst_row is not None:
        wname  = _farmer_name(worst_row["farmer"])
        wmetric = worst_row["metric"]
        wpct    = f"{float(worst_row['vs_lw'])*100:+.1f}%"
        st.metric("📉 Mayor caída", wpct,
                  delta=f"{wname} — {wmetric}", delta_color="inverse")

st.markdown("---")

# ── Alarm panel ───────────────────────────────────────────────────────────────

red_alarms  = week_df[red_mask].sort_values("vs_lw")
yell_alarms = week_df[yell_mask].sort_values("vs_lw")

def _alarm_card(row, color: str, bg: str, border_l: str, text_c: str) -> str:
    name = _farmer_name(row["farmer"])
    icon = METRIC_ICONS.get(row["metric"], "📊")
    pct  = _fmt_pct(row["vs_lw"])
    return f"""
    <div style="background:{bg};border:1px solid {color}33;border-left:4px solid {color};
                border-radius:10px;padding:0.85rem 1rem;margin-bottom:0.6rem">
        <div style="font-weight:700;color:{text_c};font-size:0.88rem">{icon} {row['metric']}</div>
        <div style="font-weight:600;color:{text_c};font-size:0.82rem;margin-top:2px">{name}</div>
        <div style="color:{color};font-size:1.1rem;font-weight:800;margin-top:4px">{pct}</div>
        <div style="color:{text_c};font-size:0.72rem;opacity:0.65;margin-top:2px">
            {row['country']} · {row['week']}
        </div>
    </div>"""

if red_alarms.empty and yell_alarms.empty:
    st.markdown("""
    <div style="background:#F0FDF4;border:1px solid #86EFAC;border-left:4px solid #22C55E;
                border-radius:12px;padding:1rem 1.4rem;margin-bottom:1rem">
        <div style="font-weight:700;color:#166534;font-size:1rem">✅ Sin alarmas esta semana</div>
        <div style="color:#15803D;font-size:0.85rem;margin-top:2px">
            Ninguna métrica del equipo cayó más del 5% vs semana anterior.
        </div>
    </div>""", unsafe_allow_html=True)
else:
    if not red_alarms.empty:
        st.markdown(f"### 🔴 Alarmas críticas — caída >10% &nbsp; `{len(red_alarms)} registros`")
        n_cols = min(3, len(red_alarms))
        cols   = st.columns(n_cols)
        for ci, row in enumerate(red_alarms.to_dict("records")):
            with cols[ci % n_cols]:
                st.markdown(
                    _alarm_card(row, "#EF4444", "#FEF2F2", "#EF4444", "#991B1B"),
                    unsafe_allow_html=True,
                )

    if not yell_alarms.empty:
        st.markdown(f"### 🟡 En seguimiento — caída 5–10% &nbsp; `{len(yell_alarms)} registros`")
        n_cols = min(4, len(yell_alarms))
        cols   = st.columns(n_cols)
        for ci, row in enumerate(yell_alarms.to_dict("records")):
            with cols[ci % n_cols]:
                st.markdown(
                    _alarm_card(row, "#F59E0B", "#FFFBEB", "#F59E0B", "#78350F"),
                    unsafe_allow_html=True,
                )

# Brand-level alarms (only when file was uploaded this session)
if not brand_df.empty:
    brand_week_df = _apply_country(brand_df[brand_df["week"] == sel_week])
    brand_red = brand_week_df[brand_week_df["vs_lw"] <= ALARM_RED]
    if not brand_red.empty:
        st.markdown(f"#### 🔴 Alarmas por Brand — caída >10% &nbsp; `{len(brand_red)} brands`")
        n_cols = min(3, len(brand_red))
        cols   = st.columns(n_cols)
        brand_red_sorted = brand_red.sort_values("vs_lw")
        for ci, row in enumerate(brand_red_sorted.to_dict("records")):
            name = _farmer_name(row["farmer"])
            icon = METRIC_ICONS.get(row["metric"], "📊")
            pct  = _fmt_pct(row["vs_lw"])
            with cols[ci % n_cols]:
                st.markdown(f"""
                <div style="background:#FFF1EE;border:1px solid #FF441B44;border-left:4px solid #FF441B;
                            border-radius:10px;padding:0.75rem 0.9rem;margin-bottom:0.5rem">
                    <div style="font-weight:700;color:#9A2500;font-size:0.86rem">{icon} {row['metric']}</div>
                    <div style="color:#9A2500;font-size:0.78rem;margin-top:2px">
                        <b>{name}</b> · {row.get('brand','')}
                    </div>
                    <div style="color:#FF441B;font-size:1rem;font-weight:800;margin-top:3px">{pct}</div>
                    <div style="color:#9A2500;font-size:0.71rem;opacity:0.6">{row['country']}</div>
                </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── Team comparison table ─────────────────────────────────────────────────────

st.markdown("### 📋 Vista del equipo — semana seleccionada")

all_farmer_emails = sorted(
    e for e in week_df["farmer"].unique()
    if e not in ("Total", "nan", "")
)

if sel_metrics and all_farmer_emails:
    pivot_rows = []
    for femail in all_farmer_emails:
        row_data = {"Farmer": _farmer_name(femail)}
        fdata    = week_df[week_df["farmer"] == femail]
        any_red  = False
        for metric in sel_metrics:
            mdata = fdata[fdata["metric"] == metric]
            if mdata.empty:
                row_data[metric] = "—"
                continue
            val  = mdata.iloc[0]["value"]
            vslw = mdata.iloc[0]["vs_lw"]
            sem  = _sema(vslw)
            if sem == "🔴":
                any_red = True
            row_data[metric] = f"{sem} {_fmt_val(metric, val)} ({_fmt_pct(vslw)})"
        row_data["_alert"] = any_red
        pivot_rows.append(row_data)

    # Sort: farmers with red alerts first
    pivot_rows.sort(key=lambda r: (not r["_alert"], r["Farmer"]))

    pivot_df = pd.DataFrame(pivot_rows)
    display_cols = ["Farmer"] + [m for m in sel_metrics if m in pivot_df.columns]

    st.data_editor(
        pivot_df[display_cols],
        use_container_width=True,
        hide_index=True,
        disabled=True,
        column_config={
            "Farmer": st.column_config.TextColumn("Farmer", width="medium"),
            **{
                m: st.column_config.TextColumn(
                    f"{METRIC_ICONS.get(m, '📊')} {m}", width="medium"
                )
                for m in sel_metrics if m in pivot_df.columns
            },
        },
    )
    st.caption("🔴 >10% caída · 🟡 5–10% caída · ⚪ sin cambio significativo · 🟢 >5% mejora")

st.markdown("---")

# ── Trend chart ───────────────────────────────────────────────────────────────

st.markdown("### 📈 Evolución histórica")

col_met, col_far = st.columns([1, 2])
with col_met:
    trend_metric = st.selectbox(
        "Métrica", sel_metrics or all_metrics[:1], key="trend_metric"
    )
with col_far:
    all_emails_hist = sorted(
        e for e in farmer_df["farmer"].unique()
        if e not in ("Total", "nan", "")
    )
    name_map = {e: _farmer_name(e) for e in all_emails_hist}
    trend_farmers = st.multiselect(
        "Farmers",
        options=all_emails_hist,
        default=all_emails_hist[:6],
        format_func=lambda e: name_map.get(e, e),
        key="trend_farmers",
    )

show_pct = st.toggle("Mostrar % vs LW en lugar de valor absoluto", key="trend_pct")

if trend_metric and trend_farmers:
    trend_df = _apply_country(
        farmer_df[
            (farmer_df["metric"] == trend_metric) &
            (farmer_df["farmer"].isin(trend_farmers))
        ]
    ).sort_values("week")

    y_col   = "vs_lw" if show_pct else "value"
    y_title = "Variación vs LW (%)" if show_pct else trend_metric

    if not trend_df.empty:
        fig = go.Figure()

        if show_pct:
            # Add zero reference line
            fig.add_hline(y=0, line_dash="solid", line_color="#9CA3AF", line_width=1)
            fig.add_hline(y=ALARM_RED,    line_dash="dash", line_color="#EF4444",
                          line_width=1, annotation_text="-10%", annotation_position="right")
            fig.add_hline(y=ALARM_YELLOW, line_dash="dash", line_color="#F59E0B",
                          line_width=1, annotation_text="-5%",  annotation_position="right")

        for femail in trend_farmers:
            fd = trend_df[trend_df["farmer"] == femail].copy()
            if fd.empty:
                continue
            fname = name_map.get(femail, femail)

            if show_pct:
                fd["y_plot"] = fd["vs_lw"] * 100
                hover_tmpl = (
                    f"<b>{fname}</b><br>%{{x}}<br>"
                    f"{trend_metric}: %{{customdata:.1f}}<br>"
                    "Vs. LW: %{y:+.1f}%<extra></extra>"
                )
                customdata = fd["value"]
            else:
                fd["y_plot"] = fd["value"]
                hover_tmpl = (
                    f"<b>{fname}</b><br>%{{x}}<br>"
                    f"{trend_metric}: %{{y:,.2f}}<extra></extra>"
                )
                customdata = fd["vs_lw"] * 100 if "vs_lw" in fd.columns else fd["value"]

            # Color markers by alarm status
            marker_colors = []
            for vs in fd["vs_lw"]:
                s = _sema(vs)
                if s == "🔴":
                    marker_colors.append("#EF4444")
                elif s == "🟡":
                    marker_colors.append("#F59E0B")
                elif s == "🟢":
                    marker_colors.append("#22C55E")
                else:
                    marker_colors.append("#6B7280")

            fig.add_trace(go.Scatter(
                x=fd["week"],
                y=fd["y_plot"],
                mode="lines+markers",
                name=fname,
                customdata=customdata,
                hovertemplate=hover_tmpl,
                line=dict(width=2),
                marker=dict(size=7, color=marker_colors, line=dict(width=1, color="white")),
            ))

        fig.update_layout(
            height=400,
            margin=dict(l=10, r=60, t=20, b=20),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="Semana", showgrid=True, gridcolor="#F3F4F6",
                       tickangle=-30),
            yaxis=dict(title=y_title, showgrid=True, gridcolor="#F3F4F6",
                       tickformat="+.1f" if show_pct else ",.1f"),
            legend=dict(orientation="h", y=-0.25, x=0),
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)
        if show_pct:
            st.caption("Línea roja = umbral -10% · Línea amarilla = umbral -5%")

st.markdown("---")

# ── Brand drill-down ──────────────────────────────────────────────────────────

st.markdown("### 🔍 Drill-down por Farmer / Brand")

if brand_df.empty:
    st.info(
        "💡 El drill-down por brand solo está disponible cuando el archivo "
        "se cargó en esta sesión. Los datos de farmer están cargados desde la DB."
    )
else:
    drill_cols = st.columns([1, 1])
    with drill_cols[0]:
        drill_metric = st.selectbox(
            "Métrica", sel_metrics or all_metrics[:1], key="drill_metric"
        )
    with drill_cols[1]:
        drill_week_sel = st.selectbox(
            "Semana", all_weeks, key="drill_week",
            format_func=lambda w: f"Sem. {w}",
        )

    drill_data = brand_df[
        (brand_df["week"] == drill_week_sel) &
        (brand_df["metric"] == drill_metric)
    ]
    if sel_country != "Todos":
        drill_data = drill_data[drill_data["country"] == sel_country]

    drill_emails = sorted(
        e for e in drill_data["farmer"].unique()
        if e not in ("Total", "nan", "")
    )

    for femail in drill_emails:
        fbrands = drill_data[drill_data["farmer"] == femail].copy()
        fbrands = fbrands.sort_values("vs_lw")

        fname       = _farmer_name(femail)
        n_red       = int((fbrands["vs_lw"] <= ALARM_RED).sum())
        n_yell      = int(((fbrands["vs_lw"] > ALARM_RED) &
                           (fbrands["vs_lw"] <= ALARM_YELLOW)).sum())
        status_icon = "🔴" if n_red > 0 else ("🟡" if n_yell > 0 else "✅")
        badges      = ""
        if n_red:
            badges += f" 🔴 {n_red}"
        if n_yell:
            badges += f" 🟡 {n_yell}"

        with st.expander(
            f"{status_icon} {fname}{badges} — {len(fbrands)} brands",
            expanded=(n_red > 0),
        ):
            tbl = fbrands[["brand", "value", "vs_lw"]].copy()
            tbl["Sem"] = tbl["vs_lw"].apply(_sema)
            tbl["Vs. LW"] = tbl["vs_lw"].apply(_fmt_pct)
            tbl["Valor"]  = tbl["value"].apply(lambda v: _fmt_val(drill_metric, v))
            tbl = tbl.rename(columns={"brand": "Brand"})

            st.data_editor(
                tbl[["Sem", "Brand", "Valor", "Vs. LW"]],
                use_container_width=True,
                hide_index=True,
                disabled=True,
                column_config={
                    "Sem":    st.column_config.TextColumn("", width="small"),
                    "Brand":  st.column_config.TextColumn("Brand", width="large"),
                    "Valor":  st.column_config.TextColumn(drill_metric, width="medium"),
                    "Vs. LW": st.column_config.TextColumn("Vs. semana ant.", width="small"),
                },
            )
