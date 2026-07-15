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
        sel_metrics = st.multiselect(
            "Métricas", all_metrics,
            default=all_metrics,
            key="sp_metrics",
        )
    with fcol4:
        _TOTAL_PAIS = "__total_pais__"
        _farmer_opts = [_TOTAL_PAIS] + list(all_farmers_emails)
        def _name_ext(e):
            return "🌎 Total País" if e == _TOTAL_PAIS else _name(e)
        sel_farmers_raw = st.multiselect("Farmers", _farmer_opts,
                                          format_func=_name_ext, key="sp_farmers")
        _show_total_only = _TOTAL_PAIS in sel_farmers_raw
        sel_farmers = [f for f in sel_farmers_raw if f != _TOTAL_PAIS]

if not sel_metrics:
    sel_metrics = all_metrics


def _apply_f(df: pd.DataFrame, week: str | None = None) -> pd.DataFrame:
    out = df.copy()
    if week:
        out = out[out["week"] == week]
    if sel_country != "Todos":
        out = out[out["country"] == sel_country]
    # When "Total País" is the only selection, don't filter by farmer
    if sel_farmers and not _show_total_only:
        out = out[out["farmer"].isin(sel_farmers)]
    if sel_metrics:
        out = out[out["metric"].isin(sel_metrics)]
    return out


week_df = _apply_f(farmer_df, sel_week)

# ── Build time-series base (all weeks, all metrics) ──────────────────────────
_ts_df_team = farmer_df[farmer_df["brand"] == "Total"].copy()
_ts_df_team = _ts_df_team[~_ts_df_team["farmer"].isin(["Total", "nan", ""])]
if sel_country != "Todos":
    _ts_df_team = _ts_df_team[_ts_df_team["country"] == sel_country]

# Filtered view for selected farmers (lines + Caídas Graves)
_ts_df = _ts_df_team.copy()
if sel_farmers:
    _ts_df = _ts_df[_ts_df["farmer"].isin(sel_farmers)]

_ts_farmers  = sorted(_ts_df["farmer"].unique())
_ts_weeks    = sorted(_ts_df["week"].unique())        # chronological
_ts_metrics  = sorted(_ts_df["metric"].unique())      # ALL metrics in the base

# ── REVIEW GENERAL header ─────────────────────────────────────────────────────
st.markdown(
    '<div style="text-align:center;margin:1rem 0 1.2rem">'
    '<span style="font-size:0.68rem;text-transform:uppercase;letter-spacing:3px;'
    'font-weight:800;color:#1E293B;border-bottom:2.5px solid #FF441B;'
    'padding-bottom:4px">&#8226; REVIEW GENERAL</span></div>',
    unsafe_allow_html=True,
)

if _ts_df.empty or not _ts_metrics:
    st.info("Sin datos. Cargá el archivo Metrics Weekly para ver las gráficas.")
