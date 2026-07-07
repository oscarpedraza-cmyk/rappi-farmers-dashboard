"""
0_Alertas.py — Análisis semanal con storytelling visual.
Aparece primero en la barra lateral por prefijo 0_.
"""
from __future__ import annotations
import sys
import io
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.auth import require_auth, render_topbar
from core.style import inject_global_css
from core.loader import FARMER_NAMES
from core.db import save_metricas_weekly, load_metricas_weekly

st.set_page_config(
    page_title="Alertas — Rappi Farmers",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(inject_global_css(), unsafe_allow_html=True)
email, is_supervisor = require_auth()
render_topbar()

# ── Constants ─────────────────────────────────────────────────────────────────
ALARM_RED    = -0.10
ALARM_YELLOW = -0.05

C_RED    = "#EF4444"
C_YELLOW = "#F59E0B"
C_GREEN  = "#22C55E"
C_MUTED  = "#6B7280"

METRIC_ICONS = {
    "Orders": "🛒", "GMV": "💰", "AOV": "📦", "Markdown": "🏷️",
    "Bookings": "📅", "Traffic": "👥", "Revenue": "💵",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _farmer_name(email_str: str) -> str:
    return FARMER_NAMES.get(email_str, email_str.split("@")[0].replace(".", " ").title())


def _sema(vs: object) -> str:
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


def _sema_color(vs: object) -> str:
    s = _sema(vs)
    return C_RED if s == "🔴" else C_YELLOW if s == "🟡" else C_GREEN if s == "🟢" else C_MUTED


def _fmt_pct(vs: object) -> str:
    if vs is None or (isinstance(vs, float) and pd.isna(vs)):
        return "—"
    try:
        return f"{float(vs)*100:+.1f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_val(metric: str, v: object) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return str(v)
    name = metric.upper()
    if "GMV" in name or "REVENUE" in name or "MARKDOWN" in name:
        return f"${fv:,.0f}"
    if "AOV" in name:
        return f"${fv:,.2f}"
    if "CVR" in name or "%" in metric:
        return f"{fv:.2%}" if abs(fv) <= 1 else f"{fv:.2f}%"
    return f"{fv:,.0f}"


# ── Excel parser (same format as Metrics Weekly by Hierarchy Level) ───────────

@st.cache_data(show_spinner=False)
def _parse_excel(file_bytes: bytes) -> tuple[list, list]:
    df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None)

    weeks: list[str] = []
    c = 4
    while c < df_raw.shape[1]:
        v = df_raw.iloc[0, c]
        if pd.notna(v):
            try:
                weeks.append(str(pd.Timestamp(v).date()))
            except Exception:
                pass
        c += 2

    farmer_recs: list[dict] = []
    brand_recs:  list[dict] = []

    for ri in range(2, df_raw.shape[0]):
        row    = df_raw.iloc[ri]
        metric = row.iloc[0]
        if not isinstance(metric, str) or not metric.strip():
            continue
        metric  = metric.strip()
        country = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
        f_raw   = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
        b_raw   = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""

        if not f_raw or f_raw in ("Total", "nan", ""):
            continue

        is_farmer_row = b_raw in ("Total", "nan", "")
        is_brand_row  = b_raw not in ("Total", "nan", "")

        for i, week in enumerate(weeks):
            vc  = 4 + i * 2
            vlc = 5 + i * 2
            if vc >= df_raw.shape[1]:
                break
            rv   = row.iloc[vc]
            rvl  = row.iloc[vlc] if vlc < df_raw.shape[1] else None
            val  = float(rv)  if pd.notna(rv)  else None
            vslw = float(rvl) if pd.notna(rvl) else None
            rec  = {
                "week": week, "metric": metric, "country": country,
                "farmer": f_raw, "brand": b_raw if is_brand_row else "Total",
                "value": val, "vs_lw": vslw,
            }
            if is_farmer_row:
                farmer_recs.append(rec)
            elif is_brand_row:
                brand_recs.append(rec)

    return farmer_recs, brand_recs


def _merge(new_recs: list, stored_recs: list) -> list:
    if not stored_recs:
        return new_recs
    new_weeks = {r["week"] for r in new_recs}
    return [r for r in stored_recs if r["week"] not in new_weeks] + new_recs


# ── Bootstrap ─────────────────────────────────────────────────────────────────

if "met_farmer_recs" not in st.session_state:
    st.session_state["met_farmer_recs"] = load_metricas_weekly() or []
if "met_brand_recs" not in st.session_state:
    st.session_state["met_brand_recs"] = []

farmer_recs: list = st.session_state["met_farmer_recs"]
brand_recs:  list = st.session_state["met_brand_recs"]

farmer_df = pd.DataFrame(farmer_recs) if farmer_recs else pd.DataFrame()
brand_df  = pd.DataFrame(brand_recs)  if brand_recs  else pd.DataFrame()

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="rb-page-header">
    <h1>🚨 Alertas & Análisis Semanal</h1>
    <p>Ranking del equipo · Evolución histórica · Alarmas automáticas por caída vs semana anterior.</p>
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
            "Export 'Metrics Weekly by Hierarchy Level' — "
            "mismo formato cada lunes. Las semanas nuevas se acumulan automáticamente."
        )
        uploaded = st.file_uploader("Metrics Weekly (.xlsx)", type=["xlsx"], key="met_upload")
        if uploaded is not None:
            with st.spinner("Procesando..."):
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
                    new_weeks   = sorted({r["week"] for r in new_farmer})
                    total_weeks = sorted({r["week"] for r in merged})
                    st.success(
                        f"✅ {len(new_weeks)} semanas nuevas · "
                        f"Total: **{len(total_weeks)} semanas** · "
                        f"{len(new_farmer):,} registros"
                    )
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error al procesar: {ex}")

