"""
9_WBR_Plan_Semanal.py — Plan de trabajo semanal (WBR)

Bloques:
  1. Briefing semanal automático: estado de los 5 KPIs, farmers críticos, alerta sem 4
  2. Proyección de cierre del mes para cada KPI (con metodología explicada)
  3. Checklist de acciones semanales (auto-generado + persistente hasta el lunes)
  4. Tracker de procesos disciplinarios (editable, solo supervisor)
"""
from __future__ import annotations
import streamlit as st
import io, json, math
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.loader import FARMER_NAMES, FARMERS_EMAILS, EXCLUDED_EMAILS
from core.metrics import get_all_semaforos, tier_farmer
from core.auth import require_auth, render_topbar
from core.style import inject_global_css
from core.db import (
    get_history, get_checklist_state, save_checklist_task,
    get_all_disciplinarios, save_disciplinario, delete_disciplinario,
    get_all_llamados, save_llamado, delete_llamado,
    save_wbr_doc, load_wbr_doc,
)

st.set_page_config(page_title="WBR Plan Semanal — Rappi Farmers", page_icon="🚀", layout="wide")
st.markdown(inject_global_css(), unsafe_allow_html=True)
email_auth, is_supervisor = require_auth()
render_topbar()

ACTIVE_FARMERS = set(FARMERS_EMAILS) - EXCLUDED_EMAILS

# ── Auto-load ─────────────────────────────────────────────────────────────────
if "farmers_data" not in st.session_state:
    from core.db import load_latest_state
    latest = load_latest_state()
    if latest:
        st.session_state["farmers_data"] = latest["farmers_data"]
        st.session_state["dia_corte"]    = latest["dia_corte"]
        st.session_state["dias_mes"]     = latest["dias_mes"]
    else:
        st.warning("⏳ El supervisor aún no ha cargado datos.")
        st.stop()

farmers_data = st.session_state["farmers_data"]
dia_corte    = st.session_state.get("dia_corte", date.today().day)
dias_mes     = st.session_state.get("dias_mes", 31)
today        = date.today()

# ── Semana del mes y clave ISO ─────────────────────────────────────────────────
sem_num      = (dia_corte - 1) // 7 + 1          # 1-4 within the month
week_key     = today.strftime("%G-W%V")           # ISO week for checklist
dias_restantes = max(dias_mes - dia_corte, 0)
progreso_pct   = round(dia_corte / dias_mes * 100, 1)

# ── Value helpers ─────────────────────────────────────────────────────────────
def _clean(v):
    """Return None if v is None or NaN."""
    if v is None: return None
    try:
        return None if math.isnan(float(v)) else v
    except (TypeError, ValueError):
        return None

# ── Color helpers ─────────────────────────────────────────────────────────────
def _semaforo_color(att: Optional[float], verde=0.90, amarillo=0.80) -> str:
    if att is None: return "#9CA3AF"
    if att >= verde:   return "#059669"
    if att >= amarillo: return "#F59E0B"
    return "#EF4444"

def _semaforo_icon(att: Optional[float], verde=0.90, amarillo=0.80) -> str:
    if att is None: return "⚪"
    if att >= verde:   return "🟢"
    if att >= amarillo: return "🟡"
    return "🔴"

def _att_bar(att: Optional[float], target: float = 1.0) -> str:
    if att is None: return ""
    pct = min(att / target * 100, 130)
    color = _semaforo_color(att)
    return (f'<div style="background:#F1F5F9;border-radius:4px;height:6px;margin-top:4px">'
            f'<div style="background:{color};width:{pct:.0f}%;height:6px;border-radius:4px"></div></div>')

# ── Compute team KPI aggregates ───────────────────────────────────────────────
kpi_vals = {"prod": [], "pitch": [], "churn": [], "ads": [], "md": []}
farmer_statuses = []

for email, data in farmers_data.items():
    if email not in ACTIVE_FARMERS:
        continue
    name  = FARMER_NAMES.get(email, email.split("@")[0].title())
    sems  = get_all_semaforos(data)
    tier  = tier_farmer(sems)

    prod  = _clean(data.get("productividad_pct"))
    pitch = _clean(data.get("Pitch_Pct"))
    churn = _clean(data.get("ATT_Churn"))
    ads   = _clean(data.get("ATT_Rev_real"))
    md    = _clean(data.get("ATT_MD_Total"))

    for key, val in [("prod", prod), ("pitch", pitch), ("churn", churn),
                     ("ads", ads), ("md", md)]:
        if val is not None:
            kpi_vals[key].append(val)

    farmer_statuses.append({
        "email": email, "name": name, "tier": tier,
        "prod": prod, "pitch": pitch, "churn": churn,
        "ads": ads, "md": md, "sems": sems,
    })

def _avg(lst): return sum(lst) / len(lst) if lst else None

team_prod  = _avg(kpi_vals["prod"])
team_pitch = _avg(kpi_vals["pitch"])
team_churn = _avg(kpi_vals["churn"])
team_ads   = _avg(kpi_vals["ads"])
team_md    = _avg(kpi_vals["md"])

farmers_red  = [f for f in farmer_statuses if f["tier"] == "red"]
farmers_crit = sorted(farmer_statuses, key=lambda x: (x["prod"] or 0))[:5]

# ── Historical comparison (last snapshot) ────────────────────────────────────
history = get_history(weeks_back=2)
prev_vals = {"prod": None, "pitch": None, "churn": None, "ads": None, "md": None}
if history:
    prev_snap = {}
    for snap in history:
        em = snap.get("email", "")
        if em and em not in prev_snap:
            prev_snap[em] = snap
    prev_lists = {"prod": [], "pitch": [], "churn": [], "ads": [], "md": []}
    for em, snap in prev_snap.items():
        for k, sk in [("prod","productividad_pct"),("pitch","Pitch_Pct"),
                      ("churn","ATT_Churn"),("ads","ATT_Rev_real"),("md","ATT_MD_Total")]:
            v = snap.get(sk)
            if v is not None:
                prev_lists[k].append(v)
    for k in prev_vals:
        prev_vals[k] = _avg(prev_lists[k])

