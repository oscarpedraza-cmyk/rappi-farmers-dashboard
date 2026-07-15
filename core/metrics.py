"""
Metric calculations and compensation engine for Rappi Farmers Dashboard.

Compensation structure (May 2026):
  ADS Revenue:    35% weight | min 80% | max 100% (capped)
  Markdown Total: 20% weight | min 80% | max 150%
  Markdown Pro:   20% weight | min 80% | max 150%
  Churn x AVA:    25% weight | min 80% | max 150%

Qualifier: productividad >= 90% (Zoho Voice + Treble + Meets only)
Revenue Share ADS: 10% (90-100%) / 20% (100-120%) / 30% (>120%) — cap $2k/mo, $5k/qtr
Penalty ADS: exclude aliados with ADS investment >= 70% of GMV
"""
from __future__ import annotations

# Business rules live in config.scoring; re-exported here so existing imports
# (from core.metrics import WEIGHTS, BOUNDS, …) keep working unchanged.
from config import scoring
from config.scoring import (  # noqa: F401  (re-export for backward compatibility)
    BOUNDS,
    QUALIFIER_PRODUCTIVIDAD,
    REVENUE_SHARE_CAP_MONTHLY,
    WEIGHTS,
)


# ── Traffic-light helpers ─────────────────────────────────────────────────────
def semaforo(val, red_thresh, yellow_thresh=None):
    """Generic semaphore. Returns 'red', 'yellow', or 'green'."""
    if val is None:
        return "gray"
    if val < red_thresh:
        return "red"
    if yellow_thresh and val < yellow_thresh:
        return "yellow"
    return "green"


def semaforo_att(att_decimal):
    """ATT as decimal (0–1.5). Red < 0.90, yellow 0.90-0.95, green >= 0.95."""
    if att_decimal is None:
        return "gray"
    if att_decimal < scoring.ATT_RED:
        return "red"
    if att_decimal < scoring.ATT_YELLOW:
        return "yellow"
    return "green"


def semaforo_pitch(pct_decimal):
    """Pitch Integral. Red < 0.50, yellow 0.50-0.65, green >= 0.65."""
    if pct_decimal is None:
        return "gray"
    if pct_decimal < scoring.PITCH_RED:
        return "red"
    if pct_decimal < scoring.PITCH_YELLOW:
        return "yellow"
    return "green"


def semaforo_net_rev(adj_pp):
    """Net Revenue Adjusted in pp. Red < -5, yellow -5 to 0, green >= 0."""
    if adj_pp is None:
        return "gray"
    if adj_pp < scoring.NET_REV_RED:
        return "red"
    if adj_pp < scoring.NET_REV_YELLOW:
        return "yellow"
    return "green"


def semaforo_no_contactados(pct):
    """% no contactados. Red > 40%, yellow 30-40%, green <= 30%."""
    if pct is None:
        return "gray"
    if pct > scoring.NO_CONTACT_RED:
        return "red"
    if pct > scoring.NO_CONTACT_YELLOW:
        return "yellow"
    return "green"


def semaforo_reactivaciones(val):
    """Reactivaciones = 0 is a direct alert."""
    if val is None:
        return "gray"
    return "red" if val == 0 else "green"


def semaforo_recurrencia_no(pct):
    """
    % cuentas con ≥2 semanas sin contactar.
    HIGHER IS BETTER — identifica marcas candidatas a salir del portafolio.
    Green ≥ 30%, yellow 15–30%, red < 15%.
    """
    if pct is None:
        return "gray"
    if pct >= scoring.RECURRENCIA_GREEN:
        return "green"
    if pct >= scoring.RECURRENCIA_YELLOW:
        return "yellow"
    return "red"


EMOJI = {"red": "🔴", "yellow": "🟡", "green": "🟢", "gray": "⚪"}
COLOR_HEX = {"red": "#EF4444", "yellow": "#F59E0B", "green": "#00B341", "gray": "#9CA3AF"}


def get_all_semaforos(farmer: dict) -> dict:
    return {
        "Churn":          semaforo_att(farmer.get("ATT_Churn")),
        "MD Total":       semaforo_att(farmer.get("ATT_MD_Total")),
        "MD Pro":         semaforo_att(farmer.get("ATT_MD_Pro")),
        "Ads Bookings":   semaforo_att(farmer.get("ATT_Book")),
        # ADS Revenue: green only if pace will reach 100% by month-end (Net_Rev_Adj ≥ 0)
        "Ads Revenue":    semaforo_net_rev(farmer.get("Net_Rev_Adj")),
        "Net Rev Adj":    semaforo_net_rev(farmer.get("Net_Rev_Adj")),
        "Pitch Integral": semaforo_pitch(farmer.get("Pitch_Pct")),
        "No Contactados": semaforo_no_contactados(farmer.get("pct_no_contactados")),
        "Reactivaciones": semaforo_reactivaciones(farmer.get("Reactivaciones")),
    }


