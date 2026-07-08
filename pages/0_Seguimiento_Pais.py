"""
0_Seguimiento_Pais.py — Dashboard de Seguimiento País
Vista ejecutiva: Pareto de cartera + análisis semanal filtrado.
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

st.set_page_config(
    page_title="Seguimiento País — Rappi Farmers",
    page_icon="🌍",
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
C_YELLOW = "#D97706"
C_GREEN  = "#16A34A"
C_MUTED  = "#64748B"
C_RAPPI  = "#FF441B"
_PALETTE = ["#FF441B","#3B82F6","#8B5CF6","#EC4899","#F59E0B","#10B981","#06B6D4","#6366F1"]


def _name(email_str: str) -> str:
    return FARMER_NAMES.get(email_str, email_str.split("@")[0].replace(".", " ").title())


def _sema_color(vs: object) -> str:
    try:
        v = float(vs)
        return C_RED if v <= ALARM_RED else C_YELLOW if v <= ALARM_YELLOW else (C_GREEN if v >= 0.05 else C_MUTED)
    except (TypeError, ValueError):
        return C_MUTED


def _fmt_pct(vs: object) -> str:
    try:
        return f"{float(vs)*100:+.1f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_val(metric: str, v: object) -> str:
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return "—"
    n = metric.upper()
    if "GMV" in n or "REVENUE" in n:
        return f"${fv:,.0f}"
    return f"{fv:,.1f}"


def _svg_sparkline(vals: list, width: int = 108, height: int = 38,
                   color: str = "#FF441B") -> str:
    clean = [float(v) for v in vals if v is not None and str(v) not in ("nan","")]
    if len(clean) < 2:
        return f'<svg width="{width}" height="{height}"></svg>'
    vmin, vmax = min(clean), max(clean)
    rng = max(vmax - vmin, 1e-9)
    n = len(clean)
    gap = 2
    bar_w = max(3, (width - gap * (n - 1)) / n)
    bars = []
    for i, v in enumerate(clean):
        norm = (v - vmin) / rng
        h = max(3, norm * (height - 6) + 3)
        x = i * (bar_w + gap)
        y = height - h
        fill = "#1E293B" if i == n - 1 else color
        op = "1" if i == n - 1 else "0.45"
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
            f'height="{h:.1f}" rx="2" fill="{fill}" opacity="{op}"/>'
        )
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block">'
        + "".join(bars) + "</svg>"
    )


def _kpi_card_html(title: str, value: str, subtitle: str,
                   spark_vals: list, delta_pct: float | None,
                   color: str = "#FF441B") -> str:
    svg = _svg_sparkline(spark_vals, color=color)
    if delta_pct is None:
        ds, dc = "—", "#94A3B8"
    elif delta_pct > 0.5:
        ds, dc = f"↑ {abs(delta_pct):.0f}%", "#16A34A"
    elif delta_pct < -0.5:
        ds, dc = f"↓ {abs(delta_pct):.0f}%", "#EF4444"
    else:
        ds, dc = "sin cambio", "#94A3B8"
    return (
        f'<div style="background:#FFFFFF;border-radius:10px;padding:1.05rem 1.1rem;'
        f'border:1px solid #E2E8F0;box-shadow:0 1px 3px rgba(15,23,42,0.06);height:100%">'
        f'<div style="font-size:0.54rem;text-transform:uppercase;letter-spacing:1.8px;'
        f'color:#94A3B8;font-weight:700;margin-bottom:5px">{title}</div>'
        f'<div style="font-size:2rem;font-weight:800;color:#0F172A;line-height:1;'
        f'margin-bottom:8px">{value}</div>'
        f'<div style="margin-bottom:8px">{svg}</div>'
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'border-top:1px solid #F1F5F9;padding-top:5px">'
        f'<span style="font-size:0.63rem;color:#CBD5E1">{subtitle}</span>'
        f'<span style="font-size:0.72rem;font-weight:700;color:{dc}">{ds}</span>'
        f'</div></div>'
    )


# ── Excel parser ──────────────────────────────────────────────────────────────

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
        is_brand_row = b_raw not in ("Total", "nan", "")
        for i, week in enumerate(weeks):
            vc  = 4 + i * 2
            vlc = 5 + i * 2
            if vc >= df_raw.shape[1]:
                break
            rv   = row.iloc[vc]
            rvl  = row.iloc[vlc] if vlc < df_raw.shape[1] else None
            val  = float(rv)  if pd.notna(rv)  else None
            vslw = float(rvl) if pd.notna(rvl) else None
            rec  = {"week": week, "metric": metric, "country": country,
                    "farmer": f_raw, "brand": b_raw if is_brand_row else "Total",
                    "value": val, "vs_lw": vslw}
            (brand_recs if is_brand_row else farmer_recs).append(rec)

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

# ── Upload (supervisor only) ──────────────────────────────────────────────────
if is_supervisor:
    weeks_loaded = sorted(farmer_df["week"].unique()) if not farmer_df.empty else []
    with st.expander(f"⬆️ Cargar métricas semanales ({len(weeks_loaded)} semanas)", expanded=(not farmer_recs)):
        st.caption("Export 'Metrics Weekly by Hierarchy Level' — acumula semanas automáticamente.")
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
                    st.success(f"✅ {len({r['week'] for r in new_farmer})} semanas nuevas · Total: {len({r['week'] for r in merged})} semanas")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error: {ex}")

if farmer_df.empty:
    st.info("⬆️ Cargá el archivo de Métricas Semanales para comenzar el análisis.")
    st.stop()

# ── GLOBAL FILTERS ────────────────────────────────────────────────────────────
all_weeks   = sorted(farmer_df["week"].unique(), reverse=True)
all_metrics = sorted(farmer_df["metric"].unique())
all_countries = [c for c in sorted(farmer_df["country"].unique()) if c in ("AR", "UY")]
all_farmers_emails = sorted(e for e in farmer_df["farmer"].unique() if e not in ("Total", "nan", ""))

with st.container():
    st.markdown('<div class="rb-filter-bar">', unsafe_allow_html=True)
    st.markdown('<div class="rb-filter-title">Filtros globales</div>', unsafe_allow_html=True)
    fcol1, fcol2, fcol3, fcol4 = st.columns([1, 2, 3, 3])
    with fcol1:
        sel_country = st.radio("País", ["Todos"] + all_countries, key="sp_country", horizontal=True)
    with fcol2:
        sel_week = st.selectbox("Semana", all_weeks, key="sp_week",
                                format_func=lambda w: f"Sem. {w}")
    with fcol3:
        sel_metrics = st.multiselect(
            "Métricas", all_metrics,
            default=[m for m in ["Orders","GMV","CVR (%)","Revenue"] if m in all_metrics] or all_metrics[:4],
            key="sp_metrics",
        )
    with fcol4:
        sel_farmers = st.multiselect("Farmers", all_farmers_emails,
                                      format_func=_name, key="sp_farmers")
    st.markdown('</div>', unsafe_allow_html=True)

if not sel_metrics:
    sel_metrics = all_metrics[:4]


def _apply_f(df: pd.DataFrame, week: str | None = None) -> pd.DataFrame:
    out = df.copy()
    if week:
        out = out[out["week"] == week]
    if sel_country != "Todos":
        out = out[out["country"] == sel_country]
    if sel_farmers:
        out = out[out["farmer"].isin(sel_farmers)]
    if sel_metrics:
        out = out[out["metric"].isin(sel_metrics)]
    return out


week_df = _apply_f(farmer_df, sel_week)

# ── Compute sparkline trend series (all weeks, filtered by country/farmers/metrics) ──
all_w_sorted = sorted(farmer_df["week"].unique())
_sp_red, _sp_yel, _sp_grn, _sp_tot = [], [], [], []
for _w in all_w_sorted:
    _wdf = _apply_f(farmer_df, _w)
    _vs = _wdf["vs_lw"].dropna()
    _sp_red.append(int((_vs <= ALARM_RED).sum()))
    _sp_yel.append(int(((_vs > ALARM_RED) & (_vs <= ALARM_YELLOW)).sum()))
    _sp_grn.append(int((_vs > ALARM_YELLOW).sum()))
    _sp_tot.append(len(_wdf))

# Delta vs previous week
def _delta_pct(series: list, idx_current: int) -> float | None:
    if idx_current < 1 or series[idx_current - 1] == 0:
        return None
    prev = series[idx_current - 1]
    cur  = series[idx_current]
    return (cur - prev) / prev * 100

_cur_idx = all_w_sorted.index(sel_week) if sel_week in all_w_sorted else len(all_w_sorted) - 1

# Current week values
valid_vs = week_df["vs_lw"].dropna()
red_n  = _sp_red[_cur_idx]
yell_n = _sp_yel[_cur_idx]
grn_n  = _sp_grn[_cur_idx]
n_fw   = week_df["farmer"].nunique()
worst  = week_df.loc[valid_vs.idxmin()] if not valid_vs.empty else None
cl     = sel_country if sel_country != "Todos" else "el equipo"

# Alert state
if red_n == 0 and yell_n == 0:
    al_icon, al_txt, al_bg, al_bd, al_c = "✅", "Sin alertas críticas", "#F0FDF4", "#16A34A", "#15803D"
elif red_n >= 5:
    al_icon, al_txt, al_bg, al_bd, al_c = "🚨", f"{red_n} alarmas críticas", "#FEF2F2", C_RED, "#991B1B"
else:
    al_icon, al_txt, al_bg, al_bd, al_c = "⚠️", f"{red_n} rojas · {yell_n} en seguimiento", "#FFFBEB", C_YELLOW, "#78350F"

worst_txt = (
    f"Peor: <b>{_name(worst['farmer'])}</b> {_fmt_pct(worst['vs_lw'])} en {worst['metric']}"
    if worst is not None else ""
)

# ── Dark hero banner ──────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:linear-gradient(135deg,#0F172A 0%,#1E293B 100%);
            border-radius:12px;padding:1.1rem 1.6rem;margin-bottom:1rem;
            display:flex;justify-content:space-between;align-items:center">
    <div>
        <div style="font-size:0.52rem;letter-spacing:3px;color:#475569;
                    text-transform:uppercase;font-weight:700;margin-bottom:3px">
            RAPPI FARMERS · DASHBOARD
        </div>
        <div style="font-size:1.1rem;font-weight:800;color:#FFFFFF;line-height:1.2">
            SEGUIMIENTO PAÍS
        </div>
        <div style="font-size:0.7rem;color:#475569;margin-top:4px">
            {cl.upper()} &nbsp;·&nbsp; Semana {sel_week}
            &nbsp;·&nbsp; {n_fw} farmers &nbsp;·&nbsp; {len(sel_metrics)} métricas
        </div>
    </div>
    <div style="text-align:right">
        <div style="background:{al_bg};color:{al_c};font-size:0.7rem;
                    font-weight:700;padding:5px 14px;border-radius:20px;
                    border:1px solid {al_bd};white-space:nowrap">
            {al_icon}&nbsp; {al_txt}
        </div>
        <div style="font-size:0.63rem;color:#475569;margin-top:5px">{worst_txt}</div>
    </div>
</div>""", unsafe_allow_html=True)

