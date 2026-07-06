from __future__ import annotations
import streamlit as st
import io
import pandas as pd
from datetime import date, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.loader import FARMER_NAMES, FARMERS_EMAILS, EXCLUDED_EMAILS, refresh_net_rev_adj
from core.metrics import get_all_semaforos, tier_farmer
from core.auth import require_auth, render_topbar
from core.style import inject_global_css
from core.db import load_latest_state

st.set_page_config(
    page_title="Resumen Semanal — Rappi Farmers",
    page_icon="🚀",
    layout="wide", initial_sidebar_state="expanded",
)
st.markdown(inject_global_css(), unsafe_allow_html=True)
email, is_supervisor = require_auth()
render_topbar()

if not is_supervisor:
    st.markdown("""
    <div style="background:#FEF2F2;border:1px solid #FCA5A5;border-left:4px solid #EF4444;
                border-radius:12px;padding:1.5rem 1.8rem;margin-top:2rem;text-align:center">
        <div style="font-size:2rem;margin-bottom:0.5rem">🔒</div>
        <div style="font-size:1.1rem;font-weight:700;color:#991B1B">Acceso restringido</div>
        <div style="color:#7F1D1D;font-size:0.88rem">Sección exclusiva del supervisor.</div>
    </div>""", unsafe_allow_html=True)
    st.stop()

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
        _cartera_src = latest.get("asignacion_raw") or latest.get("cartera_raw")
        if _cartera_src:
            st.session_state["_cartera_raw"] = _cartera_src

farmers_data = st.session_state.get("farmers_data") or {}
dia_corte    = st.session_state.get("dia_corte", date.today().day - 1)
dias_mes     = st.session_state.get("dias_mes", 31)
today        = date.today()

try:
    refresh_net_rev_adj(farmers_data, dias_mes)
except Exception:
    pass

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="rb-page-header">
    <h1>📋 Resumen Semanal</h1>
    <p>Genera el resumen del equipo listo para pegar en WhatsApp o Slack — un clic, cero edición.</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar: opciones ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Opciones")
    fmt = st.radio("Formato", ["WhatsApp", "Slack", "Texto plano"], key="resumen_fmt")
    semana_label = st.text_input("Semana / período", value=f"Semana {today.strftime('%d/%m')}", key="resumen_semana")
    incluir_gmv  = st.checkbox("Incluir GMV en riesgo", value=True, key="resumen_gmv")
    incluir_prod = st.checkbox("Incluir actividad de contactos", value=True, key="resumen_prod")
    incluir_acciones = st.checkbox("Incluir acciones sugeridas", value=True, key="resumen_acc")

# ── Recopilar datos disponibles ───────────────────────────────────────────────

# 1. Semáforo del equipo
tier_counts  = {"green": 0, "yellow": 0, "red": 0}
farmers_red  = []
farmers_yell = []
metric_reds  = {}
has_maestro  = bool(farmers_data)

if has_maestro:
    for farm, data in farmers_data.items():
        if farm not in ACTIVE_FARMERS:
            continue
        sems = get_all_semaforos(data)
        t    = tier_farmer(sems)
        tier_counts[t] = tier_counts.get(t, 0) + 1
        name = FARMER_NAMES.get(farm, farm.split("@")[0].title())
        if t == "red":
            farmers_red.append(name)
        elif t == "yellow":
            farmers_yell.append(name)
        for m, s in sems.items():
            if s == "red":
                metric_reds[m] = metric_reds.get(m, 0) + 1

# 2. GMV en riesgo (Cartera + recencia)
gmv_en_riesgo   = 0.0
marcas_en_riesgo = 0
has_cartera = False

cartera_json = st.session_state.get("_cartera_raw")
df_prod      = st.session_state.get("_productividad_raw")

