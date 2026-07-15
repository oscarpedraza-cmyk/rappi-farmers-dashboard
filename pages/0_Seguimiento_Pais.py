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
    st.markdown("""
    <div class="rb-empty-state">
        <div class="rb-empty-icon">📊</div>
        <h3>Sin métricas semanales</h3>
        <p>Cargá el archivo <b>Metrics Weekly</b> usando el expander de arriba para comenzar el análisis.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── GLOBAL FILTERS ────────────────────────────────────────────────────────────
all_weeks   = sorted(farmer_df["week"].unique(), reverse=True)
all_metrics = sorted(farmer_df["metric"].unique())
all_countries = [c for c in sorted(farmer_df["country"].unique()) if c in ("AR", "UY")]
all_farmers_emails = sorted(e for e in farmer_df["farmer"].unique() if e not in ("Total", "nan", ""))

with st.container():
    fcol1, fcol2, fcol3, fcol4 = st.columns([1, 2, 3, 3])
    with fcol1:
        sel_country = st.radio("País", ["Todos"] + all_countries, key="sp_country", horizontal=True)
    with fcol2:
        # Guard: if the persisted key is no longer in all_weeks, reset it
        _prev_week = st.session_state.get("sp_week")
        _default_week_idx = 0 if _prev_week not in all_weeks else all_weeks.index(_prev_week)
        sel_week = st.selectbox("Semana", all_weeks, index=_default_week_idx, key="sp_week",
                                format_func=lambda w: f"Sem. {w}")
    with fcol3:
        _default_metrics = [m for m in ["Orders","GMV","CVR (%)","Revenue"] if m in all_metrics] or all_metrics[:4]
        sel_metrics = st.multiselect(
            "Métricas", all_metrics,
            default=_default_metrics,
            key="sp_metrics",
        )
    with fcol4:
        sel_farmers = st.multiselect("Farmers", all_farmers_emails,
                                      format_func=_name, key="sp_farmers")

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

# ─────────────────────────────────────────────────────────────────────────────
# Helper: build one HTML summary table (farmers or brands)
# ─────────────────────────────────────────────────────────────────────────────
def _summary_table_html(
    rows_data: list[dict],          # [{label, metric1_val, metric1_vs, ...}, ...]
    metrics: list[str],
    title: str,
    title_color: str = "#FF441B",
) -> str:
    COL_W_LABEL = "2fr"
    COL_W_METRIC = " ".join(["1fr 0.9fr"] * len(metrics))
    GRID = f"{COL_W_LABEL} {COL_W_METRIC}"

    def _vs_pill(vs_raw: object) -> str:
        try:
            v = float(vs_raw)
            color = C_RED if v <= ALARM_RED else C_YELLOW if v <= ALARM_YELLOW else (C_GREEN if v > 0 else C_MUTED)
            bg = (
                "rgba(239,68,68,0.1)" if v <= ALARM_RED else
                "rgba(217,119,6,0.1)" if v <= ALARM_YELLOW else
                ("rgba(22,163,74,0.1)" if v > 0 else "rgba(100,116,139,0.08)")
            )
            return (
                f'<span style="font-size:0.78rem;font-weight:800;color:{color};'
                f'background:{bg};padding:2px 5px;border-radius:4px;white-space:nowrap">'
                f'{v*100:+.1f}%</span>'
            )
        except (TypeError, ValueError):
            return '<span style="color:#CBD5E1;font-size:0.78rem">—</span>'

    # Header
    header_cells = (
        f'<div style="padding:6px 8px;font-size:0.58rem;text-transform:uppercase;'
        f'letter-spacing:1.5px;color:#fff;font-weight:700">FARMER</div>'
    )
    for m in metrics:
        short = m.upper()[:10]
        header_cells += (
            f'<div style="padding:6px 4px;font-size:0.58rem;text-transform:uppercase;'
            f'letter-spacing:1px;color:#fff;font-weight:700;text-align:right">{short}</div>'
            f'<div style="padding:6px 4px;font-size:0.58rem;text-transform:uppercase;'
            f'letter-spacing:1px;color:rgba(255,255,255,0.7);font-weight:600;text-align:right">vs LW</div>'
        )

    rows_html = ""
    for i, row in enumerate(rows_data):
        bg = "#FFFFFF" if i % 2 == 0 else "#FFF8F6"
        cells = (
            f'<div style="padding:7px 8px;font-size:0.76rem;font-weight:600;color:#0F172A;'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{row["label"]}</div>'
        )
        for m in metrics:
            val_raw = row.get(f"{m}__val")
            vs_raw  = row.get(f"{m}__vs")
            val_str = _fmt_val(m, val_raw) if val_raw is not None else "—"
            cells += (
                f'<div style="padding:7px 4px;font-size:0.76rem;color:#0F172A;text-align:right">{val_str}</div>'
                + f'<div style="padding:7px 4px;text-align:right">{_vs_pill(vs_raw)}</div>'
            )
        rows_html += (
            f'<div style="display:grid;grid-template-columns:{GRID};background:{bg};'
            f'border-bottom:1px solid #F1F5F9">{cells}</div>'
        )

    # Total row — sum of values, average of vs_lw
    total_cells = (
        f'<div style="padding:8px 8px;font-size:0.76rem;font-weight:800;color:#0F172A;'
        f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
        f'border-top:2px solid #E2E8F0">TOTAL</div>'
    )
    for m in metrics:
        vals = [r.get(f"{m}__val") for r in rows_data if r.get(f"{m}__val") is not None]
        vss  = [r.get(f"{m}__vs")  for r in rows_data if r.get(f"{m}__vs")  is not None]
        total_val = sum(vals) if vals else None
        avg_vs    = sum(vss) / len(vss) if vss else None
        val_str   = _fmt_val(m, total_val) if total_val is not None else "—"
        total_cells += (
            f'<div style="padding:8px 4px;font-size:0.76rem;font-weight:800;color:#0F172A;'
            f'text-align:right;border-top:2px solid #E2E8F0">{val_str}</div>'
            + f'<div style="padding:8px 4px;text-align:right;border-top:2px solid #E2E8F0">{_vs_pill(avg_vs)}</div>'
        )

    return (
        f'<div style="border-radius:10px;overflow:hidden;border:1px solid #E2E8F0;'
        f'box-shadow:0 1px 4px rgba(15,23,42,0.06)">'
        # title bar
        f'<div style="background:{title_color};padding:8px 12px;font-size:0.65rem;'
        f'text-transform:uppercase;letter-spacing:2px;color:#fff;font-weight:800">{title}</div>'
        # header row
        f'<div style="display:grid;grid-template-columns:{GRID};background:#1E293B">'
        f'{header_cells}</div>'
        # data rows
        f'{rows_html}'
        # total row
        f'<div style="display:grid;grid-template-columns:{GRID};background:#F8FAFC">'
        f'{total_cells}</div>'
        f'</div>'
    )


# ── Build farmers table data ──────────────────────────────────────────────────
_farmers_tbl_data: list[dict] = []
_f_sub = week_df[week_df["brand"] == "Total"].copy()
_farmer_emails = sorted(e for e in _f_sub["farmer"].unique() if e not in ("Total", "nan", ""))

for _fe in _farmer_emails:
    _fd = _f_sub[_f_sub["farmer"] == _fe]
    row: dict = {"label": _name(_fe)}
    for _m in sel_metrics:
        _mr = _fd[_fd["metric"] == _m]
        row[f"{_m}__val"] = _mr.iloc[0]["value"]  if not _mr.empty else None
        row[f"{_m}__vs"]  = _mr.iloc[0]["vs_lw"]  if not _mr.empty else None
    _farmers_tbl_data.append(row)

# ── Build brands table data ───────────────────────────────────────────────────
_brands_tbl_data: list[dict] = []
if not brand_df.empty:
    _bd_filt = brand_df[brand_df["week"] == sel_week].copy()
    if sel_country != "Todos":
        _bd_filt = _bd_filt[_bd_filt["country"] == sel_country]
    if sel_farmers:
        _bd_filt = _bd_filt[_bd_filt["farmer"].isin(sel_farmers)]
    _brand_names = sorted(b for b in _bd_filt["brand"].unique() if b not in ("Total", "nan", ""))
    for _bn in _brand_names:
        _brow = _bd_filt[_bd_filt["brand"] == _bn]
        row2: dict = {"label": _bn}
        for _m in sel_metrics:
            _mr2 = _brow[_brow["metric"] == _m]
            row2[f"{_m}__val"] = _mr2.iloc[0]["value"]  if not _mr2.empty else None
            row2[f"{_m}__vs"]  = _mr2.iloc[0]["vs_lw"]  if not _mr2.empty else None
        _brands_tbl_data.append(row2)

# ── Render side-by-side tables ────────────────────────────────────────────────
_show_metrics_in_table = sel_metrics[:4]  # cap at 4 for readability
tcol_f, tcol_b = st.columns([6, 4])

with tcol_f:
    if _farmers_tbl_data:
        st.markdown(
            _summary_table_html(_farmers_tbl_data, _show_metrics_in_table, "FARMERS"),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="text-align:center;padding:2rem;color:#94A3B8;font-size:0.85rem">'
            'Sin datos de farmers para esta semana.</div>',
            unsafe_allow_html=True,
        )

with tcol_b:
    if _brands_tbl_data:
        st.markdown(
            _summary_table_html(_brands_tbl_data, _show_metrics_in_table, "BRANDS", title_color="#E05A00"),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="text-align:center;padding:2rem;color:#94A3B8;font-size:0.85rem">'
            'Sin datos de brands. Cargá el archivo Metrics Weekly para ver este panel.</div>',
            unsafe_allow_html=True,
        )

# ── REVIEW GENERAL ────────────────────────────────────────────────────────────
st.markdown('<div style="height:1.4rem"></div>', unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;margin:0.5rem 0 1.2rem">'
    '<span style="font-size:0.68rem;text-transform:uppercase;letter-spacing:3px;'
    'font-weight:800;color:#1E293B;border-bottom:2.5px solid #FF441B;'
    'padding-bottom:4px">&#8226; REVIEW GENERAL</span></div>',
    unsafe_allow_html=True,
)

# ── 3-column bar chart grid ───────────────────────────────────────────────────
_chart_farmers = _f_sub.copy()
_all_emails = sorted(e for e in _chart_farmers["farmer"].unique() if e not in ("Total","nan",""))

for _chunk_start in range(0, len(sel_metrics), 3):
    _chunk = sel_metrics[_chunk_start : _chunk_start + 3]
    _cols = st.columns(len(_chunk))
    for _col, _metric in zip(_cols, _chunk):
        with _col:
            # coral header box
            st.markdown(
                f'<div style="background:#FF441B;border-radius:8px 8px 0 0;'
                f'padding:7px 12px;font-size:0.62rem;text-transform:uppercase;'
                f'letter-spacing:1.5px;color:#fff;font-weight:800;margin-bottom:0">'
                f'{_metric}</div>',
                unsafe_allow_html=True,
            )
            _mdf = _chart_farmers[_chart_farmers["metric"] == _metric].copy()
            if _mdf.empty:
                st.markdown(
                    '<div style="background:#fff;border:1px solid #E2E8F0;border-radius:0 0 8px 8px;'
                    'padding:1.5rem;text-align:center;color:#94A3B8;font-size:0.78rem">'
                    'Sin datos</div>',
                    unsafe_allow_html=True,
                )
            else:
                _mdf["_label"] = _mdf["farmer"].apply(_name)
                _mdf["_color"] = _mdf["vs_lw"].apply(_sema_color)
                _mdf["_text"]  = _mdf["value"].apply(lambda v: _fmt_val(_metric, v))
                _mdf = _mdf.sort_values("value", ascending=False)
                _avg = _mdf["value"].mean()
                _fig = go.Figure(go.Bar(
                    x=_mdf["_label"],
                    y=_mdf["value"],
                    marker_color="rgba(255,68,27,0.75)",
                    text=_mdf["_text"],
                    textposition="outside",
                    textfont=dict(size=10, color="#0F172A"),
                    hovertemplate="<b>%{x}</b><br>" + _metric + ": %{text}<extra></extra>",
                ))
                _fig.add_hline(
                    y=_avg, line_dash="dash", line_color="#94A3B8", line_width=1.2,
                    annotation_text=f"prom {_fmt_val(_metric, _avg)}",
                    annotation_position="right", annotation_font=dict(size=8, color="#94A3B8"),
                )
                _fig.update_layout(
                    height=210,
                    margin=dict(l=0, r=55, t=18, b=40),
                    plot_bgcolor="#FFFFFF",
                    paper_bgcolor="#FFFFFF",
                    showlegend=False,
                    xaxis=dict(
                        showgrid=False, tickangle=-35,
                        tickfont=dict(size=9, color="#64748B"),
                        zeroline=False,
                    ),
                    yaxis=dict(
                        showgrid=True, gridcolor="#F1F5F9",
                        tickfont=dict(size=9, color="#64748B"),
                        zeroline=False,
                    ),
                )
                st.plotly_chart(
                    _fig, use_container_width=True,
                    key=f"rev_bar_{_metric}_{_chunk_start}",
                    config={"displayModeBar": False},
                )