# ── Sparkline KPI cards ───────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
_prev_week = all_w_sorted[_cur_idx - 1] if _cur_idx > 0 else None
_prev_label = f"vs {_prev_week}" if _prev_week else "primera semana"

with k1:
    st.markdown(
        _kpi_card_html(
            "ALARMAS CRÍTICAS",
            str(red_n),
            _prev_label,
            _sp_red,
            _delta_pct(_sp_red, _cur_idx),
            color=C_RED,
        ),
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        _kpi_card_html(
            "EN SEGUIMIENTO",
            str(yell_n),
            _prev_label,
            _sp_yel,
            _delta_pct(_sp_yel, _cur_idx),
            color=C_YELLOW,
        ),
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        _kpi_card_html(
            "SIN ALERTAS",
            str(grn_n),
            _prev_label,
            _sp_grn,
            _delta_pct(_sp_grn, _cur_idx),
            color=C_GREEN,
        ),
        unsafe_allow_html=True,
    )
with k4:
    _total_cur = _sp_tot[_cur_idx]
    st.markdown(
        _kpi_card_html(
            "REGISTROS SEMANA",
            str(_total_cur),
            f"{len(all_w_sorted)} semanas de historial",
            _sp_tot,
            _delta_pct(_sp_tot, _cur_idx),
            color=C_RAPPI,
        ),
        unsafe_allow_html=True,
    )