def tier_farmer(semaforos: dict) -> str:
    """Overall tier based on worst metric."""
    vals = list(semaforos.values())
    if "red" in vals:
        return "red"
    if "yellow" in vals:
        return "yellow"
    return "green"


def score_farmer(semaforos: dict, comp: dict) -> float:
    """
    Composite score 0-100 for quartile ranking.
    Weights: semáforo (60%) + variable % (40%)
    Semáforo: green=2, yellow=1, red=0, gray=0
    """
    sem_points = {"green": 2, "yellow": 1, "red": 0, "gray": 0}
    sem_vals = list(semaforos.values())
    max_sem = len(sem_vals) * 2
    sem_score = sum(sem_points.get(s, 0) for s in sem_vals) / max_sem * 100 if max_sem > 0 else 0

    var_pct = comp.get("variable_pct", 0) or 0
    if not comp.get("qualifies", True):
        var_pct = 0

    return round(sem_score * 0.6 + var_pct * 0.4, 2)


def assign_quartiles(farmers_scores: dict) -> dict:
    """
    Given {email: score}, returns {email: 'Q1'|'Q2'|'Q3'|'Q4'}.
    Q1 = best (top 25%), Q4 = worst (bottom 25%).
    """
    sorted_farmers = sorted(farmers_scores.items(), key=lambda x: x[1], reverse=True)
    n = len(sorted_farmers)
    quartiles = {}
    for i, (email, _) in enumerate(sorted_farmers):
        rank_pct = i / n
        if rank_pct < 0.25:
            quartiles[email] = "Q1"
        elif rank_pct < 0.50:
            quartiles[email] = "Q2"
        elif rank_pct < 0.75:
            quartiles[email] = "Q3"
        else:
            quartiles[email] = "Q4"
    return quartiles


QUARTILE_COLOR = {"Q1": "#00B341", "Q2": "#00C9A7", "Q3": "#F59E0B", "Q4": "#EF4444"}
QUARTILE_LABEL = {"Q1": "🏆 Q1", "Q2": "✅ Q2", "Q3": "⚠️ Q3", "Q4": "🚨 Q4"}


# ── Compensation engine ───────────────────────────────────────────────────────
def _clamp(val, low, high):
    return max(low, min(high, val))


def calcular_variable_score(
    att_ads_rev,
    att_md_total,
    att_md_pro,
    att_churn,
    productividad_pct=None,
):
    """
    Returns dict with:
      - qualifies (bool): False if productividad < 90%
      - variable_score (0–1): weighted achievement
      - variable_pct (0–100): % of variable salary earned
      - contributions: dict with per-KPI contribution
      - kpi_statuses: dict with 'earning'/'not_earning'/'partial'
    """
    qualifies = True
    if productividad_pct is not None and productividad_pct < QUALIFIER_PRODUCTIVIDAD:
        qualifies = False

    kpis = {
        "ADS_Rev":  att_ads_rev,
        "MD_Total": att_md_total,
        "MD_Pro":   att_md_pro,
        "Churn":    att_churn,
    }

    contributions = {}
    kpi_statuses = {}
    total_score = 0.0
    total_weight = 0.0

    for kpi, att in kpis.items():
        weight = WEIGHTS[kpi]
        low, high = BOUNDS[kpi]

        if att is None:
            contributions[kpi] = None
            kpi_statuses[kpi] = "sin_dato"
            continue

        total_weight += weight

        if att < low:
            contributions[kpi] = 0
            kpi_statuses[kpi] = "no_gana"
        else:
            clamped = _clamp(att, low, high)
            # Normalize: at min→0, at max→100
            score_kpi = (clamped - low) / (high - low)
            contributions[kpi] = round(score_kpi * weight * 100, 2)
            total_score += score_kpi * weight
            kpi_statuses[kpi] = "gana" if att >= scoring.KPI_EARNING_THRESHOLD else "parcial"

    max_possible = sum(WEIGHTS[k] for k in kpis if kpis[k] is not None)
    variable_pct = (total_score / max_possible * 100) if max_possible > 0 else 0

    if not qualifies:
        variable_pct = 0
        contributions = {k: 0 for k in contributions}

    return {
        "qualifies": qualifies,
        "variable_score": round(total_score, 4),
        "variable_pct": round(variable_pct, 1),
        "contributions": contributions,
        "kpi_statuses": kpi_statuses,
    }