if farmer_df.empty:
    st.info("⬆️ Subí el archivo de Métricas Semanales para comenzar el análisis.")
    st.stop()

# ── Sidebar filters ───────────────────────────────────────────────────────────

all_weeks   = sorted(farmer_df["week"].unique(), reverse=True)
all_metrics = sorted(farmer_df["metric"].unique())

with st.sidebar:
    st.markdown("### 🔍 Filtros")
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
    st.markdown("🔴 Caída >10% vs LW  \n🟡 Caída 5–10% vs LW  \n⚪ Sin cambio  \n🟢 Mejora >5%")


def _apply_country(df: pd.DataFrame) -> pd.DataFrame:
    if sel_country == "Todos":
        return df[df["country"].isin(["AR", "UY"])]
    return df[df["country"] == sel_country]


week_df = _apply_country(farmer_df[farmer_df["week"] == sel_week])

# ── KPI summary row ───────────────────────────────────────────────────────────

red_mask   = week_df["vs_lw"] <= ALARM_RED
yell_mask  = (week_df["vs_lw"] > ALARM_RED) & (week_df["vs_lw"] <= ALARM_YELLOW)
green_mask = week_df["vs_lw"] >= 0.05
red_count  = int(red_mask.sum())
yell_count = int(yell_mask.sum())
green_count= int(green_mask.sum())

worst_row = None
valid_vs  = week_df["vs_lw"].dropna()
if not valid_vs.empty:
    worst_row = week_df.loc[valid_vs.idxmin()]

best_row = None
if not valid_vs.empty:
    best_row = week_df.loc[valid_vs.idxmax()]

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("📅 Semana", sel_week)
with c2:
    st.metric("🔴 Alarmas críticas", red_count, help="Caída >10% vs semana anterior")
with c3:
    st.metric("🟡 En seguimiento", yell_count, help="Caída 5-10% vs semana anterior")
with c4:
    st.metric("🟢 Mejorando", green_count, help="Mejora >5% vs semana anterior")

st.markdown("---")