else:
    for _chunk_start in range(0, len(_ts_metrics), 3):
        _chunk = _ts_metrics[_chunk_start : _chunk_start + 3]
        _cols  = st.columns(3)

        for _col, _metric in zip(_cols, _chunk):
            with _col:
                st.markdown(
                    f'<div style="background:#FF441B;border-radius:8px 8px 0 0;'
                    f'padding:7px 12px;font-size:0.62rem;text-transform:uppercase;'
                    f'letter-spacing:1.5px;color:#fff;font-weight:800">'
                    f'{_metric}</div>',
                    unsafe_allow_html=True,
                )
                _mdf = _ts_df[_ts_df["metric"] == _metric]
                if _mdf.empty:
                    st.markdown(
                        '<div style="background:#fff;border:1px solid #E2E8F0;'
                        'border-radius:0 0 8px 8px;padding:1.5rem;text-align:center;'
                        'color:#94A3B8;font-size:0.78rem">Sin datos</div>',
                        unsafe_allow_html=True,
                    )
                    continue

                _fig = go.Figure()
                _show_farmer_detail = (len(sel_farmers) == 1 and not _show_total_only)

                # Individual farmer lines (skipped when "Total País" is selected)
                if not _show_total_only:
                    for _idx, _fe in enumerate(_ts_farmers):
                        _fd = _mdf[_mdf["farmer"] == _fe].sort_values("week").reset_index(drop=True)
                        if _fd.empty:
                            continue
                        _clr = _PALETTE[_idx % len(_PALETTE)]
                        _fig.add_trace(go.Scatter(
                            x=_fd["week"],
                            y=_fd["value"],
                            mode="lines+markers+text" if _show_farmer_detail else "lines+markers",
                            name=_name(_fe),
                            line=dict(color=_clr, width=2.5 if _show_farmer_detail else 1.5),
                            marker=dict(size=6 if _show_farmer_detail else 4),
                            text=[f"{v:,.2f}" for v in _fd["value"]] if _show_farmer_detail else None,
                            textposition="top center",
                            textfont=dict(size=9, color=_clr),
                            hovertemplate=(
                                f"<b>{_name(_fe)}</b><br>%{{x}}<br>"
                                f"{_metric}: %{{y:,.2f}}<extra></extra>"
                            ),
                        ))

                        # Alarm markers for individual farmer (same thresholds as Total País)
                        if _show_farmer_detail and len(_fd) >= 2:
                            _fa_x_r, _fa_y_r, _fa_t_r = [], [], []
                            _fa_x_y, _fa_y_y, _fa_t_y = [], [], []
                            for _i in range(1, len(_fd)):
                                _vp = _fd.loc[_i - 1, "value"]
                                _vc = _fd.loc[_i,     "value"]
                                if _vp and _vp != 0:
                                    _chg = (_vc - _vp) / abs(_vp)
                                    _lbl = f"▼ {_chg:.1%}"
                                    if _chg <= ALARM_RED:
                                        _fa_x_r.append(_fd.loc[_i, "week"]); _fa_y_r.append(_vc); _fa_t_r.append(_lbl)
                                    elif _chg <= ALARM_YELLOW:
                                        _fa_x_y.append(_fd.loc[_i, "week"]); _fa_y_y.append(_vc); _fa_t_y.append(_lbl)
                            if _fa_x_r:
                                _fig.add_trace(go.Scatter(
                                    x=_fa_x_r, y=_fa_y_r, mode="markers+text",
                                    name="⚠️ Caída grave (≥10%)",
                                    marker=dict(symbol="triangle-down", size=14, color="#EF4444",
                                                line=dict(color="#fff", width=1.5)),
                                    text=_fa_t_r, textposition="bottom center",
                                    textfont=dict(size=9, color="#EF4444"),
                                    hovertemplate="<b>Caída grave</b><br>%{x}<br>%{text}<extra></extra>",
                                    showlegend=True,
                                ))
                            if _fa_x_y:
                                _fig.add_trace(go.Scatter(
                                    x=_fa_x_y, y=_fa_y_y, mode="markers+text",
                                    name="⚠️ Caída moderada (≥5%)",
                                    marker=dict(symbol="triangle-down", size=11, color="#D97706",
                                                line=dict(color="#fff", width=1.5)),
                                    text=_fa_t_y, textposition="bottom center",
                                    textfont=dict(size=9, color="#D97706"),
                                    hovertemplate="<b>Caída moderada</b><br>%{x}<br>%{text}<extra></extra>",
                                    showlegend=True,
                                ))

                # Country aggregate — always shown; thicker + labeled "Total País" when solo
                _avg_w = (
                    _ts_df_team[_ts_df_team["metric"] == _metric]
                    .groupby("week")["value"].mean()
                    .reset_index()
                    .sort_values("week")
                    .reset_index(drop=True)
                )
                _avg_label = "🌎 Total País" if _show_total_only else "Prom. equipo"
                _avg_width  = 3 if _show_total_only else 2.5
                _fig.add_trace(go.Scatter(
                    x=_avg_w["week"],
                    y=_avg_w["value"],
                    mode="lines+markers+text" if _show_total_only else "lines",
                    name=_avg_label,
                    line=dict(color=C_RAPPI if _show_total_only else "#1E293B",
                              width=_avg_width,
                              dash="solid" if _show_total_only else "dash"),
                    marker=dict(size=6) if _show_total_only else {},
                    text=[f"{v:,.2f}" for v in _avg_w["value"]] if _show_total_only else None,
                    textposition="top center",
                    textfont=dict(size=9, color=C_RAPPI),
                    hovertemplate=(
                        f"<b>{_avg_label}</b><br>%{{x}}<br>"
                        f"{_metric}: %{{y:,.2f}}<extra></extra>"
                    ),
                ))

                # Alarm markers on Total País line — week-over-week drops
                if _show_total_only and len(_avg_w) >= 2:
                    _alarm_x_red, _alarm_y_red, _alarm_txt_red   = [], [], []
                    _alarm_x_yel, _alarm_y_yel, _alarm_txt_yel   = [], [], []
                    for _i in range(1, len(_avg_w)):
                        _v_prev = _avg_w.loc[_i - 1, "value"]
                        _v_curr = _avg_w.loc[_i,     "value"]
                        if _v_prev and _v_prev != 0:
                            _chg = (_v_curr - _v_prev) / abs(_v_prev)
                            _lbl = f"▼ {_chg:.1%}"
                            if _chg <= ALARM_RED:
                                _alarm_x_red.append(_avg_w.loc[_i, "week"])
                                _alarm_y_red.append(_v_curr)
                                _alarm_txt_red.append(_lbl)
                            elif _chg <= ALARM_YELLOW:
                                _alarm_x_yel.append(_avg_w.loc[_i, "week"])
                                _alarm_y_yel.append(_v_curr)
                                _alarm_txt_yel.append(_lbl)
                    if _alarm_x_red:
                        _fig.add_trace(go.Scatter(
                            x=_alarm_x_red, y=_alarm_y_red,
                            mode="markers+text",
                            name="⚠️ Caída grave (≥10%)",
                            marker=dict(symbol="triangle-down", size=14,
                                        color="#EF4444", line=dict(color="#fff", width=1.5)),
                            text=_alarm_txt_red,
                            textposition="bottom center",
                            textfont=dict(size=9, color="#EF4444"),
                            hovertemplate="<b>Caída grave</b><br>%{x}<br>%{text}<extra></extra>",
                            showlegend=True,
                        ))
                    if _alarm_x_yel:
                        _fig.add_trace(go.Scatter(
                            x=_alarm_x_yel, y=_alarm_y_yel,
                            mode="markers+text",
                            name="⚠️ Caída moderada (≥5%)",
                            marker=dict(symbol="triangle-down", size=11,
                                        color="#D97706", line=dict(color="#fff", width=1.5)),
                            text=_alarm_txt_yel,
                            textposition="bottom center",
                            textfont=dict(size=9, color="#D97706"),
                            hovertemplate="<b>Caída moderada</b><br>%{x}<br>%{text}<extra></extra>",
                            showlegend=True,
                        ))

                # Highlight the selected week
                if sel_week in _ts_weeks:
                    _fig.add_vline(
                        x=sel_week,
                        line_dash="dot",
                        line_color=C_RAPPI,
                        line_width=1.5,
                        annotation_text=f"Sem. {sel_week}",
                        annotation_font=dict(size=8, color=C_RAPPI),
                        annotation_position="top left",
                    )

                _fig.update_layout(
                    height=280,
                    margin=dict(l=0, r=10, t=12, b=55),
                    plot_bgcolor="#FFFFFF",
                    paper_bgcolor="#FFFFFF",
                    showlegend=True,
                    legend=dict(
                        orientation="h", y=-0.32, x=0,
                        font=dict(size=8), bgcolor="rgba(0,0,0,0)",
                    ),
                    xaxis=dict(
                        showgrid=False,
                        tickangle=-45,
                        tickfont=dict(size=8, color="#64748B"),
                        zeroline=False,
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor="#F1F5F9",
                        tickfont=dict(size=8, color="#64748B"),
                        zeroline=False,
                    ),
                    hovermode="x unified",
                )
                st.plotly_chart(
                    _fig,
                    use_container_width=True,
                    key=f"ts_{_chunk_start}_{_metric}",
                    config={"displayModeBar": False},
                )

        # Pad remaining columns in last row if chunk < 3
        for _empty_col in _cols[len(_chunk):]:
            with _empty_col:
                st.empty()