def calcular_revenue_share_ads(att_rev_ads_decimal):
    """
    Returns revenue share percentage for ADS (10/20/30%) and label.
    att_rev_ads_decimal: ATT as 0–1 (e.g. 0.95 = 95%)
    """
    if att_rev_ads_decimal is None:
        return {"pct": 0, "label": "Sin dato", "tier": "gray"}
    if att_rev_ads_decimal < scoring.REV_SHARE_MIN_ATT:
        return {"pct": 0, "label": "No aplica (< 90%)", "tier": "red"}
    if att_rev_ads_decimal <= scoring.REV_SHARE_TIER1_MAX:
        return {"pct": 10, "label": "10% Revenue Share", "tier": "yellow"}
    if att_rev_ads_decimal <= scoring.REV_SHARE_TIER2_MAX:
        return {"pct": 20, "label": "20% Revenue Share", "tier": "green"}
    return {"pct": 30, "label": "30% Revenue Share 🔥", "tier": "green"}


def calcular_compensacion_completa(farmer: dict) -> dict:
    """Full compensation snapshot for a farmer row."""
    # Use pre-calculated productividad_pct from loader (Zoho Voice + Treble + Meets only)
    prod_pct = farmer.get("productividad_pct")

    variable = calcular_variable_score(
        att_ads_rev=farmer.get("ATT_Rev_real"),
        att_md_total=farmer.get("ATT_MD_Total"),
        att_md_pro=farmer.get("ATT_MD_Pro"),
        att_churn=farmer.get("ATT_Churn"),
        productividad_pct=prod_pct,
    )

    rs_ads = calcular_revenue_share_ads(farmer.get("ATT_Rev_real"))

    return {
        **variable,
        "productividad_pct": prod_pct,
        "rs_ads": rs_ads,
    }


# ── Actionable recommendations ────────────────────────────────────────────────
def generar_recomendaciones(farmer: dict, semaforos: dict) -> list[str]:
    recs = []

    # Churn
    if semaforos.get("Churn") == "red":
        churn_follows = farmer.get("churn_follows", 0) or 0
        churn_cont = farmer.get("churn_contactados", 0) or 0
        if churn_follows == 0:
            recs.append("🎯 Churn en rojo y sin follows de churn — priorizar detección de aliados en riesgo esta semana.")
        elif churn_cont < churn_follows * 0.6:
            recs.append(f"📞 Churn en rojo con {churn_follows} follows pero solo {churn_cont} contactados — problema de gestión, no de cartera. Revisar agenda y abordaje.")
        if farmer.get("Reactivaciones") == 0:
            recs.append("⚠️ Reactivaciones = 0 — ningún aliado recuperado. Trabajar pipeline de aliados inactivos urgente.")

    # MD
    if semaforos.get("MD Total") == "red":
        md_follows = farmer.get("md_follows", 0) or 0
        md_cont = farmer.get("md_contactados", 0) or 0
        if md_follows == 0:
            recs.append("💰 MD en rojo sin follows — identificar aliados con potencial de Markdown esta semana.")
        elif md_cont < md_follows * 0.6:
            recs.append(f"💰 MD en rojo: {md_follows} follows, {md_cont} contactados. Contactabilidad baja — revisar horarios de contacto.")

    if semaforos.get("MD Pro") == "red":
        recs.append("⭐ MD Pro por debajo del 90% — enfocar en Markdown Pro con aliados PRO de la cartera.")

    # Ads
    if semaforos.get("Ads Revenue") == "red":
        brands = farmer.get("brands_riesgo", [])
        if brands:
            brand_str = ", ".join(brands[:3])
            recs.append(f"🚨 ADS en riesgo — marcas con penetración > 70% del GMV: {brand_str}. Revisar con el aliado para reducir pauta y evitar churn.")
        else:
            recs.append("📢 Ads Revenue en rojo — revisar pipeline de inversión con aliados estratégicos.")

    # Pitch Integral
    if semaforos.get("Pitch Integral") in ("red", "yellow"):
        pitch_pct = farmer.get("Pitch_Pct", 0) or 0
        recs.append(f"🎤 Pitch Integral en {pitch_pct*100:.0f}% (meta 65%) — reforzar estructura del pitch en cada visita. Pedir grabaciones para retroalimentar.")

    # Contactabilidad
    if semaforos.get("No Contactados") == "red":
        no_cont = farmer.get("no_contactados", 0) or 0
        recs.append(f"📵 {no_cont} aliados sin contactar — revisar si es problema de datos (teléfonos desactualizados) o de gestión de tiempo.")

    # Net Revenue
    if semaforos.get("Net Rev Adj") == "red":
        adj = farmer.get("Net_Rev_Adj", 0) or 0
        recs.append(f"📉 Net Revenue {adj:+.1f} pp vs ritmo esperado — acelerar facturación en la segunda mitad del mes.")

    if not recs:
        recs.append("✅ Todos los indicadores en verde. Mantener el ritmo y buscar superación de targets para maximizar Revenue Share ADS.")

    return recs
