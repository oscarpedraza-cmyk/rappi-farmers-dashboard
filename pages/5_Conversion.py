from __future__ import annotations
import streamlit as st
import io
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.loader import FARMER_NAMES, FARMERS_EMAILS, EXCLUDED_EMAILS, refresh_net_rev_adj
from core.metrics import (QUARTILE_COLOR, QUARTILE_LABEL, score_farmer,
                          assign_quartiles, get_all_semaforos, calcular_compensacion_completa)
from core.auth import require_auth, render_topbar
from core.style import inject_global_css

st.set_page_config(page_title="Conversión — Rappi Farmers", page_icon="🚀", layout="wide")
st.markdown(inject_global_css(), unsafe_allow_html=True)
email_auth, is_supervisor = require_auth()
render_topbar()


# ── Auto-load si session_state está vacío ─────────────────────────────────────
if "farmers_data" not in st.session_state:
    from core.db import load_latest_state
    latest = load_latest_state()
    if latest:
        st.session_state["farmers_data"] = latest["farmers_data"]
        st.session_state["dia_corte"]    = latest["dia_corte"]
        st.session_state["dias_mes"]     = latest["dias_mes"]
        if latest.get("productividad_raw"):
            try:
                df_raw = pd.read_json(io.StringIO(latest["productividad_raw"]))
                df_raw.columns = [int(c) for c in df_raw.columns]
                st.session_state["_productividad_raw"] = df_raw
            except Exception:
                pass
        if latest.get("conversion_raw"):
            st.session_state["_conversion_raw"] = latest["conversion_raw"]
    else:
        st.warning("⏳ El supervisor aún no ha cargado datos. Vuelve más tarde o contacta a Oscar Pedraza.")
        st.stop()

ACTIVE_FARMERS = set(FARMERS_EMAILS) - EXCLUDED_EMAILS

# ─────────────────────────────────────────────────────────────────────────────
# Helper: load Conversión DETALLE from session
# ─────────────────────────────────────────────────────────────────────────────
def load_detalle() -> Optional[pd.DataFrame]:
    raw = st.session_state.get("_conversion_raw")
    if not raw:
        # Try to restore from latest_state
        from core.db import load_latest_state
        latest = load_latest_state()
        if latest and latest.get("conversion_raw"):
            st.session_state["_conversion_raw"] = latest["conversion_raw"]
            raw = latest["conversion_raw"]
    if not raw:
        return None
    try:
        df = pd.read_json(io.StringIO(raw))
        return df
    except Exception:
        return None


df_det = load_detalle()

# ─────────────────────────────────────────────────────────────────────────────
# Quartiles from session
# ─────────────────────────────────────────────────────────────────────────────
farmers_data = st.session_state["farmers_data"]
dias_mes     = st.session_state.get("dias_mes", 31)

# Recalculate Net_Rev_Adj with today's date (not the upload date)
refresh_net_rev_adj(farmers_data, dias_mes)

all_scores = {}
for f, d in farmers_data.items():
    sems = get_all_semaforos(d)
    comp = calcular_compensacion_completa(d)
    all_scores[f] = score_farmer(sems, comp)
quartiles = assign_quartiles(all_scores)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="rb-page-header">
    <h1>🎯 Conversión Real</h1>
    <p>Conversión efectiva confirmada por sistema vs. lo que el farmer tipificó como cerrado.</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# BRANCH A — Conversión con DETALLE real (pestaña "Conversión" en Sheet Maestro)
