import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.metrics import (
    get_all_semaforos, tier_farmer, EMOJI, COLOR_HEX,
    calcular_compensacion_completa, generar_recomendaciones
)
from core.db import get_consecutive_red_weeks
from core.auth import require_auth

st.set_page_config(
    page_title="Vista Farmer — Rappi Farmers",
    page_icon="🚀",
    layout="wide",
)
email_auth, is_supervisor = require_auth()

if "farmers_data" not in st.session_state:
    st.warning("El supervisor aún no ha cargado datos. Vuelve a la página principal.")
    st.stop()

farmers_data = st.session_state["farmers_data"]
dia_corte    = st.session_state.get("dia_corte", 13)
dias_mes     = st.session_state.get("dias_mes", 31)
progreso_pct = ((dia_corte - 1) / dias_mes) * 100

# ── Farmer selector ───────────────────────────────────────────────────────────
names        = {data.get("name", em): em for em, data in farmers_data.items()}
sorted_names = sorted(names.keys())

if is_supervisor:
    selected_name = st.selectbox("👤 Selecciona un farmer", sorted_names)
else:
    my_name = next(
        (data.get("name", em) for em, data in farmers_data.items() if em == email_auth),
        None
    )
    default_idx = sorted_names.index(my_name) if my_name and my_name in sorted_names else 0
    selected_name = st.selectbox("👤 Farmer", sorted_names, index=default_idx)

farmer_email = names[selected_name]
data         = farmers_data[farmer_email]
sems         = get_all_semaforos(data)
tier         = tier_farmer(sems)
comp         = calcular_compensacion_completa(data)

# ── Header ────────────────────────────────────────────────────────────────────
tier_color = COLOR_HEX.get(tier, "#9E9E9E")
var_pct    = comp.get("variable_pct", 0)
qualifies  = comp.get("qualifies", True)
qual_badge = "" if qualifies else " ⛔"