def _delta(current, prev):
    if current is None or prev is None:
        return None
    return current - prev

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 0 — BANNER ALERTA SEMANA 4
# ════════════════════════════════════════════════════════════════════════════
if sem_num >= 4:
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#7F1D1D,#991B1B);border-radius:14px;
                padding:1.1rem 1.6rem;margin-bottom:1rem;
                box-shadow:0 4px 20px rgba(239,68,68,0.3)">
        <div style="display:flex;align-items:center;gap:12px">
            <div style="font-size:2rem">⚠️</div>
            <div>
                <div style="font-weight:800;color:white;font-size:1.05rem;letter-spacing:-0.2px">
                    SEMANA DE CIERRE — Semana {sem_num} del mes
                </div>
                <div style="color:rgba(255,255,255,0.75);font-size:0.82rem;margin-top:2px">
                    Históricamente cae el Pitch Integral en esta semana. Monitorear diariamente.
                    Quedan <b style="color:white">{dias_restantes} días</b> para cerrar el mes.
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Page header ───────────────────────────────────────────────────────────────
mes_nombre = today.strftime("%B %Y").capitalize()
st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.8rem">
    <div>
        <div style="font-size:1.3rem;font-weight:900;color:#0F172A;letter-spacing:-0.4px">
            📋 WBR — Plan Semanal
        </div>
        <div style="font-size:0.8rem;color:#64748B;margin-top:2px">
            {mes_nombre} · Semana {sem_num} del mes · Corte día <b>{dia_corte}</b> · {progreso_pct}% transcurrido
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 1 — BRIEFING SEMANAL
# ════════════════════════════════════════════════════════════════════════════
st.markdown('<div style="font-size:1rem;font-weight:800;color:#0F172A;margin-bottom:0.6rem">Estado del equipo esta semana</div>', unsafe_allow_html=True)

KPI_CONFIG = [
    {"key": "prod",  "label": "Productividad", "icon": "📞", "target": 0.90, "target_lbl": "≥ 90%", "verde": 0.90, "amarillo": 0.80},
    {"key": "pitch", "label": "Pitch Integral", "icon": "🎯", "target": 0.75, "target_lbl": "≥ 75%", "verde": 0.75, "amarillo": 0.60},
    {"key": "churn", "label": "Churn ATT",      "icon": "🔄", "target": 0.90, "target_lbl": "≥ 90%", "verde": 0.90, "amarillo": 0.80},
    {"key": "ads",   "label": "ADS Revenue",    "icon": "📢", "target": 0.90, "target_lbl": "≥ 90%", "verde": 0.90, "amarillo": 0.80},
    {"key": "md",    "label": "MD Total",       "icon": "💰", "target": 0.90, "target_lbl": "≥ 90%", "verde": 0.90, "amarillo": 0.80},
]
team_vals = {"prod": team_prod, "pitch": team_pitch, "churn": team_churn, "ads": team_ads, "md": team_md}

kpi_cols = st.columns(5)
for col, cfg in zip(kpi_cols, KPI_CONFIG):
    val    = team_vals[cfg["key"]]
    prev   = prev_vals[cfg["key"]]
    delta  = _delta(val, prev)
    color  = _semaforo_color(val, cfg["verde"], cfg["amarillo"])
    icon   = _semaforo_icon(val, cfg["verde"], cfg["amarillo"])
    pct_str = f"{val*100:.1f}%" if val is not None else "S/D"

    delta_html = ""
    if delta is not None:
        sign  = "▲" if delta >= 0 else "▼"
        dc    = "#059669" if delta >= 0 else "#EF4444"
        delta_html = f'<div style="font-size:0.72rem;color:{dc};font-weight:600">{sign} {abs(delta)*100:.1f}pp vs sem ant.</div>'
    else:
        delta_html = '<div style="font-size:0.72rem;color:#9CA3AF">Sin semana anterior</div>'

    with col:
        st.markdown(f"""
        <div style="background:#FFFFFF;border-radius:12px;padding:1rem;
                    border-top:3px solid {color};border:1px solid #E5E7EB;
                    box-shadow:0 2px 8px rgba(0,0,0,0.06)">
            <div style="font-size:0.68rem;color:#6B7280;text-transform:uppercase;
                        letter-spacing:0.6px;font-weight:600;margin-bottom:0.3rem">
                {cfg['icon']} {cfg['label']}
            </div>
            <div style="font-size:1.9rem;font-weight:800;color:{color};line-height:1.1">{icon} {pct_str}</div>
            <div style="font-size:0.7rem;color:#9CA3AF;margin-top:2px">Meta: {cfg['target_lbl']}</div>
            {_att_bar(val, cfg['target'])}
            <div style="margin-top:6px">{delta_html}</div>
        </div>""", unsafe_allow_html=True)

# ── Farmers críticos ──────────────────────────────────────────────────────────
st.markdown('<div style="height:0.8rem"></div>', unsafe_allow_html=True)
red_farmers = [f for f in farmer_statuses if f["tier"] == "red"]
yellow_farmers = [f for f in farmer_statuses if f["tier"] == "yellow"]

if red_farmers or yellow_farmers:
    def _farmer_row(f, border_color, name_color, val_color):
        prod_str  = f"Prod {f['prod']*100:.0f}%"  if f['prod']  else ""
        pitch_str = f" · Pitch {f['pitch']*100:.0f}%" if f['pitch'] else ""
        return (
            '<div style="display:flex;align-items:center;justify-content:space-between;'
            f'padding:4px 0;border-bottom:1px solid {border_color}">'
            f'<span style="font-size:0.83rem;font-weight:600;color:{name_color}">{f["name"]}</span>'
            f'<span style="font-size:0.72rem;color:{val_color}">{prod_str}{pitch_str}</span>'
            '</div>'
        )

    red_rows    = "".join(_farmer_row(f, "#FEE2E2", "#7F1D1D", "#EF4444") for f in red_farmers) \
                  if red_farmers else '<div style="color:#9CA3AF;font-size:0.8rem">Ninguno 🎉</div>'
    yellow_rows = "".join(_farmer_row(f, "#FEF3C7", "#78350F", "#D97706") for f in yellow_farmers) \
                  if yellow_farmers else '<div style="color:#9CA3AF;font-size:0.8rem">Ninguno 🎉</div>'

    col_r, col_y = st.columns(2)
    with col_r:
        st.markdown(
            '<div style="background:#FEF2F2;border:1px solid #FECACA;border-left:4px solid #EF4444;'
            'border-radius:12px;padding:0.9rem 1.1rem">'
            f'<div style="font-size:0.75rem;font-weight:700;color:#EF4444;text-transform:uppercase;'
            f'letter-spacing:0.5px;margin-bottom:0.5rem">🔴 Requieren atención urgente ({len(red_farmers)})</div>'
            f'{red_rows}'
            '</div>',
            unsafe_allow_html=True
        )
    with col_y:
        st.markdown(
            '<div style="background:#FFFBEB;border:1px solid #FDE68A;border-left:4px solid #F59E0B;'
            'border-radius:12px;padding:0.9rem 1.1rem">'
            f'<div style="font-size:0.75rem;font-weight:700;color:#F59E0B;text-transform:uppercase;'
            f'letter-spacing:0.5px;margin-bottom:0.5rem">🟡 En seguimiento ({len(yellow_farmers)})</div>'
            f'{yellow_rows}'
            '</div>',
            unsafe_allow_html=True
        )