# ── Alertas por semana — stacked bar ─────────────────────────────────────────
st.markdown(
    '<div style="font-size:0.6rem;text-transform:uppercase;letter-spacing:2px;'
    'color:#94A3B8;font-weight:700;margin:1.1rem 0 0.4rem">ALERTAS POR SEMANA</div>',
    unsafe_allow_html=True,
)
fig_aw = go.Figure()
fig_aw.add_trace(go.Bar(
    x=all_w_sorted, y=_sp_red, name="Crítico",
    marker_color=C_RED, marker_opacity=0.85,
    hovertemplate="%{x}<br>Críticos: %{y}<extra></extra>",
))
fig_aw.add_trace(go.Bar(
    x=all_w_sorted, y=_sp_yel, name="Seguimiento",
    marker_color=C_YELLOW, marker_opacity=0.85,
    hovertemplate="%{x}<br>Seguimiento: %{y}<extra></extra>",
))
fig_aw.add_trace(go.Bar(
    x=all_w_sorted, y=_sp_grn, name="OK",
    marker_color=C_GREEN, marker_opacity=0.85,
    hovertemplate="%{x}<br>OK: %{y}<extra></extra>",
))

# Highlight selected week
if sel_week in all_w_sorted:
    fig_aw.add_vline(
        x=all_w_sorted.index(sel_week),
        line_dash="dot", line_color="#0F172A", line_width=1.5,
        annotation_text=f"◀ {sel_week}",
        annotation_position="top right",
        annotation_font=dict(size=9, color="#0F172A"),
    )