st.markdown(f"""
<div style="
    background: linear-gradient(135deg, {tier_color}15, #FFFFFF);
    border-left: 5px solid {tier_color};
    border-radius: 12px;
    padding: 1rem 1.5rem;
    margin-bottom: 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
">
    <div>
        <h2 style="margin:0;font-size:1.4rem;color:#1A1A1A">
            {EMOJI.get(tier,'⚪')} {selected_name}{qual_badge}
        </h2>
        <p style="margin:0.2rem 0 0;color:#666;font-size:0.85rem">
            Corte día {dia_corte} · {progreso_pct:.1f}% del mes
        </p>
    </div>
    <div style="text-align:right">
        <div style="font-size:2rem;font-weight:800;color:{('#2E7D32' if var_pct >= 80 else '#E65100' if var_pct >= 50 else '#C62828')}">{var_pct:.0f}%</div>
        <div style="font-size:0.75rem;color:#888">variable ganado</div>
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
    color = COLOR_HEX.get(sem, "#9E9E9E")

    if val is None:                          display = "S/D"
    elif fmt == "decimal":                   display = f"{val*100:.0f}%"
    elif fmt == "pp":                        display = f"{val:+.1f}pp"
    elif fmt == "pct_raw":                   display = f"{val:.0f}%"
    else:                                    display = str(int(val))

    consec = get_consecutive_red_weeks(farmer_email, metric_map_red[sem_key]) \
             if sem_key in metric_map_red else 0
    consec_txt = f"<div style='font-size:0.62rem;color:#C62828'>{consec}w 🔴</div>" \
                 if consec >= 2 else ""

    with col:
        st.markdown(f"""
        <div style="background:#FAFAFA;border-radius:10px;padding:0.6rem 0.4rem;
                    border-top:3px solid {color};text-align:center;min-height:80px;
                    border:1px solid #EEEEEE">
            <div style="font-size:0.6rem;color:#888;margin-bottom:3px;
                        text-transform:uppercase;letter-spacing:0.4px">{label}</div>
            <div style="font-size:1.2rem;font-weight:800;color:{color};line-height:1.1">{display}</div>
            <div style="font-size:0.68rem;color:#777">{EMOJI.get(sem,'⚪')}</div>
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
    color       = COLOR_HEX.get(sem, "#9E9E9E")

    with col:
        st.markdown(f"""
        <div style="background:#FAFAFA;border-radius:10px;padding:0.9rem 1rem;
                    border-left:4px solid {color};border:1px solid #EEE">
            <div style="font-weight:700;color:#1A1A1A;margin-bottom:0.5rem;font-size:0.9rem">{label}</div>
            <div style="display:flex;justify-content:space-between;margin-bottom:2px">
                <span style="color:#666;font-size:0.82rem">Follows</span>
                <span style="font-weight:700;color:#1A1A1A">{follows}</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:2px">
                <span style="color:#666;font-size:0.82rem">Contactados</span>
                <span style="font-weight:700;color:#2E7D32">{contactados}</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                <span style="color:#666;font-size:0.82rem">Sin contactar</span>
                <span style="font-weight:700;color:#C62828">{no_cont}</span>
            </div>
            <div style="background:#E0E0E0;border-radius:4px;height:5px">
                <div style="background:{color};width:{pct_cont}%;height:5px;border-radius:4px"></div>
            </div>
            <div style="font-size:0.72rem;color:#888;margin-top:3px">{pct_cont}% efectividad</div>
        </div>
        """, unsafe_allow_html=True)

# contactabilidad general
total_f = int(data.get("total_follows") or 0)
no_ct   = int(data.get("no_contactados") or 0)
pct_nc  = float(data.get("pct_no_contactados") or 0)

if pct_nc > 40:
    st.error(f"🔴 **Contactabilidad crítica:** {no_ct} de {total_f} aliados sin contactar ({pct_nc:.0f}%). Prioridad urgente esta semana.")
elif pct_nc > 30:
    st.warning(f"🟡 Contactabilidad baja: {no_ct} aliados sin contactar ({pct_nc:.0f}%). Revisar agenda.")

# ── Variable summary (sin gauge) ──────────────────────────────────────────────
st.markdown("---")
st.markdown("#### 💰 Estado de tu variable")

rs       = comp.get("rs_ads", {})
rs_pct   = rs.get("pct", 0)
contribs = comp.get("contributions", {})
kpi_statuses = comp.get("kpi_statuses", {})

vc1, vc2, vc3, vc4, vc5, vc6 = st.columns(6)

with vc1:
    vc = "#2E7D32" if var_pct >= 80 else "#E65100" if var_pct >= 50 else "#C62828"
    st.markdown(f"""
    <div style="background:#FAFAFA;border-radius:10px;padding:0.9rem;text-align:center;border:1px solid #EEE;border-top:3px solid {vc}">
        <div style="font-size:0.65rem;color:#888;text-transform:uppercase">Variable</div>
        <div style="font-size:1.8rem;font-weight:800;color:{vc}">{var_pct:.0f}%</div>
        <div style="font-size:0.68rem;color:#888">{'⛔ Sin qualifier' if not qualifies else '✅ Qualifier OK'}</div>
    </div>""", unsafe_allow_html=True)

with vc2:
    rsc = "#2E7D32" if rs_pct >= 20 else "#E65100" if rs_pct > 0 else "#C62828"
    st.markdown(f"""
    <div style="background:#FAFAFA;border-radius:10px;padding:0.9rem;text-align:center;border:1px solid #EEE;border-top:3px solid {rsc}">
        <div style="font-size:0.65rem;color:#888;text-transform:uppercase">RS ADS</div>
        <div style="font-size:1.8rem;font-weight:800;color:{rsc}">{rs_pct}%</div>
        <div style="font-size:0.68rem;color:#888">{rs.get('label','—')[:18]}</div>
    </div>""", unsafe_allow_html=True)

kpi_defs = [
    ("ADS_Rev",  "Ads Rev 35%",  data.get("ATT_Rev_real")),
    ("MD_Total", "MD Total 20%", data.get("ATT_MD_Total")),
    ("MD_Pro",   "MD Pro 20%",   data.get("ATT_MD_Pro")),
    ("Churn",    "Churn 25%",    data.get("ATT_Churn")),
]
status_map = {"gana": ("🟢","#2E7D32"), "parcial": ("🟡","#E65100"),
              "no_gana": ("🔴","#C62828"), "sin_dato": ("⚪","#9E9E9E")}

for col, (kpi, label, att_val) in zip([vc3, vc4, vc5, vc6], kpi_defs):
    icon, kcolor = status_map.get(kpi_statuses.get(kpi, "sin_dato"), ("⚪","#9E9E9E"))
    att_str      = f"{att_val*100:.0f}%" if att_val is not None else "S/D"
    contrib      = contribs.get(kpi)
    contrib_str  = f"+{contrib:.1f}pp" if contrib else "—"
    with col:
        st.markdown(f"""
        <div style="background:#FAFAFA;border-radius:10px;padding:0.9rem;text-align:center;border:1px solid #EEE;border-top:3px solid {kcolor}">
            <div style="font-size:0.6rem;color:#888;text-transform:uppercase">{label}</div>
            <div style="font-size:1.4rem;font-weight:800;color:{kcolor}">{icon} {att_str}</div>
            <div style="font-size:0.68rem;color:#888">{contrib_str} al var.</div>
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
            <div style="background:#FFF3E0;border:1px solid #FF6B00;border-radius:8px;
                        padding:0.5rem 0.4rem;text-align:center;font-size:0.78rem;
                        font-weight:600;color:#E65100">
                ⚡ {brand}
            </div>
            """, unsafe_allow_html=True)
    if len(brands) > 5:
        st.caption(f"… y {len(brands)-5} aliados más. Ver lista completa en Vista Equipo → Rankings.")
    st.markdown("""
    <div style="background:#FFF8F2;border-radius:8px;padding:0.7rem 1rem;
                border-left:3px solid #FF6B00;margin-top:0.5rem;font-size:0.82rem;color:#555">
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