st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 2 — PROYECCIÓN DE CIERRE DEL MES
# ════════════════════════════════════════════════════════════════════════════
st.markdown('<div style="font-size:1rem;font-weight:800;color:#0F172A;margin:1rem 0 0.6rem">Proyección de cierre del mes</div>', unsafe_allow_html=True)

PROJ_KPIS = [
    {
        "key": "prod",  "label": "Productividad", "icon": "📞",
        "meta": 0.90, "meta_lbl": "90%",
        "formula": "Promedio ATT% actual de todos los farmers. Se proyecta que la tendencia se mantenga si el ritmo diario de contactos no varía.",
        "calculo": "ATT% actual del equipo (ya es el acumulado del mes, no se extrapola más)"
    },
    {
        "key": "pitch", "label": "Pitch Integral", "icon": "🎯",
        "meta": 0.75, "meta_lbl": "75%",
        "formula": "El Pitch Integral es semanal (no acumulativo). La proyección = promedio de las semanas ya transcurridas como estimado del cierre.",
        "calculo": f"Promedio de semanas completadas ({sem_num} sem) → estimado cierre mes"
    },
    {
        "key": "churn", "label": "Churn ATT",      "icon": "🔄",
        "meta": 0.90, "meta_lbl": "90%",
        "formula": "ATT Churn acumulado del mes. La proyección asume el mismo ritmo de recuperaciones vs gross churn.",
        "calculo": "ATT% actual × (días_mes / dia_corte)"
    },
    {
        "key": "ads",   "label": "ADS Revenue",    "icon": "📢",
        "meta": 0.90, "meta_lbl": "90%",
        "formula": "Proyección lineal: si el equipo mantiene el ritmo actual de ingresos ADS hasta fin de mes.",
        "calculo": "ATT% actual × (días_mes / dia_corte)"
    },
    {
        "key": "md",    "label": "MD Total",       "icon": "💰",
        "meta": 0.90, "meta_lbl": "90%",
        "formula": "Proyección del MD% usando el modelo: MD acumulado + (MD diario histórico × días restantes) / GMV proyectado.",
        "calculo": "ATT% actual × (días_mes / dia_corte)"
    },
]

proj_cols = st.columns(5)
factor    = dias_mes / dia_corte if dia_corte > 0 else 1.0

for col, cfg in zip(proj_cols, PROJ_KPIS):
    current = team_vals[cfg["key"]]
    if current is None:
        proj = None
    elif cfg["key"] == "pitch":
        proj = current   # pitch is weekly average, already the estimate
    else:
        proj = min(current * factor, 1.5)   # cap at 150%

    color  = _semaforo_color(proj, cfg["meta"], cfg["meta"] * 0.88)
    icon   = _semaforo_icon(proj, cfg["meta"], cfg["meta"] * 0.88)
    proj_str  = f"{proj*100:.1f}%" if proj is not None else "S/D"
    curr_str  = f"{current*100:.1f}%" if current is not None else "S/D"
    gap_pp    = (proj - cfg["meta"]) * 100 if proj is not None else None
    gap_html  = ""
    if gap_pp is not None:
        if gap_pp >= 0:
            gap_html = f'<div style="font-size:0.7rem;color:#059669">+{gap_pp:.1f}pp sobre meta</div>'
        else:
            gap_html = f'<div style="font-size:0.7rem;color:#EF4444">{gap_pp:.1f}pp bajo meta ⚠️</div>'

    with col:
        st.markdown(f"""
        <div style="background:#FFFFFF;border-radius:12px;padding:1rem;
                    border-left:4px solid {color};border:1px solid #E5E7EB;
                    box-shadow:0 2px 8px rgba(0,0,0,0.06)">
            <div style="font-size:0.68rem;color:#6B7280;text-transform:uppercase;
                        letter-spacing:0.6px;font-weight:600;margin-bottom:0.4rem">
                {cfg['icon']} {cfg['label']}
            </div>
            <div style="font-size:1.7rem;font-weight:800;color:{color}">{icon} {proj_str}</div>
            <div style="font-size:0.7rem;color:#9CA3AF;margin-top:2px">
                Actual: {curr_str} · Meta: {cfg['meta_lbl']}
            </div>
            {gap_html}
        </div>""", unsafe_allow_html=True)

        with st.expander("¿Cómo se calcula?", expanded=False):
            st.markdown(f"""
            <div style="font-size:0.8rem;color:#374151;line-height:1.6">
                <b>Fórmula:</b> {cfg['formula']}<br><br>
                <b>Cálculo aplicado:</b> {cfg['calculo']}<br><br>
                <b>Día de corte:</b> {dia_corte} / {dias_mes} &nbsp;·&nbsp;
                <b>Factor:</b> ×{factor:.2f}
            </div>""", unsafe_allow_html=True)

st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 3 — CHECKLIST SEMANAL
# ════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;margin:1rem 0 0.6rem">
    <div style="font-size:1rem;font-weight:800;color:#0F172A">Checklist semanal</div>
    <div style="font-size:0.72rem;color:#9CA3AF;background:#F1F5F9;border-radius:6px;padding:2px 8px">
        {week_key} · se reinicia el lunes
    </div>
