from __future__ import annotations
import streamlit as st
import io
import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.loader import refresh_net_rev_adj
from core.metrics import (
    get_all_semaforos, tier_farmer, EMOJI, COLOR_HEX,
    calcular_compensacion_completa, generar_recomendaciones
)
from core.db import get_consecutive_red_weeks
from core.auth import require_auth, render_topbar
from core.style import inject_global_css


@st.cache_data(show_spinner=False)
def _parse_conversion_raw(raw_json: str) -> pd.DataFrame:
    return pd.read_json(io.StringIO(raw_json))


def _is_si(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.upper() == "SI"


def _is_one(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce") == 1


st.set_page_config(
    page_title="Vista Farmer — Rappi Farmers",
    page_icon="🚀",
    layout="wide",
)
st.markdown(inject_global_css(), unsafe_allow_html=True)
email_auth, is_supervisor = require_auth()
render_topbar()


if "farmers_data" not in st.session_state:
    from core.db import load_latest_state
    latest = load_latest_state()
    if latest:
        st.session_state["farmers_data"]  = latest["farmers_data"]
        st.session_state["dia_corte"]     = latest["dia_corte"]
        st.session_state["dias_mes"]      = latest["dias_mes"]
        if latest.get("productividad_raw"):
            try:
                df_raw = pd.read_json(io.StringIO(latest["productividad_raw"]))
                df_raw.columns = [int(c) for c in df_raw.columns]
                st.session_state["_productividad_raw"] = df_raw
            except Exception:
                pass
    else:
        st.warning("⏳ El supervisor aún no ha cargado datos para este período. Vuelve más tarde o contacta a Oscar Pedraza.")
        st.stop()

farmers_data = st.session_state["farmers_data"]
dia_corte    = st.session_state.get("dia_corte", 13)
dias_mes     = st.session_state.get("dias_mes", 31)
progreso_pct = ((dia_corte - 1) / dias_mes) * 100
try:
    refresh_net_rev_adj(farmers_data, dias_mes)
except Exception:
    pass

# ── Farmer selector ───────────────────────────────────────────────────────────
names        = {data.get("name", em): em for em, data in farmers_data.items()}
sorted_names = sorted(names.keys())

if is_supervisor:
    selected_name = st.selectbox("👤 Selecciona un farmer", sorted_names)
    farmer_email  = names[selected_name]
else:
    # Non-supervisors are locked to their own profile — no selectbox
    email_auth_clean = email_auth.strip().lower()
    farmer_email = next(
        (em for em in farmers_data if em.strip().lower() == email_auth_clean),
        None
    )
    if farmer_email is None:
        st.error(
            "⚠️ Tu perfil no fue encontrado en los datos del equipo. "
            "Contacta a Oscar Pedraza para verificar que tu email esté registrado."
        )
        st.stop()
    selected_name = farmers_data[farmer_email].get("name", farmer_email)
    st.markdown(
        f'<div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:10px;'
        f'padding:0.6rem 1rem;margin-bottom:0.8rem;display:inline-block;'
        f'font-size:0.9rem;color:#374151;font-weight:600">'
        f'👤 Tu perfil — {selected_name}</div>',
        unsafe_allow_html=True
    )

data = farmers_data[farmer_email]
sems         = get_all_semaforos(data)
tier         = tier_farmer(sems)
comp         = calcular_compensacion_completa(data)

# ── Header ────────────────────────────────────────────────────────────────────
tier_color = COLOR_HEX.get(tier, "#9CA3AF")
var_pct    = comp.get("variable_pct", 0)
qualifies  = comp.get("qualifies", True)
qual_badge = "" if qualifies else " ⛔"
var_color  = "#00B341" if var_pct >= 80 else "#F59E0B" if var_pct >= 50 else "#EF4444"

st.markdown(f"""
<div class="rb-page-header" style="display:flex;justify-content:space-between;align-items:center;border-left-color:{tier_color}">
    <div>
        <h1 style="font-size:1.4rem">
            {EMOJI.get(tier,'⚪')} {selected_name}{qual_badge}
        </h1>
        <p>Corte día {dia_corte} · {progreso_pct:.1f}% del mes</p>
    </div>
    <div style="text-align:right">
        <div style="font-size:2rem;font-weight:800;color:{var_color}">{var_pct:.0f}%</div>
        <div style="font-size:0.75rem;color:#9CA3AF">variable ganado</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── KPI Badges ────────────────────────────────────────────────────────────────
st.markdown("#### Métricas del período")

metric_defs = [
    ("Churn",    "ATT_Churn",         "decimal", "Churn"),
    ("MD Total", "ATT_MD_Total",      "decimal", "MD Total"),
    ("MD Pro",   "ATT_MD_Pro",        "decimal", "MD Pro"),
    ("Ads Book", "ATT_Book",          "decimal", "Ads Bookings"),
    ("Ads Rev",  "ATT_Rev_real",      "decimal", "Ads Revenue"),
    ("Net Rev",  "Net_Rev_Adj",       "pp",      "Net Rev Adj"),
    ("Pitch",    "Pitch_Pct",         "decimal", "Pitch Integral"),
    ("No Cont.", "pct_no_contactados","pct_raw", "No Contactados"),
    ("Reactiv.", "Reactivaciones",    "count",   "Reactivaciones"),
]

metric_map_red = {
    "Churn": "ATT_Churn", "MD Total": "ATT_MD_Total",
    "MD Pro": "ATT_MD_Pro", "Ads Revenue": "ATT_Rev_real"
}

cols = st.columns(9)
for col, (label, key, fmt, sem_key) in zip(cols, metric_defs):
    val   = data.get(key)
    sem   = sems.get(sem_key, "gray")
    color = COLOR_HEX.get(sem, "#9CA3AF")

    if val is None:                          display = "S/D"
    elif fmt == "decimal":                   display = f"{val*100:.0f}%"
    elif fmt == "pp":                        display = f"{val:+.1f}pp"
    elif fmt == "pct_raw":                   display = f"{val:.0f}%"
    else:                                    display = str(int(val))

    consec = get_consecutive_red_weeks(farmer_email, metric_map_red[sem_key]) \
             if sem_key in metric_map_red else 0
    consec_txt = f"<div style='font-size:0.62rem;color:#EF4444'>{consec}w 🔴</div>" \
                 if consec >= 2 else ""

    with col:
        st.markdown(f"""
        <div style="background:#FFFFFF;border-radius:10px;padding:0.6rem 0.4rem;
                    border-top:3px solid {color};text-align:center;min-height:80px;
                    border:1px solid #E5E7EB;box-shadow:0 2px 6px rgba(0,0,0,0.05)">
            <div style="font-size:0.6rem;color:#6B7280;margin-bottom:3px;
                        text-transform:uppercase;letter-spacing:0.5px;font-weight:600">{label}</div>
            <div style="font-size:1.2rem;font-weight:800;color:{color};line-height:1.1">{display}</div>
            <div style="font-size:0.68rem;color:#9CA3AF">{EMOJI.get(sem,'⚪')}</div>
            {consec_txt}
        </div>
        """, unsafe_allow_html=True)

# ── Productividad cruzada ─────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Gestión de follows por palanca")

palancas = [
    ("🔄 Churn",   "churn_follows", "churn_contactados", "Churn"),
    ("💰 MD",      "md_follows",    "md_contactados",    "MD Total"),
    ("📢 Ads",     "ads_follows",   "ads_contactados",   "Ads Revenue"),
]

prod_cols = st.columns(3)
for col, (label, fk, ck, sk) in zip(prod_cols, palancas):
    follows     = int(data.get(fk) or 0)
    contactados = int(data.get(ck) or 0)
    no_cont     = follows - contactados
    pct_cont    = round(contactados / follows * 100) if follows > 0 else 0
    sem         = sems.get(sk, "gray")
    color       = COLOR_HEX.get(sem, "#9CA3AF")

    with col:
        st.markdown(f"""
        <div style="background:#FFFFFF;border-radius:10px;padding:0.9rem 1rem;
                    border-left:4px solid {color};border:1px solid #E5E7EB;
                    box-shadow:0 2px 6px rgba(0,0,0,0.05)">
            <div style="font-weight:700;color:#1A1A1A;margin-bottom:0.5rem;font-size:0.9rem">{label}</div>
            <div style="display:flex;justify-content:space-between;margin-bottom:2px">
                <span style="color:#6B7280;font-size:0.82rem">Follows</span>
                <span style="font-weight:700;color:#1A1A1A">{follows}</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:2px">
                <span style="color:#6B7280;font-size:0.82rem">Contactados</span>
                <span style="font-weight:700;color:#00B341">{contactados}</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                <span style="color:#6B7280;font-size:0.82rem">Sin contactar</span>
                <span style="font-weight:700;color:#EF4444">{no_cont}</span>
            </div>
            <div style="background:#E5E7EB;border-radius:4px;height:5px">
                <div style="background:#00C9A7;width:{pct_cont}%;height:5px;border-radius:4px"></div>
            </div>
            <div style="font-size:0.72rem;color:#9CA3AF;margin-top:3px">{pct_cont}% efectividad</div>
        </div>
        """, unsafe_allow_html=True)

# ── Contactabilidad general ───────────────────────────────────────────────────
total_f      = int(data.get("total_follows") or 0)
no_ct        = int(data.get("no_contactados") or 0)
pct_nc       = float(data.get("pct_no_contactados") or 0)

# Recurrencia de no contacto (nuevas métricas por cuenta única)
total_cuentas    = int(data.get("total_cuentas") or 0)
cuentas_no       = int(data.get("cuentas_no_contactadas") or 0)
pct_cuentas_no   = float(data.get("pct_cuentas_no_contactadas") or 0)
cuentas_recurr   = int(data.get("cuentas_recurrentes_no") or 0)
pct_recurr       = float(data.get("pct_recurrencia_no") or 0)
weekly_no        = data.get("weekly_no_contacto") or []

# Alert banner
if pct_cuentas_no > 40:
    st.error(f"🔴 **Contactabilidad crítica:** {cuentas_no} de {total_cuentas} cuentas sin contactar ({pct_cuentas_no:.0f}%). Prioridad urgente.")
elif pct_cuentas_no > 25:
    st.warning(f"🟡 Contactabilidad baja: {cuentas_no} cuentas sin contactar ({pct_cuentas_no:.0f}%). Revisar agenda.")

# Cards de contactabilidad
c_nc1, c_nc2, c_nc3 = st.columns(3)
nc_color = "#00B341" if pct_cuentas_no <= 20 else "#F59E0B" if pct_cuentas_no <= 35 else "#EF4444"
# Recurrencia: MAYOR ES MEJOR — identifica marcas candidatas a limpiar del portafolio
rc_color = "#EF4444" if pct_recurr < 10 else "#F59E0B" if pct_recurr < 20 else "#00B341"

with c_nc1:
    st.markdown(f"""
    <div style="background:#FFFFFF;border-radius:12px;padding:1rem 1.2rem;
                border-top:4px solid {nc_color};border:1px solid #E5E7EB;
                box-shadow:0 2px 8px rgba(0,0,0,0.06)">
        <div style="font-size:0.65rem;color:#6B7280;text-transform:uppercase;letter-spacing:0.5px;font-weight:600">
            📵 % Cuentas sin contactar
        </div>
        <div style="font-size:2rem;font-weight:800;color:{nc_color};margin:0.2rem 0">
            {pct_cuentas_no:.1f}%
        </div>
        <div style="font-size:0.78rem;color:#374151">
            {cuentas_no} cuentas / {total_cuentas} totales
        </div>
        <div style="font-size:0.7rem;color:#9CA3AF;margin-top:2px">
            Por cuenta única (no por fila de follow)
        </div>
    </div>""", unsafe_allow_html=True)

with c_nc2:
    st.markdown(f"""
    <div style="background:#FFFFFF;border-radius:12px;padding:1rem 1.2rem;
                border-top:4px solid {rc_color};border:1px solid #E5E7EB;
                box-shadow:0 2px 8px rgba(0,0,0,0.06)">
        <div style="font-size:0.65rem;color:#6B7280;text-transform:uppercase;letter-spacing:0.5px;font-weight:600">
            🔁 % Recurrencia sin contactar
        </div>
        <div style="font-size:2rem;font-weight:800;color:{rc_color};margin:0.2rem 0">
            {pct_recurr:.1f}%
        </div>
        <div style="font-size:0.78rem;color:#374151">
            {cuentas_recurr} cuentas sin contactar en 2+ semanas
        </div>
        <div style="font-size:0.7rem;color:#00B341;margin-top:2px;font-weight:600">
            ↑ Mayor = mejor — candidatas a salir del portafolio
        </div>
    </div>""", unsafe_allow_html=True)

with c_nc3:
    # Weekly breakdown mini-table
    if weekly_no:
        wk_html = "".join(
            f'<div style="display:flex;justify-content:space-between;padding:3px 0;'
            f'border-bottom:1px solid #F3F4F6">'
            f'<span style="color:#6B7280;font-size:0.75rem">Semana {w["week"]}</span>'
            f'<span style="font-weight:700;font-size:0.8rem;color:{"#EF4444" if w["pct"]>35 else "#F59E0B" if w["pct"]>20 else "#00B341"}">'
            f'{w["no_cuentas"]}/{w["total_cuentas"]} · {w["pct"]:.0f}%</span></div>'
            for w in weekly_no
        )
        st.markdown(f"""
        <div style="background:#FFFFFF;border-radius:12px;padding:1rem 1.2rem;
                    border-top:4px solid #4A6CF7;border:1px solid #E5E7EB;
                    box-shadow:0 2px 8px rgba(0,0,0,0.06)">
            <div style="font-size:0.65rem;color:#6B7280;text-transform:uppercase;
                        letter-spacing:0.5px;font-weight:600;margin-bottom:6px">
                📅 No contactadas por semana
            </div>
            {wk_html}
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background:#FFFFFF;border-radius:12px;padding:1rem 1.2rem;
                    border-top:4px solid #9CA3AF;border:1px solid #E5E7EB">
            <div style="font-size:0.65rem;color:#6B7280;text-transform:uppercase;font-weight:600">
                📅 Por semana
            </div>
            <div style="color:#9CA3AF;font-size:0.8rem;margin-top:4px">Sin datos semanales</div>
        </div>""", unsafe_allow_html=True)

# ── Variable summary (sin gauge) ──────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 💰 Estado de tu variable")

rs       = comp.get("rs_ads", {})
rs_pct   = rs.get("pct", 0)
contribs = comp.get("contributions", {})
kpi_statuses = comp.get("kpi_statuses", {})

vc1, vc2, vc3, vc4, vc5, vc6 = st.columns(6)

with vc1:
    vc = "#00B341" if var_pct >= 80 else "#F59E0B" if var_pct >= 50 else "#EF4444"
    st.markdown(f"""
    <div style="background:#FFFFFF;border-radius:10px;padding:0.9rem;text-align:center;border:1px solid #E5E7EB;border-top:3px solid {vc};box-shadow:0 2px 6px rgba(0,0,0,0.05)">
        <div style="font-size:0.65rem;color:#6B7280;text-transform:uppercase;font-weight:600;letter-spacing:0.5px">Variable</div>
        <div style="font-size:1.8rem;font-weight:800;color:{vc}">{var_pct:.0f}%</div>
        <div style="font-size:0.68rem;color:#9CA3AF">{'⛔ Sin qualifier' if not qualifies else '✅ Qualifier OK'}</div>
    </div>""", unsafe_allow_html=True)

with vc2:
    rsc = "#00B341" if rs_pct >= 20 else "#F59E0B" if rs_pct > 0 else "#EF4444"
    st.markdown(f"""
    <div style="background:#FFFFFF;border-radius:10px;padding:0.9rem;text-align:center;border:1px solid #E5E7EB;border-top:3px solid {rsc};box-shadow:0 2px 6px rgba(0,0,0,0.05)">
        <div style="font-size:0.65rem;color:#6B7280;text-transform:uppercase;font-weight:600;letter-spacing:0.5px">RS ADS</div>
        <div style="font-size:1.8rem;font-weight:800;color:{rsc}">{rs_pct}%</div>
        <div style="font-size:0.68rem;color:#9CA3AF">{rs.get('label','—')[:18]}</div>
    </div>""", unsafe_allow_html=True)

kpi_defs = [
    ("ADS_Rev",  "Ads Rev 35%",  data.get("ATT_Rev_real")),
    ("MD_Total", "MD Total 20%", data.get("ATT_MD_Total")),
    ("MD_Pro",   "MD Pro 20%",   data.get("ATT_MD_Pro")),
    ("Churn",    "Churn 25%",    data.get("ATT_Churn")),
]
status_map = {"gana": ("🟢","#00B341"), "parcial": ("🟡","#F59E0B"),
              "no_gana": ("🔴","#EF4444"), "sin_dato": ("⚪","#9CA3AF")}

for col, (kpi, label, att_val) in zip([vc3, vc4, vc5, vc6], kpi_defs):
    icon, kcolor = status_map.get(kpi_statuses.get(kpi, "sin_dato"), ("⚪","#9CA3AF"))
    att_str      = f"{att_val*100:.0f}%" if att_val is not None else "S/D"
    contrib      = contribs.get(kpi)
    contrib_str  = f"+{contrib:.1f}pp" if contrib is not None else "—"
    with col:
        st.markdown(f"""
        <div style="background:#FFFFFF;border-radius:10px;padding:0.9rem;text-align:center;border:1px solid #E5E7EB;border-top:3px solid {kcolor};box-shadow:0 2px 6px rgba(0,0,0,0.05)">
            <div style="font-size:0.6rem;color:#6B7280;text-transform:uppercase;font-weight:600;letter-spacing:0.5px">{label}</div>
            <div style="font-size:1.4rem;font-weight:800;color:{kcolor}">{icon} {att_str}</div>
            <div style="font-size:0.68rem;color:#9CA3AF">{contrib_str} al var.</div>
        </div>""", unsafe_allow_html=True)

# ── Plan de acción — farmer-centric ──────────────────────────────────────────
st.markdown("---")
st.markdown("### 🎯 Tu plan de esta semana")
st.caption("Acciones concretas basadas en tus métricas de hoy")

recs = generar_recomendaciones(data, sems)

# Organise into priority buckets
urgent, normal = [], []
for r in recs:
    if "urgente" in r.lower() or "crítico" in r.lower() or "priorizar" in r.lower() \
       or "sin follows" in r.lower() or "pierde variable" in r.lower():
        urgent.append(r)
    else:
        normal.append(r)

if urgent:
    for r in urgent:
        st.error(r)
for r in normal:
    st.info(r)

# ── Aliados clave ─────────────────────────────────────────────────────────────
brands = data.get("brands_riesgo", [])
st.markdown("---")
st.markdown("### 🏪 Tus aliados con mayor potencial ADS")

if brands:
    st.caption(f"Brands activos con penetración < 70% — {len(brands)} oportunidades detectadas")
    cols_b = st.columns(min(len(brands), 5))
    for col, brand in zip(cols_b, brands[:5]):
        with col:
            st.markdown(f"""
            <div style="background:#FFF7ED;border:1px solid #FF6B00;border-radius:8px;
                        padding:0.5rem 0.4rem;text-align:center;font-size:0.78rem;
                        font-weight:600;color:#FF6B00">
                ⚡ {brand}
            </div>
            """, unsafe_allow_html=True)
    if len(brands) > 5:
        st.caption(f"… y {len(brands)-5} aliados más. Ver lista completa en Vista Equipo → Rankings.")
    st.markdown("""
    <div style="background:#F0FDF9;border-radius:8px;padding:0.7rem 1rem;
                border-left:3px solid #00C9A7;margin-top:0.5rem;font-size:0.82rem;color:#374151">
        💡 <b>Acción:</b> proponer inversión ADS a estos brands en la próxima visita.
        Son aliados activos con revenue significativo y baja penetración — el upsell más sencillo.
    </div>
    """, unsafe_allow_html=True)
else:
    st.success("✅ Sin aliados en riesgo de penetración identificados esta corrida.")

# ── Gap al próximo hito de variable ──────────────────────────────────────────
st.markdown("---")
st.markdown("### 📈 ¿Qué necesito para subir mi variable?")

att_ads = data.get("ATT_Rev_real")
gaps    = []

if not qualifies:
    prod = data.get("productividad_pct") or 0
    gaps.append(f"🔴 **Qualifier bloqueado:** tu productividad es {prod*100:.0f}% y necesitas ≥ 90%. "
                "Sin esto, el variable es **0%** sin importar tus ATTs. "
                "Contactar cada follow con Zoho Voice, Treble o Meets esta semana.")

if att_ads is not None and att_ads < 0.90:
    gap = (0.90 - att_ads) * 100
    gaps.append(f"📢 **Ads Revenue:** faltan **{gap:.1f} pp** para activar el Revenue Share ADS (mínimo 90%).")
elif att_ads is not None and att_ads < 1.00:
    gap = (1.00 - att_ads) * 100
    gaps.append(f"📢 **Ads Revenue:** faltan **{gap:.1f} pp** para subir al tier 20% RS ADS.")
elif att_ads is not None and att_ads < 1.20:
    gap = (1.20 - att_ads) * 100
    gaps.append(f"🔥 **Ads Revenue:** faltan **{gap:.1f} pp** para el tier máximo 30% RS ADS.")

for kpi, sem_key, label in [
    ("ATT_Churn",    "Churn",    "Churn"),
    ("ATT_MD_Total", "MD Total", "MD Total"),
    ("ATT_MD_Pro",   "MD Pro",   "MD Pro"),
]:
    v = data.get(kpi)
    if v is not None and v < 0.90 and sems.get(sem_key) == "red":
        gaps.append(f"⚠️ **{label}:** en {v*100:.0f}% — falta {(0.90-v)*100:.1f} pp para dejar de estar en rojo.")

if not gaps:
    target_90 = 90 - var_pct
    if target_90 <= 0:
        st.success(f"🏆 Tu variable está al {var_pct:.0f}%. Mantén el ritmo y apunta al Revenue Share ADS máximo.")
    else:
        st.info(f"Estás en {var_pct:.0f}% de variable. Necesitas {target_90:.0f} pp más para llegar al 90%.")
else:
    for g in gaps:
        st.markdown(f"- {g}")

# ── Conversión y falsa conversión ─────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📊 Actividad de pitches y conversión real")
st.caption("Fuente: pestaña Conversión del Maestro. Falsa conversión = pitch marcado como hecho pero sin cierre real.")

_conv_raw = st.session_state.get("_conversion_raw")

if not _conv_raw:
    st.info("📂 Sin datos de Conversión disponibles. Asegúrate de que el Maestro incluya la pestaña **Conversión** con las columnas FARMER, DATE, MARKDOWN, MD, ADS, BN, CHURN, ORD.")
else:
    try:
        _df_conv = _parse_conversion_raw(_conv_raw)

        if "FARMER" not in _df_conv.columns:
            st.info("La hoja Conversión no tiene columna FARMER.")
        else:
            _df_conv["FARMER"] = _df_conv["FARMER"].astype(str).str.strip().str.lower()
            _df_me = _df_conv[_df_conv["FARMER"] == farmer_email].copy()

            if _df_me.empty:
                st.info("Sin datos de pitches para este farmer en el período.")
            else:
                # Drop exact duplicates (safety net)
                _before = len(_df_me)
                _df_me = _df_me.drop_duplicates()
                _after = len(_df_me)
                if _before > _after:
                    st.caption(f"ℹ️ Se descartaron {_before - _after} filas duplicadas exactas del DETALLE.")

                PALANCAS_CONV = [
                    ("MD",    "MARKDOWN", "MD",  "💰", "#4A6CF7"),
                    ("ADS",   "ADS",      "BN",  "📢", "#9333EA"),
                    ("Churn", "CHURN",    "ORD", "🔄", "#F59E0B"),
                ]

                conv_cols = st.columns(3)
                for col_idx, (name, tip_col, real_col, icon, color) in enumerate(PALANCAS_CONV):
                    tip_vals  = _is_si(_df_me[tip_col])  if tip_col  in _df_me.columns else pd.Series(False, index=_df_me.index)
                    real_vals = _is_one(_df_me[real_col]) if real_col in _df_me.columns else pd.Series(False, index=_df_me.index)

                    pitches_hechos = int(tip_vals.sum())
                    cierres_reales = int(real_vals.sum())

                    # Falsa conversión: pitch hecho pero sin cierre
                    falsos = int((tip_vals & ~real_vals).sum())
                    conv_rate = round(cierres_reales / pitches_hechos * 100, 1) if pitches_hechos > 0 else 0
                    falsa_rate = round(falsos / pitches_hechos * 100, 1) if pitches_hechos > 0 else 0

                    c_real = "#00B341" if conv_rate >= 30 else "#F59E0B" if conv_rate >= 15 else "#EF4444"
                    c_falsa = "#EF4444" if falsa_rate > 60 else "#F59E0B" if falsa_rate > 30 else "#9CA3AF"

                    with conv_cols[col_idx]:
                        st.markdown(f"""
                        <div style="background:#FFFFFF;border-radius:12px;padding:1rem 1.1rem;
                                    border-top:4px solid {color};border:1px solid #E5E7EB;
                                    box-shadow:0 2px 8px rgba(0,0,0,0.05)">
                            <div style="font-weight:700;color:#1A1A1A;margin-bottom:0.5rem">
                                {icon} {name}</div>
                            <div style="display:flex;justify-content:space-between;margin-bottom:3px">
                                <span style="color:#6B7280;font-size:0.8rem">Pitches hechos</span>
                                <span style="font-weight:700">{pitches_hechos}</span>
                            </div>
                            <div style="display:flex;justify-content:space-between;margin-bottom:3px">
                                <span style="color:#6B7280;font-size:0.8rem">Cierres reales</span>
                                <span style="font-weight:700;color:{c_real}">{cierres_reales} ({conv_rate}%)</span>
                            </div>
                            <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                                <span style="color:#6B7280;font-size:0.8rem">Falsa conversión</span>
                                <span style="font-weight:700;color:{c_falsa}">{falsos} ({falsa_rate}%)</span>
                            </div>
                            <div style="font-size:0.68rem;color:#9CA3AF">
                                Falsa conv. = pitch sin cierre real
                            </div>
                        </div>""", unsafe_allow_html=True)

                # Summary alert on high false conversion
                high_falsa = [(n, real_col, int((_is_si(_df_me[tc]) & ~_is_one(_df_me[rc])).sum()),
                               int(_is_si(_df_me[tc]).sum()))
                              for n, tc, rc, _, _ in PALANCAS_CONV
                              if tc in _df_me.columns and rc in _df_me.columns]
                for name, _, falsos, total in high_falsa:
                    if total > 0 and falsos / total > 0.6:
                        st.warning(
                            f"⚠️ **{name}:** {falsos/total*100:.0f}% de falsa conversión — "
                            f"la mayoría de los pitches no se convirtieron en cierre real. "
                            f"Revisar calidad del pitch y objeciones frecuentes."
                        )
    except Exception as _e:
        st.caption(f"ℹ️ No se pudieron cargar datos de conversión: {_e}")