# ── CAÍDAS GRAVES — semana anterior inmediata ─────────────────────────────────
# Siempre compara las dos últimas semanas disponibles en el dataset filtrado.
_all_weeks_sorted = sorted(_ts_df["week"].unique())
if len(_all_weeks_sorted) >= 2:
    _w_curr = _all_weeks_sorted[-1]   # semana más reciente
    _w_prev = _all_weeks_sorted[-2]   # inmediatamente anterior

    _curr_df = _ts_df[_ts_df["week"] == _w_curr]
    _prev_df = _ts_df[_ts_df["week"] == _w_prev]

    # Cruzar por (farmer, metric): buscar vs_lw en la semana actual
    # vs_lw ya es el delta vs semana anterior, así que lo usamos directamente.
    _drops = []
    for _fe in _ts_farmers:
        for _m in _ts_metrics:
            _row = _curr_df[(_curr_df["farmer"] == _fe) & (_curr_df["metric"] == _m)]
            if _row.empty:
                continue
            _vs = _row.iloc[0]["vs_lw"]
            _val = _row.iloc[0]["value"]
            try:
                _vs_f = float(_vs)
            except (TypeError, ValueError):
                continue
            if _vs_f <= ALARM_RED:
                # Valor previo para contexto
                _prev_row = _prev_df[(_prev_df["farmer"] == _fe) & (_prev_df["metric"] == _m)]
                _val_prev = _prev_row.iloc[0]["value"] if not _prev_row.empty else None
                _drops.append({
                    "farmer":   _fe,
                    "metric":   _m,
                    "vs_lw":    _vs_f,
                    "value":    _val,
                    "val_prev": _val_prev,
                })

    st.markdown('<div style="height:1.5rem"></div>', unsafe_allow_html=True)
    st.markdown(
        f'<div style="text-align:center;margin:0.5rem 0 1.2rem">'
        f'<span style="font-size:0.68rem;text-transform:uppercase;letter-spacing:3px;'
        f'font-weight:800;color:#EF4444;border-bottom:2.5px solid #EF4444;'
        f'padding-bottom:4px">&#9660; CA&#205;DAS GRAVES &mdash; Sem. {_w_curr} vs Sem. {_w_prev}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if not _drops:
        st.markdown(
            '<div style="text-align:center;padding:1.5rem;color:#16A34A;font-size:0.9rem;font-weight:600">'
            '&#10003; Sin caídas graves (&le;-10%) en la última semana.'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        _drops_df = pd.DataFrame(_drops).sort_values("vs_lw")

        # ── Tabla resumen de caídas ────────────────────────────────────────────
        _drop_rows_html = ""
        for _, _dr in _drops_df.iterrows():
            _fname  = _name(_dr["farmer"])
            _pct    = f"{_dr['vs_lw']*100:+.1f}%"
            _val_s  = _fmt_val(_dr["metric"], _dr["value"])
            _prev_s = _fmt_val(_dr["metric"], _dr["val_prev"]) if _dr["val_prev"] is not None else "—"
            _severity = "#7F1D1D" if _dr["vs_lw"] <= -0.20 else "#991B1B"
            _bg = "#FEF2F2" if _dr["vs_lw"] <= -0.20 else "#FFF5F5"
            _drop_rows_html += (
                f'<div style="display:grid;grid-template-columns:2fr 1.6fr 1fr 1fr 1fr;'
                f'background:{_bg};border-bottom:1px solid #FEE2E2;align-items:center">'
                f'<div style="padding:7px 10px;font-size:0.78rem;font-weight:600;color:#0F172A">{_fname}</div>'
                f'<div style="padding:7px 8px;font-size:0.78rem;color:#374151">{_dr["metric"]}</div>'
                f'<div style="padding:7px 8px;font-size:0.82rem;font-weight:800;color:{_severity};text-align:right">{_pct}</div>'
                f'<div style="padding:7px 8px;font-size:0.78rem;color:#374151;text-align:right">{_prev_s}</div>'
                f'<div style="padding:7px 8px;font-size:0.78rem;font-weight:600;color:#0F172A;text-align:right">{_val_s}</div>'
                f'</div>'
            )

        _header_html = (
            '<div style="display:grid;grid-template-columns:2fr 1.6fr 1fr 1fr 1fr;'
            'background:#1E293B;border-radius:8px 8px 0 0">'
            '<div style="padding:7px 10px;font-size:0.6rem;text-transform:uppercase;letter-spacing:1.5px;color:#fff;font-weight:700">Farmer</div>'
            '<div style="padding:7px 8px;font-size:0.6rem;text-transform:uppercase;letter-spacing:1.5px;color:#fff;font-weight:700">Métrica</div>'
            '<div style="padding:7px 8px;font-size:0.6rem;text-transform:uppercase;letter-spacing:1.5px;color:#FCA5A5;font-weight:700;text-align:right">vs LW</div>'
            '<div style="padding:7px 8px;font-size:0.6rem;text-transform:uppercase;letter-spacing:1.5px;color:#94A3B8;font-weight:700;text-align:right">Sem. anterior</div>'
            '<div style="padding:7px 8px;font-size:0.6rem;text-transform:uppercase;letter-spacing:1.5px;color:#fff;font-weight:700;text-align:right">Sem. actual</div>'
            '</div>'
        )

        st.markdown(
            f'<div style="border-radius:8px;overflow:hidden;border:1px solid #FEE2E2;'
            f'box-shadow:0 1px 4px rgba(239,68,68,0.12)">'
            f'{_header_html}{_drop_rows_html}</div>',
            unsafe_allow_html=True,
        )

        # ── Heatmap de caídas: farmer × métrica ───────────────────────────────
        st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
        _pivot = _drops_df.pivot_table(
            index="farmer", columns="metric", values="vs_lw", aggfunc="min"
        )
        _pivot.index = [_name(e) for e in _pivot.index]
        _z = _pivot.values.tolist()
        _text = [
            [f"{v*100:+.1f}%" if v is not None and not pd.isna(v) else "" for v in row]
            for row in _z
        ]
        _fig_heat = go.Figure(go.Heatmap(
            z=_z,
            x=list(_pivot.columns),
            y=list(_pivot.index),
            text=_text,
            texttemplate="%{text}",
            textfont=dict(size=11, color="#fff"),
            colorscale=[
                [0.0,  "#7F1D1D"],
                [0.35, "#DC2626"],
                [0.7,  "#F87171"],
                [1.0,  "#FECACA"],
            ],
            showscale=False,
            zmin=min(_drops_df["vs_lw"].min(), -0.30),
            zmax=ALARM_RED,
            hovertemplate="%{y} · %{x}: %{text}<extra></extra>",
        ))
        _fig_heat.update_layout(
            height=max(180, len(_pivot) * 36 + 60),
            margin=dict(l=0, r=0, t=8, b=8),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(side="top", tickfont=dict(size=10), showgrid=False),
            yaxis=dict(tickfont=dict(size=10), showgrid=False),
        )
        st.plotly_chart(_fig_heat, use_container_width=True, key="drops_heat",
                        config={"displayModeBar": False})
