import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import get_history, get_available_dates, get_farmer_trend, get_consecutive_red_weeks
from core.loader import FARMER_NAMES, FARMERS_EMAILS
from core.metrics import COLOR_HEX, EMOJI
from core.auth import require_auth, render_topbar
from core.style import inject_global_css

st.set_page_config(page_title="Histórico — Rappi Farmers", page_icon="🚀", layout="wide")
st.markdown(inject_global_css(), unsafe_allow_html=True)
email, is_supervisor = require_auth()
render_topbar()


st.markdown("""
<div class="rb-page-header">
    <h1>📈 Histórico — Evolución en el tiempo</h1>
    <p>Tendencias semanales por farmer y por palanca. Guardar snapshot en página principal agrega puntos al histórico.</p>
</div>
""", unsafe_allow_html=True)

dates = get_available_dates()

if not dates:
    st.info("""
    **No hay datos históricos aún.**

    Para generar histórico:
    1. Carga el Sheet Maestro en la página principal
    2. Haz clic en **"💾 Guardar snapshot histórico"**
    3. Repite cada semana al enviar el reporte

    Después de al menos 2 corridas, verás las tendencias aquí.
    """)
    st.stop()

st.success(f"📅 {len(dates)} corridas disponibles — desde {dates[-1]} hasta {dates[0]}")

# ── Filtros ───────────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    all_farmers_in_db = list(set(
        snap["email"] for snap in get_history(weeks_back=20) if snap.get("email")
    ))
    farmer_names_in_db = {
        FARMER_NAMES.get(e, e.split("@")[0].replace(".", " ").title()): e
        for e in all_farmers_in_db
    }
    sorted_farmer_names = sorted(farmer_names_in_db.keys())

    mode = st.radio("Modo de vista", ["Por farmer", "Por métrica (equipo)"], horizontal=True)

with col2:
    metric_options = {
        "Churn ATT": ("ATT_Churn", "decimal"),
        "MD Total ATT": ("ATT_MD_Total", "decimal"),
        "MD Pro ATT": ("ATT_MD_Pro", "decimal"),
        "Ads Bookings ATT": ("ATT_Book", "decimal"),
        "Ads Revenue ATT": ("ATT_Rev_real", "decimal"),
        "Net Revenue Adj (pp)": ("Net_Rev_Adj", "pp"),
        "Pitch Integral": ("Pitch_Pct", "decimal"),
        "% No Contactados": ("pct_no_contactados", "pct_raw"),
    }
    selected_metrics = st.multiselect(
        "Métricas a visualizar",
        list(metric_options.keys()),
        default=["Churn ATT", "MD Total ATT", "Ads Revenue ATT"],
    )