# ─────────────────────────────────────────────────────────────────────────────
if df_det is not None and not df_det.empty and "FARMER" in df_det.columns:

    # Normalize
    df_det["FARMER"] = df_det["FARMER"].astype(str).str.strip().str.lower()
    df_det = df_det[df_det["FARMER"].isin(ACTIVE_FARMERS)].copy()

    # Bool conversion helpers
    def _bool_col(df, col):
        """Returns Series: True where col == 'SI'"""
        if col not in df.columns:
            return pd.Series(False, index=df.index)
        return df[col].astype(str).str.upper().str.strip() == "SI"

    def _num_col(df, col):
        """Returns Series: numeric (NaN where missing)"""
        if col not in df.columns:
            return pd.Series(pd.NA, index=df.index, dtype=float)
        return pd.to_numeric(df[col], errors="coerce")

    # ── Summary table per farmer ──────────────────────────────────────────────
    summary_rows = []
    for farmer in sorted(ACTIVE_FARMERS):
        fd = df_det[df_det["FARMER"] == farmer]
        if fd.empty:
            continue
        name = FARMER_NAMES.get(farmer, farmer.split("@")[0].title())
        n    = len(fd)

        # MD
        md_tip    = int(_bool_col(fd, "MARKDOWN").sum())
        md_real   = int((_num_col(fd, "MD") == 1).sum())
        md_falso  = int((_bool_col(fd, "MARKDOWN") & (_num_col(fd, "MD") != 1)).sum())
        md_pct    = round(md_real / md_tip * 100, 1) if md_tip > 0 else 0

        # ADS
        ads_tip   = int(_bool_col(fd, "ADS").sum())
        ads_real  = int((_num_col(fd, "BN") == 1).sum())
        ads_falso = int((_bool_col(fd, "ADS") & (_num_col(fd, "BN") != 1)).sum())
        ads_pct   = round(ads_real / ads_tip * 100, 1) if ads_tip > 0 else 0

        # Churn
        ch_tip    = int(_bool_col(fd, "CHURN").sum())
        ch_real   = int((_num_col(fd, "ORD") == 1).sum())
        ch_falso  = int((_bool_col(fd, "CHURN") & (_num_col(fd, "ORD") != 1)).sum())
        ch_pct    = round(ch_real / ch_tip * 100, 1) if ch_tip > 0 else 0

        # Global quality score (weighted)
        total_tip    = md_tip + ads_tip + ch_tip
        total_real   = md_real + ads_real + ch_real
        calidad_tip  = round(total_real / total_tip * 100, 1) if total_tip > 0 else 0

        summary_rows.append({
            "email":        farmer,
            "Farmer":       name,
            "Seguimientos": n,
            "Q":            quartiles.get(farmer, "Q4"),
            # MD
            "MD Tipificó":  md_tip,
            "MD Real":      md_real,
            "MD Falso":     md_falso,
            "MD Conv%":     md_pct,
            # ADS
            "ADS Tipificó": ads_tip,
            "ADS Real":     ads_real,
            "ADS Falso":    ads_falso,
            "ADS Conv%":    ads_pct,
            # Churn
            "CH Tipificó":  ch_tip,
            "CH Real":      ch_real,
            "CH Falso":     ch_falso,
            "CH Conv%":     ch_pct,
            # Global
            "Calidad %":    calidad_tip,
        })

    df_sum = pd.DataFrame(summary_rows).sort_values("Calidad %", ascending=False)

    # ── KPI cards del equipo ──────────────────────────────────────────────────
    total_md_tip   = df_sum["MD Tipificó"].sum()
    total_md_real  = df_sum["MD Real"].sum()
    total_ads_tip  = df_sum["ADS Tipificó"].sum()
    total_ads_real = df_sum["ADS Real"].sum()
    total_ch_tip   = df_sum["CH Tipificó"].sum()
    total_ch_real  = df_sum["CH Real"].sum()
    total_falso    = df_sum["MD Falso"].sum() + df_sum["ADS Falso"].sum() + df_sum["CH Falso"].sum()

    avg_md_pct  = round(total_md_real  / total_md_tip  * 100, 1) if total_md_tip  > 0 else 0
    avg_ads_pct = round(total_ads_real / total_ads_tip * 100, 1) if total_ads_tip > 0 else 0
    avg_ch_pct  = round(total_ch_real  / total_ch_tip  * 100, 1) if total_ch_tip  > 0 else 0

    def _card(icon, label, pct, real, tip, color):
        return f"""
        <div style="background:#FFFFFF;border-radius:12px;padding:1.2rem 1.4rem;
                    border-top:4px solid {color};border:1px solid #E5E7EB;
                    box-shadow:0 2px 8px rgba(0,0,0,0.06)">
            <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;
                        letter-spacing:0.5px;font-weight:600">{icon} {label}</div>
            <div style="font-size:2.2rem;font-weight:800;color:{color};margin:0.2rem 0">{pct}%</div>
            <div style="font-size:0.8rem;color:#374151">
                {int(real)} cierres reales / {int(tip)} tipificados
            </div>
        </div>"""

    c1, c2, c3, c4 = st.columns(4)
    c_md  = "#00B341" if avg_md_pct  >= 30 else "#F59E0B" if avg_md_pct  >= 15 else "#EF4444"
    c_ads = "#00B341" if avg_ads_pct >= 30 else "#F59E0B" if avg_ads_pct >= 15 else "#EF4444"
    c_ch  = "#00B341" if avg_ch_pct  >= 30 else "#F59E0B" if avg_ch_pct  >= 15 else "#EF4444"
    with c1: st.markdown(_card("💰", "MD Conv. Real",   avg_md_pct,  total_md_real,  total_md_tip,  c_md),  unsafe_allow_html=True)
    with c2: st.markdown(_card("📢", "ADS Conv. Real",  avg_ads_pct, total_ads_real, total_ads_tip, c_ads), unsafe_allow_html=True)
    with c3: st.markdown(_card("🔄", "Churn Conv. Real",avg_ch_pct,  total_ch_real,  total_ch_tip,  c_ch),  unsafe_allow_html=True)
    with c4:
        falso_color = "#EF4444" if total_falso > 100 else "#F59E0B" if total_falso > 50 else "#00B341"
        st.markdown(f"""
        <div style="background:#FFF5F5;border-radius:12px;padding:1.2rem 1.4rem;
                    border-top:4px solid {falso_color};border:1px solid #FEE2E2;
                    box-shadow:0 2px 8px rgba(0,0,0,0.06)">
            <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;
                        letter-spacing:0.5px;font-weight:600">⚠️ Falsa Conversión</div>
            <div style="font-size:2.2rem;font-weight:800;color:{falso_color};margin:0.2rem 0">{int(total_falso)}</div>
            <div style="font-size:0.8rem;color:#374151">
                Casos tipificados como cerrados sin cierre efectivo
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabla resumen por farmer ──────────────────────────────────────────────
    st.markdown("### 📊 Conversión real por farmer")
    st.caption("Datos del DETALLE — sistema confirma cierre efectivo (MD=1, BN=1, ORD=1)")

    # Build HTML table
    medal = ["🥇", "🥈", "🥉"]
    rows_html = ""
    for i, (_, row) in enumerate(df_sum.iterrows()):
        rank   = medal[i] if i < 3 else str(i + 1)
        bg     = "#FFFFFF" if i % 2 == 0 else "#FAFBFC"
        q      = row["Q"]
        qcolor = QUARTILE_COLOR.get(q, "#9CA3AF")
        calidad = row["Calidad %"]
        cal_c  = "#00B341" if calidad >= 30 else "#F59E0B" if calidad >= 15 else "#EF4444"

        def _pct_cell(pct, falso):
            c = "#00B341" if pct >= 30 else "#F59E0B" if pct >= 15 else "#EF4444"
            alert = f' <span style="color:#EF4444;font-size:0.7rem">({int(falso)} ✗)</span>' if falso > 0 else ""
            return f'<span style="color:{c};font-weight:700">{pct:.1f}%</span>{alert}'

        rows_html += f"""
        <tr style="background:{bg};border-bottom:1px solid #F3F4F6">
            <td style="padding:11px 14px;text-align:center">{rank}</td>
            <td style="padding:11px 14px;border-left:3px solid {qcolor}">
                <span style="background:{qcolor}18;color:{qcolor};font-size:0.65rem;
                      font-weight:700;padding:2px 6px;border-radius:4px;margin-right:6px">{q}</span>
                <span style="font-weight:600;color:#1A1A1A">{row['Farmer']}</span>
            </td>
            <td style="padding:11px 14px;text-align:center;color:#6B7280">{int(row['Seguimientos'])}</td>
            <td style="padding:11px 14px;text-align:center">{_pct_cell(row['MD Conv%'], row['MD Falso'])}</td>
            <td style="padding:11px 14px;text-align:center;font-size:0.8rem;color:#374151">
                {int(row['MD Real'])}/{int(row['MD Tipificó'])}
            </td>
            <td style="padding:11px 14px;text-align:center">{_pct_cell(row['ADS Conv%'], row['ADS Falso'])}</td>
            <td style="padding:11px 14px;text-align:center;font-size:0.8rem;color:#374151">
                {int(row['ADS Real'])}/{int(row['ADS Tipificó'])}
            </td>
            <td style="padding:11px 14px;text-align:center">{_pct_cell(row['CH Conv%'], row['CH Falso'])}</td>
            <td style="padding:11px 14px;text-align:center;font-size:0.8rem;color:#374151">
                {int(row['CH Real'])}/{int(row['CH Tipificó'])}
            </td>
            <td style="padding:11px 14px;text-align:center;font-weight:800;color:{cal_c};font-size:1rem">
                {calidad:.1f}%
            </td>
        </tr>"""

    st.markdown(f"""
    <div style="border-radius:14px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.10);margin-bottom:2rem">
        <div style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse;font-size:0.83rem;background:white">
            <thead>
                <tr style="background:#F8F9FA;border-bottom:2px solid #E5E7EB">
                    <th style="padding:10px 14px;text-align:center;color:#6B7280;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.8px">#</th>
                    <th style="padding:10px 14px;text-align:left;color:#6B7280;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.8px">FARMER</th>
                    <th style="padding:10px 14px;text-align:center;color:#6B7280;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.8px">SEGUIM.</th>
                    <th style="padding:10px 14px;text-align:center;color:#4A90D9;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.8px">💰 MD %</th>
                    <th style="padding:10px 14px;text-align:center;color:#4A90D9;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.8px">MD R/T</th>
                    <th style="padding:10px 14px;text-align:center;color:#9333EA;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.8px">📢 ADS %</th>
                    <th style="padding:10px 14px;text-align:center;color:#9333EA;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.8px">ADS R/T</th>
                    <th style="padding:10px 14px;text-align:center;color:#F59E0B;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.8px">🔄 CHURN %</th>
                    <th style="padding:10px 14px;text-align:center;color:#F59E0B;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.8px">CH R/T</th>
                    <th style="padding:10px 14px;text-align:center;color:#374151;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.8px">CALIDAD TIP.</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
        </div>
    </div>
    <div style="font-size:0.72rem;color:#9CA3AF;margin-bottom:1.5rem">
        R/T = Reales / Tipificados &nbsp;·&nbsp; (N ✗) = casos tipificados como cerrados sin cierre efectivo en sistema
        &nbsp;·&nbsp; Calidad de Tipificación = total cierres reales / total tipificados
    </div>
    """, unsafe_allow_html=True)

    # ── ALERTA FALSA CONVERSIÓN ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("""
    <div style="background:#FEF2F2;border:2px solid #EF4444;border-radius:14px;
                padding:1.2rem 1.6rem;margin-bottom:1.5rem">
        <div style="font-size:1.1rem;font-weight:800;color:#EF4444;margin-bottom:4px">
            ⚠️ Alerta de Falsa Conversión
        </div>
        <div style="font-size:0.85rem;color:#7F1D1D">
            El farmer tipificó como <b>cerrado</b> en su seguimiento, pero el sistema
            <b>no registra cierre efectivo</b>. Estos casos requieren revisión o corrección de tipificación.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Filter selector
    farmer_options = (["Todos"] if is_supervisor else []) + [
        FARMER_NAMES.get(f, f) for f in sorted(ACTIVE_FARMERS)
        if f in df_det["FARMER"].values
    ]

    if is_supervisor:
        sel_farmer_name = st.selectbox("Filtrar por farmer", farmer_options, key="conv_sel_farmer")
    else:
        my_name = FARMER_NAMES.get(email_auth.strip().lower(), email_auth)
        sel_farmer_name = my_name
        st.markdown(f"""
        <div style="background:rgba(74,108,247,0.08);border-left:4px solid #4A6CF7;
                    border-radius:8px;padding:0.7rem 1rem;margin-bottom:1rem">
            👤 <b>Viendo tus casos: {my_name}</b>
        </div>""", unsafe_allow_html=True)

    palanca_sel = st.radio("Palanca", ["Todas", "MD", "ADS", "Churn"],
                           horizontal=True, key="conv_palanca_sel")

    # Build false-conversion detail table
    def _build_falsos(palanca_filter):
        """Returns a DataFrame of false-conversion rows for display."""
        frames = []
        palancas = {
            "MD":    ("MARKDOWN", "MD", "TIPO_DE_MARKDOWN"),
            "ADS":   ("ADS",      "BN", "TIPO_DE_ADS"),
            "Churn": ("CHURN",    "ORD", None),
        }
        target = {palanca_filter: palancas[palanca_filter]} if palanca_filter != "Todas" else palancas
        for pal_name, (tip_col, real_col, tipo_col) in target.items():
            if tip_col not in df_det.columns or real_col not in df_det.columns:
                continue
            mask = (_bool_col(df_det, tip_col)) & (_num_col(df_det, real_col) != 1)
            sub  = df_det[mask].copy()
            if sub.empty:
                continue
            sub = sub.rename(columns={"FARMER": "email"})
            sub["Palanca"]  = pal_name
            sub["Tipificó"] = "SI"
            sub["Cierre Sistema"] = "❌ Sin cierre"
            sub["Tipo"] = sub[tipo_col].astype(str) if tipo_col and tipo_col in sub.columns else "—"
            # Pick display columns
            cols_show = ["email", "Palanca"]
            for c in ["BRAND_NAME", "DATE", "COUNTRY"]:
                if c in sub.columns:
                    cols_show.append(c)
            cols_show += ["Tipo", "Cierre Sistema"]
            frames.append(sub[cols_show].copy())
        if not frames:
            return pd.DataFrame()
        result = pd.concat(frames, ignore_index=True)
        result["Farmer"] = result["email"].map(lambda e: FARMER_NAMES.get(e, e))
        return result

    df_falsos = _build_falsos(palanca_sel)

    # Apply farmer filter
    if sel_farmer_name != "Todos":
        email_sel = next(
            (e for e, n in FARMER_NAMES.items() if n == sel_farmer_name), None
        )
        if email_sel and "email" in df_falsos.columns:
            df_falsos = df_falsos[df_falsos["email"] == email_sel]

    if df_falsos.empty:
        st.success("✅ No hay casos de falsa conversión para el filtro seleccionado.")
    else:
        total_falsos = len(df_falsos)
        st.markdown(f"""
        <div style="background:#FEE2E2;border-radius:8px;padding:0.6rem 1rem;
                    margin-bottom:0.8rem;font-weight:700;color:#991B1B">
            🚨 {total_falsos} caso{'s' if total_falsos != 1 else ''} de falsa conversión
            {'(equipo completo)' if sel_farmer_name == 'Todos' else f'de {sel_farmer_name}'}
        </div>""", unsafe_allow_html=True)

        # Rename for display
        rename_map = {
            "Farmer": "Farmer", "Palanca": "Palanca",
            "BRAND_NAME": "Tienda", "DATE": "Fecha",
            "COUNTRY": "País", "Tipo": "Tipo",
            "Cierre Sistema": "Sistema"
        }
        display_cols = [c for c in rename_map if c in df_falsos.columns]
        df_display = df_falsos[display_cols].rename(columns=rename_map)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        if is_supervisor:
            # Summary bar chart — falsos por farmer y palanca
            st.markdown("#### Distribución de falsa conversión por farmer")
            falso_by = (df_falsos.groupby(["Farmer", "Palanca"])
                        .size().reset_index(name="Casos"))
            pal_colors = {"MD": "#4A90D9", "ADS": "#9333EA", "Churn": "#F59E0B"}
            fig = go.Figure()
            for pal in ["MD", "ADS", "Churn"]:
                sub_p = falso_by[falso_by["Palanca"] == pal]
                if sub_p.empty:
                    continue
                fig.add_trace(go.Bar(
                    name=pal, x=sub_p["Farmer"], y=sub_p["Casos"],
                    marker_color=pal_colors.get(pal, "#9CA3AF"),
                    text=sub_p["Casos"], textposition="outside",
                ))
            fig.update_layout(
                barmode="group", height=340,
                margin=dict(l=10, r=10, t=20, b=80),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                xaxis_tickangle=-35,
                legend=dict(orientation="h", y=1.1),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Gráfico de conversión real por palanca ────────────────────────────────
    st.markdown("---")
    st.markdown("### 📈 Comparativa de conversión real")

    tabs = st.tabs(["💰 MD", "📢 ADS", "🔄 Churn"])
    for tab, pal, tip_col, real_col in zip(
        tabs,
        ["MD", "ADS", "Churn"],
        ["MARKDOWN", "ADS", "CHURN"],
        ["MD", "BN", "ORD"]
    ):
        with tab:
            if tip_col not in df_det.columns or real_col not in df_det.columns:
                st.info(f"Sin columna {tip_col}/{real_col} en los datos.")
                continue

            pal_rows = []
            for farmer in sorted(ACTIVE_FARMERS):
                fd   = df_det[df_det["FARMER"] == farmer]
                name = FARMER_NAMES.get(farmer, farmer.split("@")[0].title())
                tip  = int(_bool_col(fd, tip_col).sum())
                real = int((_num_col(fd, real_col) == 1).sum())
                pct  = round(real / tip * 100, 1) if tip > 0 else 0
                falso= tip - real
                pal_rows.append({"Farmer": name, "Tipificó": tip, "Real": real,
                                  "Falso": falso, "Conv%": pct})
            df_pal = pd.DataFrame(pal_rows).sort_values("Conv%", ascending=False)

            avg = df_pal["Conv%"].mean()
            colors = ["#00B341" if v >= avg else "#EF4444" for v in df_pal["Conv%"]]

            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="Tipificó (total)", x=df_pal["Farmer"], y=df_pal["Tipificó"],
                marker_color="#E5E7EB", opacity=0.6,
            ))
            fig.add_trace(go.Bar(
                name="Cierre real", x=df_pal["Farmer"], y=df_pal["Real"],
                marker_color="#00B341", opacity=0.9,
                text=df_pal["Conv%"].apply(lambda v: f"{v:.0f}%"),
                textposition="outside",
            ))
            fig.add_trace(go.Bar(
                name="Falso (tipificó=SI, sin cierre)",
                x=df_pal["Farmer"], y=df_pal["Falso"],
                marker_color="#EF4444", opacity=0.7,
            ))
            fig.update_layout(
                barmode="overlay", height=360,
                margin=dict(l=10, r=10, t=30, b=90),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", y=1.12),
                xaxis_tickangle=-35,
            )
            fig.add_hline(y=avg, line_dash="dash", line_color="#F59E0B",
                          annotation_text=f"Prom. {avg:.1f}%", annotation_position="top right")
            st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# BRANCH B — Fallback: conversión desde hoja Productividad (clásico)