# ── ① Resumen ejecutivo (storytelling narrativo) ──────────────────────────────

country_label = sel_country if sel_country != "Todos" else "el equipo"
n_farmers_w   = week_df["farmer"].nunique()

if worst_row is not None:
    worst_name   = _farmer_name(worst_row["farmer"])
    worst_metric = worst_row["metric"]
    worst_pct    = _fmt_pct(worst_row["vs_lw"])

if best_row is not None and float(best_row["vs_lw"] or 0) > 0:
    best_name   = _farmer_name(best_row["farmer"])
    best_metric = best_row["metric"]
    best_pct    = _fmt_pct(best_row["vs_lw"])
    best_line   = f"La mejor señal: <b>{best_name}</b> con <b style='color:{C_GREEN}'>{best_pct}</b> en {best_metric}."
else:
    best_line = ""

if red_count == 0 and yell_count == 0:
    headline = f"✅ Semana limpia para {country_label} — sin alarmas."
    headline_color = "#166534"
    headline_bg    = "#F0FDF4"
    headline_border= "#22C55E"
elif red_count >= 5:
    headline = f"🚨 Semana crítica para {country_label} — {red_count} alarmas rojas activas."
    headline_color = "#991B1B"
    headline_bg    = "#FEF2F2"
    headline_border= C_RED
else:
    headline = f"⚠️ {red_count} alarma{'s' if red_count != 1 else ''} roja{'s' if red_count != 1 else ''} · {yell_count} en seguimiento para {country_label}."
    headline_color = "#78350F"
    headline_bg    = "#FFFBEB"
    headline_border= C_YELLOW

worst_line = (
    f"Mayor caída: <b>{worst_name}</b> perdió <b style='color:{C_RED}'>{worst_pct}</b> en <b>{worst_metric}</b>."
    if worst_row is not None else ""
)

st.markdown(f"""
<div style="background:{headline_bg};border-left:5px solid {headline_border};
            border-radius:0 12px 12px 0;padding:1rem 1.4rem;margin-bottom:1.2rem">
    <div style="font-size:1.1rem;font-weight:800;color:{headline_color};margin-bottom:0.4rem">
        {headline}
    </div>
    <div style="font-size:0.88rem;color:#374151;line-height:1.6">
        Se analizaron <b>{n_farmers_w} farmers</b> con <b>{len(week_df)} registros</b>
        de métricas en {country_label}. {worst_line} {best_line}
    </div>
</div>
""", unsafe_allow_html=True)

# ── ② Alarm cards ─────────────────────────────────────────────────────────────

red_alarms  = week_df[red_mask].sort_values("vs_lw")
yell_alarms = week_df[yell_mask].sort_values("vs_lw")


def _alarm_card(row: dict, color: str, bg: str, text_c: str) -> str:
    name = _farmer_name(row["farmer"])
    icon = METRIC_ICONS.get(row["metric"], "📊")
    pct  = _fmt_pct(row["vs_lw"])
    val  = _fmt_val(row["metric"], row["value"])
    return f"""
    <div style="background:{bg};border:1px solid {color}33;border-left:4px solid {color};
                border-radius:10px;padding:0.85rem 1rem;margin-bottom:0.6rem">
        <div style="font-weight:700;color:{text_c};font-size:0.88rem">{icon} {row['metric']}</div>
        <div style="font-weight:600;color:{text_c};font-size:0.82rem;margin-top:2px">{name}</div>
        <div style="color:{color};font-size:1.1rem;font-weight:800;margin-top:4px">{pct}</div>
        <div style="color:{text_c};font-size:0.75rem;margin-top:2px;opacity:0.7">
            Valor actual: {val} &nbsp;·&nbsp; {row['country']}
        </div>
    </div>"""