fig_aw.update_layout(
    barmode="stack",
    height=160,
    margin=dict(l=0, r=0, t=5, b=5),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    showlegend=True,
    legend=dict(orientation="h", x=1, y=1.02, xanchor="right",
                font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
    xaxis=dict(showgrid=False, tickangle=-35, tickfont=dict(size=9), zeroline=False),
    yaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickfont=dict(size=9), zeroline=False),
    hovermode="x unified",
    bargap=0.15,
)
st.plotly_chart(fig_aw, use_container_width=True, key="aw_stacked")
st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

# ── PARETO DE CARTERA ─────────────────────────────────────────────────────────
cartera_json = st.session_state.get("_cartera_raw")
df_pareto_brands: pd.DataFrame = pd.DataFrame()
pareto_brand_ids: list[str] = []

if cartera_json:
    try:
        df_cart = pd.read_json(io.StringIO(cartera_json))
        df_cart.columns = [str(c).strip() for c in df_cart.columns]
        _cm = {c.upper(): c for c in df_cart.columns}
        gmv_col  = _cm.get("GMV_L28D")
        name_col = _cm.get("BRAND_NAME") or _cm.get("COUNTRY_BRAND_ID")
        email_col = next((c for c in df_cart.columns if "EMAIL_NUEVO" in c.upper()), None)

        if gmv_col and name_col:
            df_cart[gmv_col] = pd.to_numeric(df_cart[gmv_col], errors="coerce").fillna(0)
            if not is_supervisor and email_col:
                df_cart = df_cart[df_cart[email_col].str.lower() == email.strip().lower()]
            elif sel_farmers and email_col:
                df_cart = df_cart[df_cart[email_col].isin(sel_farmers)]
            df_cart = df_cart[df_cart[gmv_col] > 0].sort_values(gmv_col, ascending=False).reset_index(drop=True)
            total_gmv = df_cart[gmv_col].sum()
            if total_gmv > 0:
                df_cart["_cum_pct"] = df_cart[gmv_col].cumsum() / total_gmv * 100
                n_p = max(20, int((df_cart["_cum_pct"] <= 80).sum()) + 1)
                n_p = min(30, n_p, len(df_cart))
                df_pareto_brands = df_cart.head(n_p).copy()
                pareto_brand_ids = df_pareto_brands[name_col].astype(str).tolist()
    except Exception:
        pass