if incluir_gmv and cartera_json:
    try:
        df_cart = pd.read_json(io.StringIO(cartera_json))
        df_cart.columns = [str(c).strip() for c in df_cart.columns]
        _cl = {c.lower(): c for c in df_cart.columns}
        GMV_COL    = _cl.get("gmv_l28d")
        ID_COL     = _cl.get("country_brand_id")
        FARMER_COL = _cl.get("brand_owner_email_nuevo")

        if GMV_COL:
            df_cart[GMV_COL] = pd.to_numeric(df_cart[GMV_COL], errors="coerce").fillna(0)

        # Recencia desde Productividad
        last_contact: dict = {}
        if df_prod is not None and ID_COL:
            try:
                required = {4, 14, 15}
                if required.issubset(set(df_prod.columns)):
                    date_col = 10 if 10 in df_prod.columns else (9 if 9 in df_prod.columns else None)
                    if date_col:
                        dfd = df_prod[[15, date_col]].copy()
                        dfd.columns = ["code", "date"]
                        dfd["date"] = pd.to_datetime(dfd["date"], errors="coerce")
                        # Fallback epoch-ms
                        num = pd.to_numeric(df_prod[date_col], errors="coerce")
                        bad = dfd["date"].notna() & (dfd["date"].dt.year < 2000)
                        if bad.any():
                            dfd.loc[bad, "date"] = pd.to_datetime(num[bad], unit="ms", errors="coerce")
                        dfd["code"] = dfd["code"].astype(str)
                        cutoff = pd.Timestamp(today) - pd.Timedelta(days=30)
                        df_30  = dfd[dfd["date"].notna() & (dfd["date"] >= cutoff)]
                        last_contact = df_30.groupby("code")["date"].max().to_dict()
            except Exception:
                pass

        if ID_COL:
            df_cart[ID_COL] = df_cart[ID_COL].astype(str)
            df_cart["days_since"] = df_cart[ID_COL].map(
                lambda c: max(0, (pd.Timestamp(today) - pd.Timestamp(last_contact[c])).days)
                if c in last_contact else None
            )
        else:
            df_cart["days_since"] = None

        at_risk = df_cart[df_cart["days_since"] >= 14] if "days_since" in df_cart else pd.DataFrame()
        if GMV_COL and not at_risk.empty:
            gmv_en_riesgo    = float(at_risk[GMV_COL].sum())
            marcas_en_riesgo = len(at_risk)
        has_cartera = True
    except Exception:
        pass

# 3. Actividad de contactos esta semana vs. semana pasada
contactos_esta   = 0
contactos_prev   = 0
has_actividad    = False

if incluir_prod and df_prod is not None:
    try:
        required = {4, 14}
        if required.issubset(set(df_prod.columns)):
            date_col = 10 if 10 in df_prod.columns else (9 if 9 in df_prod.columns else None)
            if date_col:
                dfc = df_prod[[4, 14, date_col]].copy()
                dfc.columns = ["contactado", "farmer", "date"]
                dfc["date"] = pd.to_datetime(dfc["date"], errors="coerce")
                num = pd.to_numeric(df_prod[date_col], errors="coerce")
                bad = dfc["date"].notna() & (dfc["date"].dt.year < 2000)
                if bad.any():
                    dfc.loc[bad, "date"] = pd.to_datetime(num[bad], unit="ms", errors="coerce")
                dfc = dfc.dropna(subset=["date"])
                dfc["farmer"] = dfc["farmer"].astype(str).str.strip().str.lower()
                dfc = dfc[dfc["farmer"].isin(ACTIVE_FARMERS)]

                start_this = pd.Timestamp(today - timedelta(days=today.weekday()))  # lunes
                start_prev = start_this - timedelta(weeks=1)

                this_week = dfc[(dfc["date"] >= start_this) & (dfc["date"] < start_this + timedelta(weeks=1))]
                prev_week = dfc[(dfc["date"] >= start_prev) & (dfc["date"] < start_this)]

                contactos_esta = len(this_week)
                contactos_prev = len(prev_week)
                has_actividad  = True
    except Exception:
        pass


# ── Generar texto ─────────────────────────────────────────────────────────────
def b(txt):
    if fmt == "WhatsApp": return f"*{txt}*"
    if fmt == "Slack":    return f"*{txt}*"
    return txt

def i(txt):
    if fmt == "WhatsApp": return f"_{txt}_"
    if fmt == "Slack":    return f"_{txt}_"
    return txt

NL = "\n"

lines = []

# Encabezado
lines.append(b(f"📊 REPORTE SEMANAL — FARMERS AR/UY"))
lines.append(i(f"{semana_label} · Corte día {dia_corte}/{dias_mes}"))
lines.append("")