</div>
""", unsafe_allow_html=True)

# ── Auto-generate tasks based on KPI state ───────────────────────────────────
auto_tasks = []

# Productividad
prod_criticos = [f for f in farmer_statuses if f["prod"] is not None and f["prod"] < 0.80]
prod_cerca    = [f for f in farmer_statuses if f["prod"] is not None and 0.80 <= f["prod"] < 0.90]
if prod_criticos:
    names = ", ".join(f["name"].split()[0] for f in prod_criticos[:4])
    auto_tasks.append({
        "id": "prod_critico", "priority": "alta",
        "icon": "🔴", "categoria": "Productividad",
        "texto": f"Revisar agenda individual con farmers críticos en productividad: {names}",
        "detalle": f"{len(prod_criticos)} farmer(s) con ATT < 80%"
    })
if prod_cerca:
    names = ", ".join(f["name"].split()[0] for f in prod_cerca[:3])
    auto_tasks.append({
        "id": "prod_cerca", "priority": "media",
        "icon": "🟡", "categoria": "Productividad",
        "texto": f"Seguimiento diario a farmers cerca del límite: {names}",
        "detalle": f"{len(prod_cerca)} farmer(s) entre 80-90% ATT"
    })

# Pitch
pitch_bajos = [f for f in farmer_statuses if f["pitch"] is not None and f["pitch"] < 0.75]
if pitch_bajos:
    names = ", ".join(f["name"].split()[0] for f in sorted(pitch_bajos, key=lambda x: x["pitch"])[:4])
    auto_tasks.append({
        "id": "pitch_muestreo", "priority": "alta",
        "icon": "🎯", "categoria": "Pitch Integral",
        "texto": f"Agendar muestreo de pitch con farmers bajo meta: {names}",
        "detalle": f"{len(pitch_bajos)} farmer(s) con % palancas < 75%"
    })

# Churn
churn_bajos = [f for f in farmer_statuses if f["churn"] is not None and f["churn"] < 0.80]
if churn_bajos:
    names = ", ".join(f["name"].split()[0] for f in churn_bajos[:3])
    auto_tasks.append({
        "id": "churn_recuperacion", "priority": "alta",
        "icon": "🔄", "categoria": "Churn",
        "texto": f"Revisión de reactivaciones pendientes: {names}",
        "detalle": "Verificar prevenciones W1 diarias y 1 reactivación semanal mínima"
    })

# Ads
ads_bajos = [f for f in farmer_statuses if f["ads"] is not None and f["ads"] < 0.90]
if ads_bajos:
    auto_tasks.append({
        "id": "ads_top10", "priority": "media",
        "icon": "📢", "categoria": "ADS",
        "texto": "Sesión Top 10 ADS (1h semanal) con farmers bajo meta",
        "detalle": f"{len(ads_bajos)} farmer(s) bajo 90% ATT ADS Revenue"
    })

# MD / Coinversión
md_bajos = [f for f in farmer_statuses if f["md"] is not None and f["md"] < 0.90]
if md_bajos:
    auto_tasks.append({
        "id": "md_coinversion", "priority": "media",
        "icon": "💰", "categoria": "MD",
        "texto": "Revisar avance de coinversiones vs meta 41/semana",
        "detalle": "Foco: Lady Bobativa y Luis Fernando Hernández"
    })

# Semana de cierre
if sem_num >= 4:
    auto_tasks.append({
        "id": "cierre_pitch_monitoreo", "priority": "alta",
        "icon": "⚠️", "categoria": "Cierre de mes",
        "texto": "Monitorear Pitch Integral DIARIAMENTE (riesgo de caída histórico en sem 4)",
        "detalle": "Verificar que los farmers no abandonen palancas bajo presión de productividad"
    })
    auto_tasks.append({
        "id": "cierre_campanas", "priority": "alta",
        "icon": "📅", "categoria": "Cierre de mes",
        "texto": "Verificar ejecución de campañas en riesgo antes del miércoles",
        "detalle": "Banners pendientes y campañas de renovación"
    })

# Tarea recurrente siempre presente
auto_tasks.append({
    "id": "wbr_acuerdos_uy", "priority": "baja",
    "icon": "🌎", "categoria": "Uruguay",
    "texto": "Verificar que no haya bajas unilaterales de campañas ADS/MD en UY (acuerdo RGM)",
    "detalle": "DRI verifica semanalmente"
})

# ── Render checklist ──────────────────────────────────────────────────────────
done_state = get_checklist_state(week_key)
priority_order = {"alta": 0, "media": 1, "baja": 2}
auto_tasks.sort(key=lambda t: priority_order.get(t["priority"], 3))

priority_colors = {"alta": "#EF4444", "media": "#F59E0B", "baja": "#059669"}
priority_labels = {"alta": "URGENTE", "media": "ESTA SEMANA", "baja": "RECURRENTE"}
n_done  = sum(1 for t in auto_tasks if done_state.get(t["id"], False))
n_total = len(auto_tasks)

st.markdown(f"""
<div style="background:#F8FAFC;border-radius:10px;padding:0.6rem 1rem;
            margin-bottom:0.8rem;display:flex;align-items:center;gap:12px">
    <div style="font-size:0.82rem;color:#374151;font-weight:600">
        Progreso: <b>{n_done}/{n_total}</b> tareas completadas
    </div>
    <div style="flex:1;background:#E5E7EB;border-radius:4px;height:8px">
        <div style="background:#059669;width:{int(n_done/n_total*100) if n_total else 0}%;height:8px;border-radius:4px"></div>
    </div>