# ── TABS ──────────────────────────────────────────────────────────────────────
tab_pareto, tab_ranking, tab_evol, tab_heat = st.tabs([
    "🏆 Pareto de Cartera",
    "📊 Ranking del equipo",
    "📈 Evolución histórica",
    "🗺️ Heatmap de alertas",
])

# ── Pareto ────────────────────────────────────────────────────────────────────
with tab_pareto:
    if df_pareto_brands.empty:
        if not cartera_json:
            st.info("💡 Cargá la Asignación/Cartera en **Carga de Datos** para ver el Pareto por GMV.")
        else:
            st.info("Sin datos suficientes. Verificá columnas GMV_L28D y BRAND_NAME en la Asignación.")
    else:
        _cm2 = {c.upper(): c for c in df_pareto_brands.columns}
        gc2  = _cm2.get("GMV_L28D")
        nc2  = _cm2.get("BRAND_NAME") or _cm2.get("COUNTRY_BRAND_ID")
        total_g2 = df_pareto_brands[gc2].sum()
        n_pb = len(df_pareto_brands)

        st.markdown(f"""
        <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:10px;
                    padding:0.85rem 1.2rem;margin-bottom:0.8rem;display:flex;
                    justify-content:space-between;align-items:center;box-shadow:0 1px 2px rgba(15,23,42,0.05)">
            <div>
                <div style="font-weight:700;font-size:0.95rem;color:#0F172A">Top {n_pb} Brands por GMV</div>
                <div style="font-size:0.76rem;color:#64748B;margin-top:2px">
                    GMV L28D total: <b>${total_g2:,.0f}</b> — enfocate en estas marcas
                </div>
            </div>
            <div style="text-align:right">
                <div style="font-size:1.6rem;font-weight:800;color:#FF441B">{n_pb}</div>
                <div style="font-size:0.68rem;color:#94A3B8">brands · Pareto 80%</div>
            </div>
        </div>""", unsafe_allow_html=True)

        fig_p = go.Figure()
        fig_p.add_trace(go.Bar(
            x=df_pareto_brands[nc2].astype(str), y=df_pareto_brands[gc2],
            marker_color=C_RAPPI, marker_opacity=0.82, name="GMV L28D",
            hovertemplate="<b>%{x}</b><br>GMV: $%{y:,.0f}<extra></extra>",
        ))
        fig_p.add_trace(go.Scatter(
            x=df_pareto_brands[nc2].astype(str), y=df_pareto_brands["_cum_pct"],
            mode="lines+markers", name="% Acumulado", yaxis="y2",
            line=dict(color="#3B82F6", width=2),
            marker=dict(size=5, color="#3B82F6"),
        ))
        fig_p.add_hline(y=80, line_dash="dash", line_color="#94A3B8", line_width=1,
                        yref="y2", annotation_text="80%", annotation_font_size=9)
        fig_p.update_layout(
            height=330, margin=dict(l=0, r=60, t=10, b=65),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickformat="$,.0f"),
            yaxis2=dict(overlaying="y", side="right", range=[0,105], ticksuffix="%", showgrid=False),
            xaxis=dict(showgrid=False, tickangle=-45, tickfont_size=9),
            legend=dict(orientation="h", y=1.04, x=0, font_size=11),
            hovermode="x unified",
        )
        st.plotly_chart(fig_p, use_container_width=True, key="pareto_chart")

        # Per-metric bars for pareto brands
        if not brand_df.empty and pareto_brand_ids:
            st.markdown('<div class="rb-section-title">Pareto brands — métricas esta semana</div>', unsafe_allow_html=True)
            pb_df = brand_df[brand_df["brand"].isin(pareto_brand_ids) & (brand_df["week"] == sel_week)]
            if sel_country != "Todos":
                pb_df = pb_df[pb_df["country"] == sel_country]
            if not pb_df.empty:
                for metric in sel_metrics[:3]:
                    mdf = pb_df[pb_df["metric"] == metric].sort_values("value", ascending=False).head(20)
                    if mdf.empty:
                        continue
                    mdf = mdf.copy()
                    mdf["color"] = mdf["vs_lw"].apply(_sema_color)
                    mdf["label"] = mdf["vs_lw"].apply(_fmt_pct)
                    avg_v = mdf["value"].mean()
                    fig_b = go.Figure(go.Bar(
                        x=mdf["brand"], y=mdf["value"],
                        marker_color=mdf["color"], text=mdf["label"], textposition="outside",
                        hovertemplate="<b>%{x}</b><br>" + metric + ": %{y:,.2f}<br>vs LW: %{text}<extra></extra>",
                    ))
                    fig_b.add_hline(y=avg_v, line_dash="dash", line_color="#94A3B8", line_width=1.2,
                                   annotation_text=f"Prom. {_fmt_val(metric, avg_v)}",
                                   annotation_position="right", annotation_font_size=9)
                    fig_b.update_layout(
                        height=215, margin=dict(l=0, r=80, t=20, b=50),
                        title=dict(text=metric, font=dict(size=12, color="#0F172A"), x=0),
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        showlegend=False,
                        xaxis=dict(showgrid=False, tickangle=-38, tickfont_size=9),
                        yaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
                    )
                    st.plotly_chart(fig_b, use_container_width=True, key=f"pb_m_{metric}")