if mode == "Por farmer":
    # ── Single farmer trend ───────────────────────────────────────────────────
    selected_name = st.selectbox("Farmer", sorted_farmer_names)
    email = farmer_names_in_db[selected_name]

    if not selected_metrics:
        st.warning("Selecciona al menos una métrica.")
        st.stop()

    keys = [metric_options[m][0] for m in selected_metrics]
    trend = get_farmer_trend(email, keys)

    if not trend:
        st.info("Sin datos para este farmer en el histórico.")
        st.stop()

    df_trend = pd.DataFrame(trend)
    df_trend["snap_date"] = pd.to_datetime(df_trend["snap_date"])
    df_trend = df_trend.sort_values("snap_date")

    st.markdown(f"### Evolución de {selected_name}")

    fig = go.Figure()
    for metric_label, (key, fmt) in metric_options.items():
        if metric_label not in selected_metrics or key not in df_trend.columns:
            continue
        vals = df_trend[key].tolist()
        dates_x = df_trend["snap_date"].tolist()

        if fmt == "decimal":
            y = [v * 100 if v is not None else None for v in vals]
            ref_line = 90
        elif fmt == "pp":
            y = vals
            ref_line = 0
        else:
            y = vals
            ref_line = 30

        fig.add_trace(go.Scatter(
            x=dates_x, y=y,
            name=metric_label,
            mode="lines+markers",
            line=dict(width=2),
            marker=dict(size=8),
            connectgaps=False,
        ))

    # Reference line (90% / 0pp / 30%)
    if selected_metrics:
        first_fmt = metric_options[selected_metrics[0]][1]
        ref = 90 if first_fmt == "decimal" else (0 if first_fmt == "pp" else 30)
        fig.add_hline(y=ref, line_dash="dash", line_color="white",
                      opacity=0.4, annotation_text="Target")

    fig.update_layout(
        height=400,
        margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Consecutive red weeks ─────────────────────────────────────────────────
    st.markdown("### Semanas consecutivas en rojo")
    red_map = {
        "Churn ATT": "ATT_Churn",
        "MD Total ATT": "ATT_MD_Total",
        "MD Pro ATT": "ATT_MD_Pro",
        "Ads Revenue ATT": "ATT_Rev_real",
    }
    red_cols = st.columns(len([m for m in selected_metrics if m in red_map]) or 1)
    idx = 0
    for m in selected_metrics:
        if m in red_map:
            weeks = get_consecutive_red_weeks(email, red_map[m])
            with red_cols[idx]:
                color = "#EF4444" if weeks >= 3 else "#F59E0B" if weeks >= 2 else "#00B341"
                st.markdown(f"""
                <div style="background:#FFFFFF;border-radius:10px;padding:1rem;text-align:center;border-top:4px solid {color};border:1px solid #E5E7EB;box-shadow:0 2px 6px rgba(0,0,0,0.05)">
                    <div style="font-size:0.72rem;color:#6B7280;font-weight:600;text-transform:uppercase;letter-spacing:0.5px">{m}</div>
                    <div style="font-size:2rem;font-weight:800;color:{color}">{weeks}w</div>
                    <div style="font-size:0.7rem;color:#9CA3AF">consecutivas en 🔴</div>
                </div>
                """, unsafe_allow_html=True)
            idx += 1

else:
    # ── Team metric trend ─────────────────────────────────────────────────────
    if not selected_metrics:
        st.warning("Selecciona al menos una métrica.")
        st.stop()

    selected_metric = selected_metrics[0]
    key, fmt = metric_options[selected_metric]

    st.markdown(f"### Evolución del equipo — {selected_metric}")

    all_history = get_history(weeks_back=12)
    if not all_history:
        st.info("Sin datos históricos.")
        st.stop()

    df_all = pd.DataFrame(all_history)
    df_all["snap_date"] = pd.to_datetime(df_all["snap_date"])
    df_all = df_all.sort_values("snap_date")

    if key not in df_all.columns:
        st.warning(f"Métrica {selected_metric} no disponible en el histórico.")
        st.stop()

    if fmt == "decimal":
        df_all["_val"] = df_all[key] * 100
        ref = 90
    elif fmt == "pp":
        df_all["_val"] = df_all[key]
        ref = 0
    else:
        df_all["_val"] = df_all[key]
        ref = 30

    fig2 = go.Figure()
    for email_f in df_all.get("email", pd.Series(dtype=str)).unique() if "email" in df_all.columns else []:
        sub = df_all[df_all["email"] == email_f].dropna(subset=["_val"])
        if sub.empty:
            continue
        name = FARMER_NAMES.get(email_f, email_f.split("@")[0].replace(".", " ").title())
        fig2.add_trace(go.Scatter(
            x=sub["snap_date"], y=sub["_val"],
            name=name,
            mode="lines+markers",
            line=dict(width=1.5),
            marker=dict(size=6),
            opacity=0.85,
        ))

    fig2.add_hline(y=ref, line_dash="dash", line_color="#E8281F",
                   opacity=0.6, annotation_text="Target")

    fig2.update_layout(
        height=450,
        margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.01),
        hovermode="x unified",
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Average trend
    avg_trend = df_all.groupby("snap_date")["_val"].mean().reset_index()
    st.markdown(f"**Promedio del equipo:** {avg_trend['_val'].iloc[-1]:.1f}{'%' if fmt in ('decimal','pct_raw') else ' pp'} en la última corrida")

    # Table: last two snaps comparison
    if len(dates) >= 2:
        st.markdown("### Variación vs corrida anterior")
        snap_curr = get_history(weeks_back=1)
        snap_prev_list = [s for s in get_history(weeks_back=3) if s.get("snap_date") != dates[0]]

        curr_by_farmer = {s.get("email"): s.get(key) for s in snap_curr if s.get("email")}
        prev_by_farmer = {s.get("email"): s.get(key) for s in snap_prev_list if s.get("email")}

        rows = []
        for email_f, curr_val in curr_by_farmer.items():
            prev_val = prev_by_farmer.get(email_f)
            name = FARMER_NAMES.get(email_f, email_f)
            if curr_val is not None and prev_val is not None:
                delta = (curr_val - prev_val) * (100 if fmt == "decimal" else 1)
                trend_icon = "📈" if delta > 0 else "📉" if delta < 0 else "➡️"
                rows.append({
                    "Farmer": name,
                    "Actual": f"{curr_val*100:.1f}%" if fmt == "decimal" else f"{curr_val:.1f}",
                    "Anterior": f"{prev_val*100:.1f}%" if fmt == "decimal" else f"{prev_val:.1f}",
                    "Δ": f"{trend_icon} {delta:+.1f}{'pp' if fmt != 'pct_raw' else '%'}",
                })
        if rows:
            st.dataframe(pd.DataFrame(rows).sort_values("Δ"), use_container_width=True, hide_index=True)