if not red_alarms.empty:
    st.markdown(f"### 🔴 Alarmas críticas — caída >10% &nbsp; `{len(red_alarms)} registros`")
    n_cols = min(3, len(red_alarms))
    cols   = st.columns(n_cols)
    for ci, row in enumerate(red_alarms.to_dict("records")):
        with cols[ci % n_cols]:
            st.markdown(_alarm_card(row, C_RED, "#FEF2F2", "#991B1B"), unsafe_allow_html=True)

if not yell_alarms.empty:
    st.markdown(f"### 🟡 En seguimiento — caída 5–10% &nbsp; `{len(yell_alarms)} registros`")
    n_cols = min(4, len(yell_alarms))
    cols   = st.columns(n_cols)
    for ci, row in enumerate(yell_alarms.to_dict("records")):
        with cols[ci % n_cols]:
            st.markdown(_alarm_card(row, C_YELLOW, "#FFFBEB", "#78350F"), unsafe_allow_html=True)

if red_alarms.empty and yell_alarms.empty:
    st.markdown("""
    <div style="background:#F0FDF4;border:1px solid #86EFAC;border-left:4px solid #22C55E;
                border-radius:12px;padding:1rem 1.4rem;margin-bottom:1rem">
        <div style="font-weight:700;color:#166534">✅ Sin alarmas esta semana</div>
        <div style="color:#15803D;font-size:0.85rem;margin-top:2px">
            Ninguna métrica cayó más del 5% vs semana anterior.
        </div>
    </div>""", unsafe_allow_html=True)