# ── Ranking ───────────────────────────────────────────────────────────────────
with tab_ranking:
    if week_df.empty:
        st.info("Sin datos para los filtros seleccionados.")
    else:
        all_e = sorted(e for e in week_df["farmer"].unique() if e not in ("Total","nan",""))
        for metric in sel_metrics:
            mdata = week_df[(week_df["metric"] == metric) & (week_df["farmer"].isin(all_e))].copy()
            if mdata.empty:
                continue
            mdata["_name"] = mdata["farmer"].apply(_name)
            mdata["color"] = mdata["vs_lw"].apply(_sema_color)
            mdata["label"] = mdata["vs_lw"].apply(_fmt_pct)
            mdata = mdata.sort_values("value", ascending=False)
            avg_v = mdata["value"].mean()
            n_red_m = int((mdata["vs_lw"].dropna() <= ALARM_RED).sum())

            st.markdown(
                f"<div style='font-size:0.74rem;color:#64748B;margin:0.8rem 0 0.15rem'>"
                f"<b>{metric}</b> · {len(mdata)} farmers"
                + (f" · <span style='color:{C_RED};font-weight:600'>{n_red_m} críticos</span>" if n_red_m else "")
                + "</div>",
                unsafe_allow_html=True,
            )
            fig_r = go.Figure(go.Bar(
                x=mdata["_name"], y=mdata["value"],
                marker_color=mdata["color"], text=mdata["label"], textposition="outside",
                hovertemplate="<b>%{x}</b><br>" + metric + ": %{y:,.2f}<br>vs LW: %{text}<extra></extra>",
            ))
            fig_r.add_hline(y=avg_v, line_dash="dash", line_color="#94A3B8", line_width=1.2,
                           annotation_text=f"Prom. {_fmt_val(metric, avg_v)}",
                           annotation_position="right", annotation_font_size=9)
            fig_r.update_layout(
                height=230, margin=dict(l=0, r=85, t=5, b=40),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                xaxis=dict(showgrid=False, tickangle=-28, tickfont_size=11),
                yaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
            )
            st.plotly_chart(fig_r, use_container_width=True, key=f"rank_{metric}")