# ─────────────────────────────────────────────────────────────────────────────
else:
    if df_det is not None:
        st.info("ℹ️ El DETALLE cargado no tiene columna FARMER. Usando datos de Productividad.")
    else:
        st.info("📂 **Para ver Conversión Real**, añade una pestaña llamada **`Conversión`** en el Sheet Maestro con el contenido del DETALLE.xlsx (columnas: FARMER, MARKDOWN, MD, ADS, BN, CHURN, ORD, BRAND_NAME…)\n\nMostrando embudo clásico desde hoja Productividad.")

    raw_prod = st.session_state.get("_productividad_raw")
    if raw_prod is None:
        st.warning("⚠️ Tampoco hay datos de Productividad. Sube el Sheet Maestro.")
        st.stop()

    df = raw_prod.copy()
    FARMER_COL   = 14
    CONTACT_COL  = 4
    MD_COL, MD_ACEPT_COL = 26, 32
    ADS_COL, ADS_TIPO_COL, ADS_NEVER_COL = 35, 36, 39
    CHURN_COL, CHURN_REAC_COL = 40, 46

    ADS_POSITIVE  = {"upselling", "reactivación", "retention"}
    ADS_NEVER_POS = {"activo con coinversión", "activo sin coinversión"}

    def is_contacted(row):
        return str(row[CONTACT_COL]).strip().upper() != "NO"

    def is_md_contrato(row):
        return str(row[MD_ACEPT_COL]).strip().lower() == "si"

    def is_ads_contrato(row):
        tipo  = str(row[ADS_TIPO_COL]).strip().lower()  if ADS_TIPO_COL  < len(row) else ""
        never = str(row[ADS_NEVER_COL]).strip().lower() if ADS_NEVER_COL < len(row) else ""
        return tipo in ADS_POSITIVE or (tipo == "never ads" and never in ADS_NEVER_POS)

    def is_churn_retencion(row):
        if CHURN_REAC_COL >= len(row): return False
        val = row[CHURN_REAC_COL]
        return pd.notna(val) and str(val).strip() not in ("", "nan", "NaT")

    results = []
    for farmer_email, sub in df.groupby(FARMER_COL):
        farmer_email = str(farmer_email).strip().lower()
        if farmer_email not in ACTIVE_FARMERS: continue
        name = FARMER_NAMES.get(farmer_email, farmer_email.split("@")[0].title())
        for palanca_name, palanca_col, contrato_fn in [
            ("MD", MD_COL, is_md_contrato),
            ("Ads", ADS_COL, is_ads_contrato),
            ("Churn", CHURN_COL, is_churn_retencion),
        ]:
            if palanca_col >= df.shape[1]: continue
            p_sub = sub[sub[palanca_col].astype(str).str.upper() == "SI"]
            oportunidades = len(p_sub)
            if oportunidades == 0: continue
            contactados = int(p_sub.apply(is_contacted, axis=1).sum())
            contratos   = int(p_sub.apply(contrato_fn,  axis=1).sum())
            results.append({
                "email": farmer_email, "Farmer": name, "Palanca": palanca_name,
                "Oportunidades": int(oportunidades), "Contactados": int(contactados),
                "No contactados": int(oportunidades - contactados),
                "Contratos": int(contratos),
                "Conv. total %":    round(contratos / oportunidades * 100, 1),
                "Conv. efectiva %": round(contratos / contactados * 100, 1) if contactados > 0 else 0,
            })

    df_conv = pd.DataFrame(results)
    if df_conv.empty:
        st.error("Sin datos de conversión en la hoja Productividad.")
        st.stop()

    df_conv["Quartil"] = df_conv["email"].map(lambda e: quartiles.get(e, "Q4"))

    # Quick summary
    col_md, col_ads, col_churn = st.columns(3)
    for col, palanca, icon in [(col_md,"MD","💰"), (col_ads,"Ads","📢"), (col_churn,"Churn","🔄")]:
        sub = df_conv[df_conv["Palanca"] == palanca]
        if sub.empty:
            with col: st.metric(f"{icon} {palanca}", "Sin datos")
            continue
        avg_t = sub["Conv. total %"].mean()
        contr = sub["Contratos"].sum()
        ops   = sub["Oportunidades"].sum()
        c     = "#00B341" if avg_t >= 30 else "#F59E0B" if avg_t >= 15 else "#EF4444"
        with col:
            st.markdown(f"""
            <div style="background:#FFFFFF;border-radius:12px;padding:1.2rem;
                        border-top:4px solid {c};border:1px solid #E5E7EB;
                        box-shadow:0 2px 8px rgba(0,0,0,0.06)">
                <div style="font-size:0.72rem;color:#6B7280;text-transform:uppercase;
                            letter-spacing:0.5px;font-weight:600">{icon} {palanca}</div>
                <div style="font-size:2.2rem;font-weight:800;color:{c};margin:0.3rem 0">{avg_t:.1f}%</div>
                <div style="font-size:0.75rem;color:#9CA3AF">{int(contr)} contratos / {int(ops)} oportunidades</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    tabs = st.tabs(["💰 MD (Markdown)", "📢 Ads", "🔄 Churn (Retención)"])
    for tab, palanca in zip(tabs, ["MD", "Ads", "Churn"]):
        with tab:
            sub = df_conv[df_conv["Palanca"] == palanca].sort_values("Conv. total %", ascending=False)
            if sub.empty: st.info(f"Sin datos de conversión para {palanca}."); continue
            avg_t = sub["Conv. total %"].mean()
            colors = ["#00C9A7" if v >= avg_t else "#EF4444" for v in sub["Conv. total %"]]
            fig = go.Figure(go.Bar(
                x=sub["Farmer"], y=sub["Conv. total %"], marker_color=colors,
                text=sub["Conv. total %"].apply(lambda v: f"{v:.1f}%"), textposition="outside",
            ))
            fig.add_hline(y=avg_t, line_dash="dash", line_color="#E8281F",
                          annotation_text=f"Promedio {avg_t:.1f}%")
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=80),
                              plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                              xaxis_tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)

            display = sub[["Quartil","Farmer","Oportunidades","Contactados",
                           "No contactados","Contratos","Conv. total %","Conv. efectiva %"]].copy()

            def color_conv(val):
                try:
                    v = float(val)
                    if v >= 30: return "color: #00B341; font-weight: bold"
                    if v >= 15: return "color: #F59E0B; font-weight: bold"
                    return "color: #EF4444; font-weight: bold"
                except: return ""

            st.dataframe(
                display.style.map(color_conv, subset=["Conv. total %", "Conv. efectiva %"]),
                use_container_width=True, hide_index=True
            )