if has_maestro:
    # Estado del equipo
    lines.append(b("Estado del equipo:"))
    lines.append(f"🟢 {tier_counts['green']} farmers en verde")
    lines.append(f"🟡 {tier_counts['yellow']} en seguimiento")
    lines.append(f"🔴 {tier_counts['red']} críticos")
    lines.append("")

    if farmers_red:
        lines.append(b("🚨 Requieren atención urgente:"))
        for n in farmers_red:
            lines.append(f"• {n}")
        lines.append("")

    if farmers_yell:
        lines.append(b("⚠️ En seguimiento:"))
        for n in farmers_yell:
            lines.append(f"• {n}")
        lines.append("")

    # KPIs críticos
    top_kpis = sorted(metric_reds.items(), key=lambda x: -x[1])[:4]
    if top_kpis:
        lines.append(b("📌 KPIs más críticos:"))
        for metric, cnt in top_kpis:
            lines.append(f"• {metric}: {cnt} farmers bajo meta")
        lines.append("")
else:
    lines.append(i("(Sin datos del Maestro — semáforo no disponible)"))
    lines.append("")

# GMV en riesgo
if incluir_gmv and has_cartera:
    lines.append(b("💰 Cartera en riesgo de churn:"))
    if gmv_en_riesgo > 0:
        lines.append(f"• {marcas_en_riesgo} marcas sin contacto ≥2 sem")
        lines.append(f"• GMV en riesgo: ${gmv_en_riesgo:,.0f}")
    else:
        lines.append("• Sin marcas en riesgo crítico ✅")
    lines.append("")

# Actividad de contactos
if incluir_prod and has_actividad:
    delta = contactos_esta - contactos_prev
    arrow = "↑" if delta >= 0 else "↓"
    lines.append(b("📞 Actividad de contactos:"))
    lines.append(f"• Esta semana: {contactos_esta} follows")
    lines.append(f"• Semana anterior: {contactos_prev} follows")
    lines.append(f"• Variación: {arrow} {abs(delta)} ({'+' if delta>=0 else ''}{delta/max(1,contactos_prev)*100:.0f}%)")
    lines.append("")

# Acciones sugeridas
if incluir_acciones:
    lines.append(b("📋 Acciones esta semana:"))
    if has_maestro and farmers_red:
        lines.append(f"• 1:1 urgente con: {', '.join(farmers_red[:3])}")
    if gmv_en_riesgo > 5_000:
        lines.append(f"• Revisar Alerta Temprana de Churn ({marcas_en_riesgo} marcas)")
    if has_actividad and contactos_esta < contactos_prev * 0.8:
        lines.append("• Contactos abajo vs. semana pasada — verificar actividad del equipo")
    if not (has_maestro and farmers_red) and not (gmv_en_riesgo > 5_000):
        lines.append("• Mantener ritmo — equipo sin alertas críticas")
    lines.append("")

# Pie
lines.append(i(f"Generado desde el Dashboard de Farmers · {today.strftime('%d/%m/%Y')}"))

resumen_txt = NL.join(lines)

# ── Preview + Copy ────────────────────────────────────────────────────────────
col_prev, col_edit = st.columns([1, 1])

with col_prev:
    st.markdown("### Vista previa")
    st.markdown("""
    <div style="background:#ECE5DD;border-radius:12px;padding:1.2rem 1.4rem;
                font-family:monospace;font-size:0.82rem;white-space:pre-wrap;
                color:#1A1A1A;line-height:1.6">
    """ + resumen_txt.replace("\n", "<br>").replace("*", "").replace("_", "") + """
    </div>""", unsafe_allow_html=True)

with col_edit:
    st.markdown("### Texto copiable")
    st.caption("Hacé clic en el ícono de copiar (esquina superior derecha del bloque)")
    st.code(resumen_txt, language=None)

st.markdown("---")

# ── KPIs del resumen ──────────────────────────────────────────────────────────
st.markdown("### Datos usados para generar el resumen")
c1, c2, c3, c4 = st.columns(4)
c1.metric("🟢 Verde",        tier_counts["green"] if has_maestro else "—")
c2.metric("🟡 Seguimiento",  tier_counts["yellow"] if has_maestro else "—")
c3.metric("🔴 Críticos",     tier_counts["red"] if has_maestro else "—")
c4.metric("💰 GMV en riesgo", f"${gmv_en_riesgo:,.0f}" if has_cartera else "—")

if has_actividad:
    c5, c6, _, _ = st.columns(4)
    c5.metric("📞 Follows esta semana",  contactos_esta)
    c6.metric("📞 Follows sem. anterior", contactos_prev,
              delta=contactos_esta - contactos_prev)

if not has_maestro:
    st.info(
        "💡 Cargá el Sheet Maestro para incluir el semáforo y los KPIs de ATT en el resumen. "
        "Con solo la Asignación, el resumen incluye GMV en riesgo y actividad de contactos."
    )