# ── Evolución histórica ───────────────────────────────────────────────────────
with tab_evol:
    col_em, col_ef = st.columns([1, 2])
    with col_em:
        evol_metric = st.selectbox("Métrica", sel_metrics or all_metrics[:1], key="evol_m")
    with col_ef:
        evol_farmers = st.multiselect(
            "Farmers", all_farmers_emails,
            default=(sel_farmers or all_farmers_emails[:6]),
            format_func=_name, key="evol_f",
        )
    show_pct_t = st.toggle("Mostrar % vs LW", key="evol_pct")
    show_avg_t = st.toggle("Mostrar promedio equipo", value=True, key="evol_avg")

    if evol_metric and evol_farmers:
        evol_df = farmer_df[(farmer_df["metric"] == evol_metric) & (farmer_df["farmer"].isin(evol_farmers))].copy()
        if sel_country != "Todos":
            evol_df = evol_df[evol_df["country"] == sel_country]
        evol_df = evol_df.sort_values("week")
        y_col = "vs_lw" if show_pct_t else "value"

        if not evol_df.empty:
            # Trend summary
            if len(all_weeks) >= 2:
                prev_w = all_weeks[1] if len(all_weeks) > 1 else all_weeks[0]
                base_df = farmer_df if sel_country == "Todos" else farmer_df[farmer_df["country"] == sel_country]
                cur_a = base_df[(base_df["metric"] == evol_metric) & (base_df["week"] == sel_week)]["value"].mean()
                prv_a = base_df[(base_df["metric"] == evol_metric) & (base_df["week"] == prev_w)]["value"].mean()
                if not pd.isna(cur_a) and not pd.isna(prv_a) and prv_a != 0:
                    delta = (cur_a - prv_a) / abs(prv_a) * 100
                    dc = C_GREEN if delta > 0 else C_RED
                    st.markdown(
                        f"<div style='font-size:0.78rem;color:#374151;margin-bottom:0.4rem'>"
                        f"Promedio equipo en <b>{evol_metric}</b>: "
                        f"<span style='color:{dc};font-weight:700'>{'↑' if delta>0 else '↓'}{abs(delta):.1f}%</span>"
                        f" vs semana anterior ({_fmt_val(evol_metric, prv_a)} → {_fmt_val(evol_metric, cur_a)})</div>",
                        unsafe_allow_html=True,
                    )

            fig_e = go.Figure()
            if show_pct_t:
                fig_e.add_hline(y=0, line_dash="solid", line_color="#CBD5E1", line_width=1)
                fig_e.add_hline(y=ALARM_RED*100, line_dash="dash", line_color=C_RED, line_width=1,
                               annotation_text="-10%", annotation_position="right", annotation_font_size=9)
                fig_e.add_hline(y=ALARM_YELLOW*100, line_dash="dash", line_color=C_YELLOW, line_width=1,
                               annotation_text="-5%", annotation_position="right", annotation_font_size=9)

            if show_avg_t:
                base2 = farmer_df if sel_country == "Todos" else farmer_df[farmer_df["country"] == sel_country]
                avg_w = base2[base2["metric"] == evol_metric].groupby("week")[y_col].mean().reset_index().sort_values("week")
                y_a = avg_w[y_col] * 100 if show_pct_t else avg_w[y_col]
                fig_e.add_trace(go.Scatter(
                    x=avg_w["week"], y=y_a, mode="lines", name="Prom. equipo",
                    line=dict(width=2, dash="dot", color="#94A3B8"),
                ))

            for idx, femail in enumerate(evol_farmers):
                fd = evol_df[evol_df["farmer"] == femail].sort_values("week")
                if fd.empty:
                    continue
                y_v = fd[y_col] * 100 if show_pct_t else fd[y_col]
                fig_e.add_trace(go.Scatter(
                    x=fd["week"], y=y_v, mode="lines+markers", name=_name(femail),
                    line=dict(width=2, color=_PALETTE[idx % len(_PALETTE)]),
                    marker=dict(size=6, color=[_sema_color(v) for v in fd["vs_lw"]],
                                line=dict(width=1.2, color="white")),
                ))

            fig_e.update_layout(
                height=390, margin=dict(l=0, r=55, t=10, b=15),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickangle=-28),
                yaxis=dict(showgrid=True, gridcolor="#F1F5F9",
                           tickformat="+.1f%" if show_pct_t else ",.1f"),
                legend=dict(orientation="h", y=-0.18, x=0, font_size=11),
                hovermode="x unified",
            )
            st.plotly_chart(fig_e, use_container_width=True, key="evol_fig")

