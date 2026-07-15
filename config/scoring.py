"""Compensation weights, bounds and semaphore thresholds.

Single source of truth for every numeric business rule used by
:mod:`core.metrics`. Extracting them here removes magic numbers from the
calculation code and makes the compensation policy auditable in one place.

Compensation structure (May 2026):
  ADS Revenue:    35% weight | min 80% | max 100% (capped)
  Markdown Total: 20% weight | min 80% | max 150%
  Markdown Pro:   20% weight | min 80% | max 150%
  Churn x AVA:    25% weight | min 80% | max 150%
"""
from __future__ import annotations

# ── Weights and bounds ────────────────────────────────────────────────────────
WEIGHTS: dict[str, float] = {
    "ADS_Rev":  0.35,
    "MD_Total": 0.20,
    "MD_Pro":   0.20,
    "Churn":    0.25,
}

BOUNDS: dict[str, tuple[float, float]] = {
    "ADS_Rev":  (0.80, 1.00),   # capped at 100%
    "MD_Total": (0.80, 1.50),
    "MD_Pro":   (0.80, 1.50),
    "Churn":    (0.80, 1.50),
}

QUALIFIER_PRODUCTIVIDAD: float = 0.90   # must be >= 90%
REVENUE_SHARE_CAP_MONTHLY: int = 2000   # USD

# KPI is considered fully "earning" (vs partial) at/above this achievement.
KPI_EARNING_THRESHOLD: float = 0.90

# ── Semaphore thresholds ──────────────────────────────────────────────────────
# ATT metrics (Churn, MD Total, MD Pro, Bookings): red < 0.90, yellow < 0.95.
ATT_RED: float = 0.90
ATT_YELLOW: float = 0.95

# Pitch Integral: red < 0.50, yellow < 0.65.
PITCH_RED: float = 0.50
PITCH_YELLOW: float = 0.65

# Net Revenue Adjusted (in pp): red < -5, yellow < 0.
NET_REV_RED: float = -5.0
NET_REV_YELLOW: float = 0.0

# % no contactados: red > 40, yellow > 30 (higher is worse).
NO_CONTACT_RED: float = 40.0
NO_CONTACT_YELLOW: float = 30.0

# % recurrencia sin contactar: green >= 30, yellow >= 15 (higher is better).
RECURRENCIA_GREEN: float = 30.0
RECURRENCIA_YELLOW: float = 15.0

# ── Revenue-share ADS tiers (by ATT achievement) ──────────────────────────────
REV_SHARE_MIN_ATT: float = 0.90    # below this → no revenue share
REV_SHARE_TIER1_MAX: float = 1.00  # <= 1.00 → 10%
REV_SHARE_TIER2_MAX: float = 1.20  # <= 1.20 → 20%; above → 30%

# ── ADS penetration risk ──────────────────────────────────────────────────────
# A brand spending more than this share of GMV on ADS fees is at critical risk.
ADS_PENETRATION_RISK: float = 0.70