</div>
""", unsafe_allow_html=True)

for task in auto_tasks:
    tid       = task["id"]
    is_done   = done_state.get(tid, False)
    p_color   = priority_colors.get(task["priority"], "#9CA3AF")
    p_label   = priority_labels.get(task["priority"], "")
    bg        = "#F0FDF4" if is_done else "#FFFFFF"
    text_decor = "line-through;opacity:0.5" if is_done else "none"

    col_check, col_content = st.columns([0.5, 11])
    with col_check:
        new_val = st.checkbox("", value=is_done, key=f"chk_{tid}_{week_key}",
                              label_visibility="collapsed")
        if new_val != is_done:
            save_checklist_task(week_key, tid, new_val)
            st.rerun()
    with col_content:
        st.markdown(f"""
        <div style="background:{bg};border:1px solid {'#BBF7D0' if is_done else '#E5E7EB'};
                    border-radius:10px;padding:0.65rem 1rem;margin-bottom:0.3rem">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:2px">
                <span style="font-size:0.62rem;font-weight:700;color:{p_color};
                             background:{p_color}18;padding:1px 6px;border-radius:4px;
                             letter-spacing:0.4px">{p_label}</span>
                <span style="font-size:0.68rem;color:#9CA3AF">{task['categoria']}</span>
            </div>
            <div style="font-size:0.86rem;font-weight:600;color:#1A1A2E;text-decoration:{text_decor}">
                {task['icon']} {task['texto']}
            </div>
            <div style="font-size:0.75rem;color:#6B7280;margin-top:2px">{task['detalle']}</div>
        </div>""", unsafe_allow_html=True)

st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 4 — ADVERTENCIAS Y DISCIPLINARIO (solo supervisor)
# ════════════════════════════════════════════════════════════════════════════
if not is_supervisor:
    st.stop()

st.markdown("---")

# ── Shared helpers ────────────────────────────────────────────────────────────
TIPO_COLORS = {
    "Manpower":      ("#EFF6FF", "#2563EB"),
    "Rappi directo": ("#FFF7ED", "#EA580C"),
}

def _tipo_badge(tipo: str) -> str:
    bg, fg = TIPO_COLORS.get(tipo, ("#F1F5F9", "#64748B"))
    return (
        f'<span style="font-size:0.62rem;font-weight:700;color:{fg};background:{bg};'
        f'border:1px solid {fg}33;padding:1px 7px;border-radius:4px">{tipo}</span>'
    )

def _warning_dots(count: int) -> str:
    """3 dots: yellow for 1-2, red for 3, gray for unused."""
    dots = []
    for i in range(1, 4):
        if i < count:
            c = "#F59E0B"
        elif i == count:
            c = "#EF4444" if count == 3 else "#F59E0B"
        else:
            c = "#D1D5DB"
        dots.append(
            f'<span style="font-size:1.05rem;color:{c}">●</span>'
        )
    return "".join(dots)

ESTADO_COLOR = {
    "Recolectando evidencia": ("#FEF3C7", "#D97706", "#92400E"),
    "Enviado a Manpower":     ("#EDE9FE", "#7C3AED", "#4C1D95"),
    "Enviado a HRBP":         ("#FCE7F3", "#DB2777", "#831843"),
    "En espera de respuesta": ("#DBEAFE", "#2563EB", "#1E3A8A"),
    "Cerrado — favorable":    ("#D1FAE5", "#059669", "#064E3B"),
    "Cerrado — desfavorable": ("#FEE2E2", "#DC2626", "#7F1D1D"),
}
TIPOS_CONTRATO = ["Manpower", "Rappi directo"]

ESTADOS_POR_TIPO = {
    "Manpower":      ["Recolectando evidencia", "Enviado a Manpower",
                      "En espera de respuesta", "Cerrado — favorable", "Cerrado — desfavorable"],
    "Rappi directo": ["Recolectando evidencia", "Enviado a HRBP",
                      "En espera de respuesta", "Cerrado — favorable", "Cerrado — desfavorable"],
}

def _estados(tipo: str) -> list:
    return ESTADOS_POR_TIPO.get(tipo, ESTADOS_POR_TIPO["Manpower"])

# ════════════════════════════════════════════════════════════════════════════
# 4a — LLAMADOS DE ATENCIÓN
# ════════════════════════════════════════════════════════════════════════════
st.markdown(
    '<div style="font-size:1rem;font-weight:800;color:#0F172A;margin-bottom:0.3rem">'
    '⚠️ Llamados de atención</div>'
    '<div style="font-size:0.77rem;color:#64748B;margin-bottom:0.8rem">'
    'Al tercer llamado se inicia proceso disciplinario formal. '
    'El flujo varía según el tipo de contrato del farmer.</div>',
    unsafe_allow_html=True
)

all_llamados = get_all_llamados()

# Group by farmer
from collections import defaultdict
llamados_by_farmer: dict = defaultdict(list)
for ll in all_llamados:
    llamados_by_farmer[ll["farmer_email"]].append(ll)

if llamados_by_farmer:
    disc_emails = {r["farmer_email"] for r in get_all_disciplinarios()}

    for fem, lls in sorted(llamados_by_farmer.items(),
                            key=lambda x: -len(x[1])):
        fname     = FARMER_NAMES.get(fem, fem.split("@")[0].title())
        count     = len(lls)
        tipo      = lls[0]["tipo_contrato"]
        tipo_html = _tipo_badge(tipo)
        dots_html = _warning_dots(count)
        border    = "#EF4444" if count >= 3 else "#F59E0B" if count == 2 else "#E5E7EB"
        bg_card   = "#FEF2F2" if count >= 3 else "#FFFBEB" if count == 2 else "#FFFFFF"

        with st.expander(f"{fname} — {count}/3 llamados", expanded=(count >= 2)):
            # Header card
            st.markdown(
                f'<div style="background:{bg_card};border:1px solid {border};'
                f'border-radius:10px;padding:0.75rem 1rem;margin-bottom:0.6rem;'
                f'display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">'
                f'<div style="display:flex;align-items:center;gap:10px">'
                f'<span style="font-weight:700;color:#0F172A;font-size:0.9rem">{fname}</span>'
                f'{tipo_html}'
                f'</div>'
                f'<div style="display:flex;align-items:center;gap:6px">'
                f'{dots_html}'
                f'<span style="font-size:0.72rem;color:#6B7280;margin-left:4px">'
                f'{count} de 3 llamados</span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True
            )

            # Alerta 3 llamados
            if count >= 3 and fem not in disc_emails:
                st.markdown(
                    '<div style="background:#FEF2F2;border:1px solid #FECACA;border-left:4px solid #EF4444;'
                    'border-radius:8px;padding:0.65rem 1rem;margin-bottom:0.6rem;font-size:0.82rem;color:#7F1D1D">'
                    '<b>🔴 Tercer llamado alcanzado.</b> Corresponde iniciar proceso disciplinario formal.'
                    '</div>',
                    unsafe_allow_html=True
                )
                if st.button("Iniciar proceso disciplinario formal →",
                             key=f"inic_{fem}", type="primary"):
                    st.session_state[f"_prefill_disc_{fem}"] = True
                    st.rerun()

            # Tipo contrato hint
            if tipo == "Manpower":
                st.caption("🔵 Manpower: escalar a través del coordinador Manpower asignado al equipo.")
            else:
                st.caption("🟠 Rappi directo: escalar a través de HRBP de Rappi Colombia/UY.")

            # List of warnings
            for ll in sorted(lls, key=lambda x: x["numero"]):
                num   = ll["numero"]
                fecha = ll["fecha"]
                motiv = ll["motivo"] or "Sin motivo registrado"
                dot_c = "#EF4444" if num == 3 else "#F59E0B"
                st.markdown(
                    f'<div style="display:flex;align-items:flex-start;gap:10px;'
                    f'padding:6px 0;border-bottom:1px solid #F1F5F9">'
                    f'<span style="font-size:1rem;color:{dot_c};flex-shrink:0">●</span>'
                    f'<div>'
                    f'<div style="font-size:0.82rem;font-weight:600;color:#374151">'
                    f'Llamado #{num} — {fecha}</div>'
                    f'<div style="font-size:0.76rem;color:#6B7280">{motiv}</div>'
                    f'</div>'
                    f'<div style="margin-left:auto;flex-shrink:0">'
                    f'</div></div>',
                    unsafe_allow_html=True
                )
                if st.button("✕", key=f"del_ll_{ll['id']}", help="Eliminar este llamado"):
                    delete_llamado(ll["id"])
                    st.rerun()

else:
    st.markdown(
        '<div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:10px;'
        'padding:0.9rem 1.2rem;color:#065F46;font-size:0.85rem">'
        '✅ No hay llamados de atención registrados.</div>',
        unsafe_allow_html=True
    )

# ── Registrar nuevo llamado ───────────────────────────────────────────────────
st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)
with st.expander("➕ Registrar llamado de atención", expanded=False):
    all_farmers_sorted = sorted(
        {FARMER_NAMES.get(e, e): e for e in ACTIVE_FARMERS}.items()
    )
    nl_c1, nl_c2 = st.columns(2)
    nl_name = nl_c1.selectbox(
        "Farmer", [n for n, _ in all_farmers_sorted], key="nl_farmer"
    )
    nl_tipo = nl_c2.selectbox("Tipo de contrato", TIPOS_CONTRATO, key="nl_tipo")

    nl_email = dict(all_farmers_sorted)[nl_name]
    farmer_llamados = llamados_by_farmer.get(nl_email, [])
    next_num = len(farmer_llamados) + 1

    nl_c3, nl_c4 = st.columns(2)
    nl_num  = nl_c3.selectbox(
        "Número de llamado", [1, 2, 3],
        index=min(next_num - 1, 2), key="nl_num"
    )
    nl_fecha = nl_c4.text_input(
        "Fecha (AAAA-MM-DD)", value=today.isoformat(), key="nl_fecha"
    )
    nl_motivo = st.text_area(
        "Motivo del llamado", height=80, key="nl_motivo",
        placeholder="Describe brevemente la causa (ej: ATT < 90% por 2 semanas consecutivas)"
    )

    if st.button("✅ Registrar llamado", type="primary", key="nl_save"):
        save_llamado(nl_email, nl_num, nl_fecha, nl_motivo, nl_tipo)
        st.success(f"Llamado #{nl_num} registrado para {nl_name} ✅")
        st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# 4b — PROCESOS DISCIPLINARIOS FORMALES
# ════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(
    '<div style="font-size:1rem;font-weight:800;color:#0F172A;margin-bottom:0.6rem">'
    '🔒 Procesos disciplinarios formales</div>',
    unsafe_allow_html=True
)

disciplinarios = get_all_disciplinarios()

if disciplinarios:
    for rec in disciplinarios:
        fname  = FARMER_NAMES.get(rec["farmer_email"], rec["farmer_email"])
        estado = rec["estado"]
        tipo   = rec.get("tipo_contrato", "Manpower")
        bg, fc, tc = ESTADO_COLOR.get(estado, ("#F1F5F9", "#64748B", "#0F172A"))

        vencimiento = ""
        if rec.get("fecha_limite"):
            try:
                fl     = date.fromisoformat(rec["fecha_limite"])
                dias_v = (fl - today).days
                vc     = "#EF4444" if dias_v <= 2 else "#F59E0B" if dias_v <= 5 else "#059669"
                vencimiento = (
                    f'<span style="font-size:0.72rem;color:{vc};font-weight:600">'
                    f'⏰ Vence en {dias_v}d ({fl.strftime("%d/%m")})</span>'
                )
            except Exception:
                pass

        with st.expander(f"{fname} — {estado}", expanded=False):
            tipo_html = _tipo_badge(tipo)
            inicio_html = (
                f'<span style="font-size:0.78rem;color:#6B7280">Inicio: {rec["fecha_inicio"]}</span>'
                if rec.get("fecha_inicio") else ""
            )
            pp_html = (
                f'<div style="font-size:0.8rem;color:#374151;margin-top:8px">'
                f'<b>Próximo paso:</b> {rec["proximo_paso"]}</div>'
                if rec.get("proximo_paso") else ""
            )
            notas_html = (
                f'<div style="font-size:0.78rem;color:#6B7280;margin-top:4px;font-style:italic">'
                f'{rec["notas"]}</div>'
                if rec.get("notas") else ""
            )
            st.markdown(
                f'<div style="background:{bg};border-radius:8px;padding:0.8rem 1rem;margin-bottom:0.8rem">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
                f'<span style="font-weight:700;color:{tc};font-size:0.95rem">{fname}</span>'
                f'{tipo_html}'
                f'</div>'
                f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:4px">'
                f'<span style="font-size:0.78rem;color:{fc};background:white;'
                f'border-radius:6px;padding:2px 8px;font-weight:600">{estado}</span>'
                f'{inicio_html}{vencimiento}'
                f'</div>'
                f'{pp_html}{notas_html}'
                f'</div>',
                unsafe_allow_html=True
            )

            # Tipo contrato hint
            if tipo == "Manpower":
                st.caption("🔵 Proceso a través del coordinador Manpower.")
            else:
                st.caption("🟠 Proceso a través de HRBP Rappi.")

            col_e1, col_e2, col_e3 = st.columns(3)
            # Tipo must be selected first — its value drives the valid estado list
            new_tipo = col_e1.selectbox(
                "Tipo contrato", TIPOS_CONTRATO,
                index=TIPOS_CONTRATO.index(tipo) if tipo in TIPOS_CONTRATO else 0,
                key=f"tipo_{rec['farmer_email']}"
            )
            _estados_edit = _estados(new_tipo)
            _est_idx = (_estados_edit.index(estado)
                        if estado in _estados_edit else 0)
            new_estado = col_e2.selectbox(
                "Estado", _estados_edit,
                index=_est_idx,
                key=f"est_{rec['farmer_email']}"
            )
            new_fl = col_e3.text_input(
                "Fecha límite (AAAA-MM-DD)", value=rec.get("fecha_limite", ""),
                key=f"fl_{rec['farmer_email']}"
            )
            new_pp    = st.text_input("Próximo paso", value=rec.get("proximo_paso", ""),
                                      key=f"pp_{rec['farmer_email']}")
            new_notas = st.text_area("Notas", value=rec.get("notas", ""), height=80,
                                     key=f"nt_{rec['farmer_email']}")

            col_s, col_d = st.columns([3, 1])
            if col_s.button("💾 Guardar cambios", key=f"sv_{rec['farmer_email']}",
                            use_container_width=True):
                save_disciplinario(rec["farmer_email"], new_estado,
                                   rec.get("fecha_inicio", ""),
                                   new_pp, new_fl, new_notas, new_tipo)
                st.success("Guardado ✅")
                st.rerun()
            if col_d.button("🗑 Cerrar proceso", key=f"dl_{rec['farmer_email']}",
                            use_container_width=True):
                delete_disciplinario(rec["farmer_email"])
                st.rerun()
else:
    st.markdown(
        '<div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:10px;'
        'padding:0.9rem 1.2rem;color:#065F46;font-size:0.85rem">'
        '✅ No hay procesos disciplinarios formales activos.</div>',
        unsafe_allow_html=True
    )

# ── Nuevo proceso formal ──────────────────────────────────────────────────────
st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)

# Check if pre-filled from llamados "iniciar proceso" button
_prefill_email = next(
    (em for em in ACTIVE_FARMERS
     if st.session_state.get(f"_prefill_disc_{em}")), None
)
_prefill_open = _prefill_email is not None

with st.expander("➕ Registrar nuevo proceso disciplinario formal",
                 expanded=_prefill_open):
    existing_emails = {r["farmer_email"] for r in disciplinarios}
    available       = {FARMER_NAMES.get(e, e): e
                       for e in sorted(ACTIVE_FARMERS) if e not in existing_emails}

    if not available:
        st.info("Todos los farmers activos ya tienen proceso registrado.")
    else:
        # If opened from llamados alert, pre-select that farmer
        _prefill_name = (FARMER_NAMES.get(_prefill_email, _prefill_email)
                         if _prefill_email and _prefill_email in ACTIVE_FARMERS else None)
        _avail_names  = list(available.keys())
        _default_idx  = (_avail_names.index(_prefill_name)
                         if _prefill_name and _prefill_name in _avail_names else 0)

        col_n1, col_n2, col_n3 = st.columns(3)
        sel_name = col_n1.selectbox("Farmer", _avail_names,
                                    index=_default_idx, key="new_disc_farmer")
        sel_tipo = col_n2.selectbox("Tipo de contrato", TIPOS_CONTRATO,
                                    key="new_disc_tipo")
        # Estado options are filtered by tipo — no "Enviado a Manpower" for Rappi directo
        _estados_init = _estados(sel_tipo)
        sel_estado = col_n3.selectbox("Estado inicial", _estados_init,
                                      key="new_disc_estado")
        col_n4, col_n5 = st.columns(2)
        sel_fi = col_n4.text_input("Fecha de inicio (AAAA-MM-DD)",
                                    value=today.isoformat(), key="new_disc_fi")
        sel_fl = col_n5.text_input("Fecha límite (AAAA-MM-DD)", key="new_disc_fl")
        sel_pp    = st.text_input("Próximo paso", key="new_disc_pp")
        sel_notas = st.text_area("Notas iniciales", height=80, key="new_disc_notas")

        if st.button("✅ Registrar proceso formal", type="primary", key="new_disc_save"):
            email_sel = available[sel_name]
            save_disciplinario(email_sel, sel_estado, sel_fi, sel_pp,
                               sel_fl, sel_notas, sel_tipo)
            # Clear prefill flag
            st.session_state.pop(f"_prefill_disc_{email_sel}", None)
            st.success(f"Proceso registrado para {sel_name} ✅")
            st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 5 — DOCUMENTO WBR SEMANAL
# ════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(
    '<div style="font-size:1rem;font-weight:800;color:#0F172A;margin-bottom:0.3rem">'
    '📄 Documento WBR — Foco Semanal</div>'
    '<div style="font-size:0.78rem;color:#64748B;margin-bottom:0.8rem">'
    'Cargá aquí tu WBR actualizado cada semana. El dashboard extrae automáticamente '
    'el plan de acción de cada KPI y lo vincula con los datos del equipo.</div>',
    unsafe_allow_html=True
)

# ── Parser ────────────────────────────────────────────────────────────────────
def _parse_wbr_docx(file_bytes: bytes) -> dict:
    """Parse a WBR .docx and return structured section data."""
    try:
        import io as _io
        from docx import Document as _Doc
        doc = _Doc(_io.BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    except Exception as e:
        return {"error": str(e), "sections": {}}

    SECTION_MARKERS = [
        ("productividad", ["PERFORMANCE", "Productividad"]),
        ("pitch",         ["PITCH INTEGRAL"]),
        ("churn",         ["ASSORTMENT", "Churn"]),
        ("ads",           ["PROFITABILITY", "Ads"]),
        ("md",            ["AFFORDABILITY", "MD"]),
        ("catalog",       ["CATALOG SCORE"]),
    ]

    result = {
        "title":       paragraphs[0] if paragraphs else "",
        "uploaded_at": datetime.now().isoformat(),
        "week_key":    week_key,
        "sections":    {},
    }

    current_sec   = None
    plan_lines    = []
    update_lines  = []  # "→ Para semana" paragraphs
    in_plan       = False

    def _flush():
        if current_sec and (plan_lines or update_lines):
            result["sections"][current_sec] = {
                "plan":    "\n".join(plan_lines).strip(),
                "updates": "\n".join(update_lines).strip(),
            }

    for para in paragraphs:
        p_up = para.upper()

        # Detect section header
        matched_sec = None
        for sec_key, markers in SECTION_MARKERS:
            if any(m.upper() in p_up for m in markers) and "PLAN DE ACCIÓN" not in p_up:
                matched_sec = sec_key
                break

        if matched_sec:
            _flush()
            current_sec  = matched_sec
            plan_lines   = []
            update_lines = []
            in_plan      = False
            continue

        # Detect plan de acción start
        if "PLAN DE ACCIÓN" in p_up and current_sec:
            in_plan = True
            rest = para.split(":", 1)[-1].strip()
            if rest:
                plan_lines.append(rest)
            continue

        if not in_plan or not current_sec:
            continue

        # "→ Para semana" updates go into separate bucket
        if para.startswith("→"):
            update_lines.append(para)
        else:
            plan_lines.append(para)

    _flush()
    return result


def _highlight_farmers(text: str, active_names: set) -> str:
    """Wrap known farmer first names in bold orange spans."""
    import re
    for name in sorted(active_names, key=len, reverse=True):
        first = name.split()[0]
        if len(first) < 3:
            continue
        pattern = re.compile(re.escape(first), re.IGNORECASE)
        text = pattern.sub(
            f'<b style="color:#F59E0B">{first}</b>', text, count=5
        )
    return text


# ── Section config ────────────────────────────────────────────────────────────
WBR_SECTIONS = [
    {"key": "productividad", "icon": "📞", "label": "Productividad",    "color": "#4A6CF7"},
    {"key": "pitch",         "icon": "🎯", "label": "Pitch Integral",   "color": "#9333EA"},
    {"key": "churn",         "icon": "🔄", "label": "Churn / Assortment","color": "#059669"},
    {"key": "ads",           "icon": "📢", "label": "ADS / Profitability","color": "#F59E0B"},
    {"key": "md",            "icon": "💰", "label": "MD / Affordability", "color": "#EF4444"},
    {"key": "catalog",       "icon": "📦", "label": "Catalog Score",    "color": "#64748B"},
]

active_farmer_names = {
    FARMER_NAMES.get(e, e.split("@")[0].title())
    for e in ACTIVE_FARMERS
}

# ── Load persisted doc for this week ─────────────────────────────────────────
wbr_doc = st.session_state.get("_wbr_doc_cache") or load_wbr_doc(week_key)
if wbr_doc and "_wbr_doc_cache" not in st.session_state:
    st.session_state["_wbr_doc_cache"] = wbr_doc

# ── Upload widget (supervisor only) ──────────────────────────────────────────
with st.expander(
    "📤 Cargar nuevo WBR (.docx)" if not wbr_doc else
    f"📤 Reemplazar WBR ({wbr_doc.get('title','')[:60]}…)",
    expanded=not bool(wbr_doc)
):
    uploaded = st.file_uploader(
        "Seleccioná el archivo WBR actualizado de esta semana",
        type=["docx"],
        key="wbr_docx_upload",
        label_visibility="collapsed",
    )
    if uploaded is not None:
        # Use file name + size as signature to process only once per file
        file_sig = f"{uploaded.name}_{uploaded.size}"
        if st.session_state.get("_wbr_last_sig") != file_sig:
            with st.spinner("Procesando documento..."):
                parsed = _parse_wbr_docx(uploaded.read())
            if "error" in parsed:
                st.error(f"Error al leer el documento: {parsed['error']}")
            else:
                save_wbr_doc(week_key, parsed)
                st.session_state["_wbr_last_sig"]   = file_sig
                st.session_state["_wbr_doc_cache"]  = parsed
                wbr_doc = parsed
                st.success(f"WBR cargado: **{parsed['title']}** ✅")
        else:
            st.success(f"WBR activo: **{wbr_doc.get('title','')}** ✅")

# ── Display parsed doc ────────────────────────────────────────────────────────
if not wbr_doc:
    st.markdown(
        '<div style="background:#F8FAFC;border:1px dashed #CBD5E1;border-radius:12px;'
        'padding:1.5rem;text-align:center;color:#94A3B8;font-size:0.85rem">'
        '📄 Aún no hay documento WBR cargado para esta semana.<br>'
        '<span style="font-size:0.75rem">Cargá el .docx actualizado usando el panel de arriba.</span>'
        '</div>',
        unsafe_allow_html=True
    )
else:
    # Metadata bar
    uploaded_dt = wbr_doc.get("uploaded_at", "")
    try:
        dt_obj = datetime.fromisoformat(uploaded_dt)
        uploaded_dt = dt_obj.strftime("%d %b %Y, %H:%M").lstrip("0")
    except Exception:
        pass

    st.markdown(
        '<div style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:10px;'
        'padding:0.6rem 1rem;margin-bottom:0.8rem;display:flex;align-items:center;gap:10px">'
        '<span style="font-size:1.1rem">📄</span>'
        f'<div><div style="font-weight:700;color:#0F172A;font-size:0.85rem">'
        f'{wbr_doc.get("title","Documento WBR")}</div>'
        f'<div style="font-size:0.72rem;color:#64748B">Semana {week_key} · '
        f'Cargado: {uploaded_dt}</div></div>'
        '</div>',
        unsafe_allow_html=True
    )

    sections = wbr_doc.get("sections", {})

    for cfg in WBR_SECTIONS:
        sec = sections.get(cfg["key"])
        if not sec:
            continue

        plan_text    = sec.get("plan", "").strip()
        update_text  = sec.get("updates", "").strip()

        if not plan_text and not update_text:
            continue

        color = cfg["color"]
        label = cfg["label"]
        icon  = cfg["icon"]

        with st.expander(f"{icon} {label}", expanded=(cfg["key"] in ("productividad","pitch","churn"))):

            # "→ Para semana" updates shown first as the most recent focus
            if update_text:
                for line in update_text.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    line_hl = _highlight_farmers(line, active_farmer_names)
                    st.markdown(
                        f'<div style="background:{color}0D;border-left:3px solid {color};'
                        'border-radius:0 8px 8px 0;padding:0.65rem 1rem;margin-bottom:0.4rem;'
                        'font-size:0.82rem;color:#1E293B;line-height:1.6">'
                        f'<span style="font-weight:700;color:{color}">Foco actual →</span> '
                        f'{line_hl}</div>',
                        unsafe_allow_html=True
                    )

            # Original plan de acción
            if plan_text:
                plan_hl = _highlight_farmers(
                    plan_text.replace("\n", "<br>"), active_farmer_names
                )
                st.markdown(
                    '<div style="background:#F8FAFC;border-radius:8px;padding:0.75rem 1rem;'
                    'margin-top:0.4rem;font-size:0.8rem;color:#374151;line-height:1.7;'
                    'border:1px solid #E5E7EB">'
                    f'<div style="font-size:0.67rem;font-weight:700;color:#9CA3AF;'
                    'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px">'
                    'Plan de acción</div>'
                    f'{plan_hl}</div>',
                    unsafe_allow_html=True
                )