# ── Heatmap ───────────────────────────────────────────────────────────────────
with tab_heat:
    if week_df.empty:
        st.info("Sin datos para el heatmap.")
    else:
        all_e_h = sorted(e for e in week_df["farmer"].unique() if e not in ("Total","nan",""))
        z_vals, text_vals, y_labels = [], [], [_name(e) for e in all_e_h]

        for femail in all_e_h:
            frow = week_df[week_df["farmer"] == femail]
            z_row, t_row = [], []
            for m in sel_metrics:
                mr = frow[frow["metric"] == m]
                if mr.empty:
                    z_row.append(-1); t_row.append("S/D"); continue
                vs = mr.iloc[0]["vs_lw"]
                if vs is None or pd.isna(vs):
                    z_row.append(-1); t_row.append("S/D"); continue
                try:
                    v = float(vs)
                    z_row.append(0 if v <= ALARM_RED else 1 if v <= ALARM_YELLOW else 2)
                    t_row.append(f"{v*100:+.1f}%")
                except (TypeError, ValueError):
                    z_row.append(-1); t_row.append("?")
            z_vals.append(z_row)
            text_vals.append(t_row)

        cs = [
            [0.000,"#CBD5E1"],[0.166,"#CBD5E1"],
            [0.167,"#FCA5A5"],[0.499,"#FCA5A5"],
            [0.500,"#FDE68A"],[0.832,"#FDE68A"],
            [0.833,"#86EFAC"],[1.000,"#86EFAC"],
        ]
        fig_h = go.Figure(go.Heatmap(
            z=z_vals, x=sel_metrics, y=y_labels,
            text=text_vals, texttemplate="%{text}",
            textfont=dict(size=11, color="#0F172A"),
            colorscale=cs, showscale=False,
            hovertemplate="%{y} | %{x}: %{text}<extra></extra>",
            zmin=-1, zmax=2,
        ))
        fig_h.update_layout(
            height=max(280, len(y_labels)*33),
            margin=dict(l=10, r=10, t=10, b=10),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(side="top"),
        )
        st.plotly_chart(fig_h, use_container_width=True, key="heat_fig")
        st.caption("🟢 Mejora >5% · 🟡 Caída 5-10% · 🔴 Caída >10% · ⬜ Sin datos")