# Brand-level alarms
if not brand_df.empty:
    brand_week_df = _apply_country(brand_df[brand_df["week"] == sel_week])
    brand_red     = brand_week_df[brand_week_df["vs_lw"] <= ALARM_RED]
    if not brand_red.empty:
        st.markdown(f"#### 🔴 Alarmas por Brand — `{len(brand_red)} brands`")
        n_cols = min(3, len(brand_red))
        cols   = st.columns(n_cols)
        for ci, row in enumerate(brand_red.sort_values("vs_lw").to_dict("records")):
            pct = _fmt_pct(row["vs_lw"])
            with cols[ci % n_cols]:
                st.markdown(f"""
                <div style="background:#FFF1EE;border-left:4px solid #FF441B;
                            border-radius:10px;padding:0.75rem 0.9rem;margin-bottom:0.5rem">
                    <div style="font-weight:700;color:#9A2500;font-size:0.86rem">
                        {METRIC_ICONS.get(row['metric'],'📊')} {row['metric']}
                    </div>
                    <div style="color:#9A2500;font-size:0.78rem;margin-top:2px">
                        <b>{_farmer_name(row['farmer'])}</b> · {row.get('brand','')}
                    </div>
                    <div style="color:#FF441B;font-size:1rem;font-weight:800;margin-top:3px">{pct}</div>
                    <div style="color:#9A2500;font-size:0.71rem;opacity:0.6">{row['country']}</div>
                </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── ③ Storytelling charts ─────────────────────────────────────────────────────

st.markdown("### 📊 Análisis visual del equipo")

tab_ranking, tab_trend, tab_table, tab_drill = st.tabs([
    "🏆 Ranking del equipo",
    "📈 Evolución histórica",
    "📋 Vista completa",
    "🔍 Drill-down por brand",
])

# ─── Tab 1: Ranking del equipo (barras) ───────────────────────────────────────

with tab_ranking:
    if not sel_metrics:
        st.info("Seleccioná al menos una métrica en el panel lateral.")
    else:
        all_farmer_emails = sorted(
            e for e in week_df["farmer"].unique() if e not in ("Total", "nan", "")
        )
        name_map = {e: _farmer_name(e) for e in all_farmer_emails}

        for metric in sel_metrics:
            mdata = week_df[week_df["metric"] == metric].copy()
            mdata = mdata[mdata["farmer"].isin(all_farmer_emails)].copy()
            if mdata.empty:
                continue

            mdata["name"]  = mdata["farmer"].map(name_map)
            mdata["color"] = mdata["vs_lw"].apply(_sema_color)
            mdata["label"] = mdata["vs_lw"].apply(_fmt_pct)
            mdata = mdata.sort_values("value", ascending=False)

            avg_val = mdata["value"].mean()
            icon    = METRIC_ICONS.get(metric, "📊")

            # Narrative line
            above_avg = (mdata["value"] >= avg_val).sum()
            below_avg = len(mdata) - above_avg
            n_red_m   = (mdata["vs_lw"] <= ALARM_RED).sum()
            narrative = (
                f"**{above_avg}** farmers por encima del promedio "
                f"({_fmt_val(metric, avg_val)})"
            )
            if n_red_m:
                narrative += f", **{n_red_m}** con caída crítica 🔴"

            st.markdown(
                f"<div style='font-size:0.78rem;color:#6B7280;margin:0.8rem 0 0.2rem'>"
                f"{icon} <b>{metric}</b> · {narrative}</div>",
                unsafe_allow_html=True,
            )

            fig = go.Figure()

            # Bars colored by alarm status
            fig.add_trace(go.Bar(
                x=mdata["name"],
                y=mdata["value"],
                marker_color=mdata["color"],
                text=mdata["label"],
                textposition="outside",
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    f"{metric}: %{{y:,.2f}}<br>"
                    "Vs. LW: %{text}<extra></extra>"
                ),
                name=metric,
            ))

            # Average reference line
            fig.add_hline(
                y=avg_val,
                line_dash="dash",
                line_color="#9CA3AF",
                line_width=1.5,
                annotation_text=f"Prom. {_fmt_val(metric, avg_val)}",
                annotation_position="right",
                annotation_font_size=11,
                annotation_font_color="#6B7280",
            )

            fig.update_layout(
                height=260,
                margin=dict(l=0, r=90, t=10, b=40),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                xaxis=dict(showgrid=False, tickangle=-30, tickfont_size=11),
                yaxis=dict(showgrid=True, gridcolor="#F3F4F6",
                           tickformat=",.0f", tickfont_size=11),
            )
            st.plotly_chart(fig, use_container_width=True, key=f"bar_{metric}")

# ─── Tab 2: Evolución histórica (líneas) ──────────────────────────────────────

with tab_trend:
    col_tmet, col_tfar = st.columns([1, 2])
    with col_tmet:
        trend_metric = st.selectbox(
            "Métrica", sel_metrics or all_metrics[:1], key="trend_metric"
        )
    with col_tfar:
        all_emails_hist = sorted(
            e for e in farmer_df["farmer"].unique() if e not in ("Total", "nan", "")
        )
        name_map_hist = {e: _farmer_name(e) for e in all_emails_hist}
        trend_farmers = st.multiselect(
            "Farmers",
            options=all_emails_hist,
            default=all_emails_hist[:6],
            format_func=lambda e: name_map_hist.get(e, e),
            key="trend_farmers",
        )

    show_pct = st.toggle("Mostrar % vs LW en lugar de valor absoluto", key="trend_pct")
    show_avg = st.toggle("Mostrar promedio del equipo", value=True, key="trend_avg")

    if trend_metric and trend_farmers:
        trend_df = _apply_country(
            farmer_df[
                (farmer_df["metric"] == trend_metric) &
                (farmer_df["farmer"].isin(trend_farmers))
            ]
        ).sort_values("week")

        y_col   = "vs_lw" if show_pct else "value"
        y_title = "Variación vs LW (%)" if show_pct else trend_metric

        # Narrative summary for trend
        if len(all_weeks) >= 2:
            prev_week = all_weeks[1] if all_weeks[0] == sel_week else all_weeks[0]
            cur_avg   = _apply_country(
                farmer_df[(farmer_df["metric"] == trend_metric) &
                          (farmer_df["week"] == sel_week)]
            )["value"].mean()
            prv_avg   = _apply_country(
                farmer_df[(farmer_df["metric"] == trend_metric) &
                          (farmer_df["week"] == prev_week)]
            )["value"].mean()
            if not pd.isna(cur_avg) and not pd.isna(prv_avg) and prv_avg != 0:
                delta_pct = (cur_avg - prv_avg) / abs(prv_avg) * 100
                trend_dir = "subió" if delta_pct > 0 else "bajó"
                trend_col = C_GREEN if delta_pct > 0 else C_RED
                st.markdown(
                    f"<div style='font-size:0.83rem;color:#374151;margin-bottom:0.5rem'>"
                    f"El promedio del equipo en <b>{trend_metric}</b> "
                    f"<span style='color:{trend_col};font-weight:700'>"
                    f"{trend_dir} {abs(delta_pct):.1f}%</span> vs la semana anterior "
                    f"({_fmt_val(trend_metric, prv_avg)} → {_fmt_val(trend_metric, cur_avg)}).</div>",
                    unsafe_allow_html=True,
                )

        if not trend_df.empty:
            fig = go.Figure()

            if show_pct:
                fig.add_hline(y=0,            line_dash="solid", line_color="#9CA3AF", line_width=1)
                fig.add_hline(y=ALARM_RED*100, line_dash="dash",  line_color=C_RED,    line_width=1,
                              annotation_text="-10%", annotation_position="right")
                fig.add_hline(y=ALARM_YELLOW*100, line_dash="dash", line_color=C_YELLOW, line_width=1,
                              annotation_text="-5%", annotation_position="right")

            # Team average line
            if show_avg:
                avg_by_week = (
                    _apply_country(farmer_df[farmer_df["metric"] == trend_metric])
                    .groupby("week")[y_col].mean()
                    .reset_index()
                    .sort_values("week")
                )
                y_vals = avg_by_week[y_col] * 100 if show_pct else avg_by_week[y_col]
                fig.add_trace(go.Scatter(
                    x=avg_by_week["week"],
                    y=y_vals,
                    mode="lines",
                    name="Prom. equipo",
                    line=dict(width=3, dash="dot", color="#9CA3AF"),
                    hovertemplate="<b>Promedio equipo</b><br>%{x}<br>%{y:,.2f}<extra></extra>",
                ))

            # Individual farmer lines
            _palette = px.colors.qualitative.Set2
            for idx, femail in enumerate(trend_farmers):
                fd = trend_df[trend_df["farmer"] == femail].copy()
                if fd.empty:
                    continue
                fname = name_map_hist.get(femail, femail)
                color = _palette[idx % len(_palette)]

                y_vals = fd["vs_lw"] * 100 if show_pct else fd["value"]

                marker_colors = [_sema_color(v) for v in fd["vs_lw"]]

                fig.add_trace(go.Scatter(
                    x=fd["week"],
                    y=y_vals,
                    mode="lines+markers",
                    name=fname,
                    line=dict(width=2, color=color),
                    marker=dict(size=8, color=marker_colors,
                                line=dict(width=1.5, color="white")),
                    hovertemplate=(
                        f"<b>{fname}</b><br>%{{x}}<br>{trend_metric}: %{{y:,.2f}}<extra></extra>"
                    ),
                ))

            fig.update_layout(
                height=420,
                margin=dict(l=10, r=70, t=20, b=20),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(title="Semana", showgrid=True, gridcolor="#F3F4F6",
                           tickangle=-30, tickfont_size=11),
                yaxis=dict(title=y_title, showgrid=True, gridcolor="#F3F4F6",
                           tickformat="+.1f%" if show_pct else ",.1f",
                           tickfont_size=11),
                legend=dict(orientation="h", y=-0.22, x=0, font_size=11),
                hovermode="x unified",
            )
            st.plotly_chart(fig, use_container_width=True, key="trend_fig")
            if show_pct:
                st.caption("Marcadores rojos = caída >10% · Amarillos = caída 5–10% · Verdes = mejora >5%")

# ─── Tab 3: Vista completa del equipo ─────────────────────────────────────────

with tab_table:
    all_fe = sorted(e for e in week_df["farmer"].unique() if e not in ("Total", "nan", ""))
    nm     = {e: _farmer_name(e) for e in all_fe}

    if sel_metrics and all_fe:
        pivot_rows = []
        for femail in all_fe:
            row_data = {"Farmer": nm.get(femail, femail)}
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

        pivot_rows.sort(key=lambda r: (not r["_alert"], r["Farmer"]))
        pivot_df    = pd.DataFrame(pivot_rows)
        display_col = ["Farmer"] + [m for m in sel_metrics if m in pivot_df.columns]

        st.data_editor(
            pivot_df[display_col],
            use_container_width=True,
            hide_index=True,
            disabled=True,
            column_config={
                "Farmer": st.column_config.TextColumn("Farmer", width="medium"),
                **{
                    m: st.column_config.TextColumn(
                        f"{METRIC_ICONS.get(m,'📊')} {m}", width="medium"
                    )
                    for m in sel_metrics if m in pivot_df.columns
                },
            },
        )
        st.caption("🔴 >10% caída · 🟡 5–10% caída · ⚪ sin cambio · 🟢 >5% mejora · Farmers con alerta primero")

# ─── Tab 4: Drill-down por Brand ──────────────────────────────────────────────

with tab_drill:
    if brand_df.empty:
        st.info(
            "💡 El drill-down por brand solo está disponible cuando el archivo "
            "se cargó en esta sesión."
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
        ].copy()
        if sel_country != "Todos":
            drill_data = drill_data[drill_data["country"] == sel_country]

        drill_emails = sorted(
            e for e in drill_data["farmer"].unique() if e not in ("Total", "nan", "")
        )

        for femail in drill_emails:
            fbrands = drill_data[drill_data["farmer"] == femail].sort_values("vs_lw")
            fname   = _farmer_name(femail)
            n_red   = int((fbrands["vs_lw"] <= ALARM_RED).sum())
            n_yell  = int(((fbrands["vs_lw"] > ALARM_RED) &
                           (fbrands["vs_lw"] <= ALARM_YELLOW)).sum())
            s_icon  = "🔴" if n_red else ("🟡" if n_yell else "✅")
            badges  = (f" 🔴 {n_red}" if n_red else "") + (f" 🟡 {n_yell}" if n_yell else "")

            with st.expander(f"{s_icon} {fname}{badges} — {len(fbrands)} brands"):
                fbrands["name_b"] = fbrands["brand"]
                fbrands["color"]  = fbrands["vs_lw"].apply(_sema_color)
                fbrands["label"]  = fbrands["vs_lw"].apply(_fmt_pct)
                fbrands = fbrands.sort_values("value", ascending=False)

                fig_b = go.Figure(go.Bar(
                    x=fbrands["name_b"],
                    y=fbrands["value"],
                    marker_color=fbrands["color"],
                    text=fbrands["label"],
                    textposition="outside",
                    hovertemplate=(
                        "<b>%{x}</b><br>"
                        f"{drill_metric}: %{{y:,.2f}}<br>"
                        "Vs. LW: %{text}<extra></extra>"
                    ),
                ))
                avg_b = fbrands["value"].mean()
                fig_b.add_hline(
                    y=avg_b, line_dash="dash", line_color="#9CA3AF", line_width=1,
                    annotation_text=f"Prom. {_fmt_val(drill_metric, avg_b)}",
                    annotation_position="right", annotation_font_size=10,
                )
                fig_b.update_layout(
                    height=220,
                    margin=dict(l=0, r=80, t=10, b=40),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    xaxis=dict(showgrid=False, tickangle=-30, tickfont_size=10),
                    yaxis=dict(showgrid=True, gridcolor="#F3F4F6", tickfont_size=10),
                )
                st.plotly_chart(fig_b, use_container_width=True, key=f"drill_{femail}")
