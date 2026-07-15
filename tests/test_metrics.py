"""Characterization tests for core.metrics.

These lock the CURRENT behavior of the compensation / semaphore engine so that
the Fase-1 refactor cannot silently change any business result. If a value here
changes, it must be a deliberate, reviewed decision — not an accident.
"""
from __future__ import annotations

import pytest

from core import metrics


# ── Semaphore helpers ─────────────────────────────────────────────────────────
class TestSemaforoGeneric:
    def test_none_is_gray(self):
        assert metrics.semaforo(None, 0.9) == "gray"

    def test_below_red_threshold(self):
        assert metrics.semaforo(0.5, 0.9) == "red"

    def test_yellow_band(self):
        assert metrics.semaforo(0.92, 0.9, 0.95) == "yellow"

    def test_green_above_all(self):
        assert metrics.semaforo(0.99, 0.9, 0.95) == "green"

    def test_green_when_no_yellow_threshold(self):
        assert metrics.semaforo(0.91, 0.9) == "green"


class TestSemaforoAtt:
    @pytest.mark.parametrize(
        "val,expected",
        [
            (None, "gray"),
            (0.0, "red"),
            (0.89, "red"),
            (0.90, "yellow"),
            (0.94, "yellow"),
            (0.95, "green"),
            (1.50, "green"),
        ],
    )
    def test_bands(self, val, expected):
        assert metrics.semaforo_att(val) == expected


class TestSemaforoPitch:
    @pytest.mark.parametrize(
        "val,expected",
        [
            (None, "gray"),
            (0.49, "red"),
            (0.50, "yellow"),
            (0.64, "yellow"),
            (0.65, "green"),
            (1.0, "green"),
        ],
    )
    def test_bands(self, val, expected):
        assert metrics.semaforo_pitch(val) == expected


class TestSemaforoNetRev:
    @pytest.mark.parametrize(
        "val,expected",
        [
            (None, "gray"),
            (-6, "red"),
            (-5, "yellow"),
            (-0.1, "yellow"),
            (0, "green"),
            (10, "green"),
        ],
    )
    def test_bands(self, val, expected):
        assert metrics.semaforo_net_rev(val) == expected


class TestSemaforoNoContactados:
    @pytest.mark.parametrize(
        "val,expected",
        [
            (None, "gray"),
            (41, "red"),
            (40, "yellow"),
            (31, "yellow"),
            (30, "green"),
            (0, "green"),
        ],
    )
    def test_bands(self, val, expected):
        assert metrics.semaforo_no_contactados(val) == expected


class TestSemaforoReactivaciones:
    def test_none(self):
        assert metrics.semaforo_reactivaciones(None) == "gray"

    def test_zero_is_red(self):
        assert metrics.semaforo_reactivaciones(0) == "red"

    def test_positive_is_green(self):
        assert metrics.semaforo_reactivaciones(3) == "green"


class TestSemaforoRecurrenciaNo:
    @pytest.mark.parametrize(
        "val,expected",
        [
            (None, "gray"),
            (30, "green"),
            (29, "yellow"),
            (15, "yellow"),
            (14, "red"),
            (0, "red"),
        ],
    )
    def test_bands(self, val, expected):
        assert metrics.semaforo_recurrencia_no(val) == expected


# ── Aggregate semaphore snapshot ──────────────────────────────────────────────
def test_get_all_semaforos_keys_and_values():
    farmer = {
        "ATT_Churn": 0.96,
        "ATT_MD_Total": 0.80,
        "ATT_MD_Pro": None,
        "ATT_Book": 0.95,
        "Net_Rev_Adj": -3,
        "Pitch_Pct": 0.70,
        "pct_no_contactados": 20,
        "Reactivaciones": 0,
    }
    sem = metrics.get_all_semaforos(farmer)
    assert sem == {
        "Churn": "green",
        "MD Total": "red",
        "MD Pro": "gray",
        "Ads Bookings": "green",
        "Ads Revenue": "yellow",
        "Net Rev Adj": "yellow",
        "Pitch Integral": "green",
        "No Contactados": "green",
        "Reactivaciones": "red",
    }


class TestTierFarmer:
    def test_red_wins(self):
        assert metrics.tier_farmer({"a": "green", "b": "red", "c": "yellow"}) == "red"

    def test_yellow_over_green(self):
        assert metrics.tier_farmer({"a": "green", "b": "yellow"}) == "yellow"

    def test_all_green(self):
        assert metrics.tier_farmer({"a": "green", "b": "green"}) == "green"


# ── Compensation engine ───────────────────────────────────────────────────────
class TestCalcularVariableScore:
    def test_all_max_qualifies(self):
        r = metrics.calcular_variable_score(
            att_ads_rev=1.00,
            att_md_total=1.50,
            att_md_pro=1.50,
            att_churn=1.50,
            productividad_pct=0.95,
        )
        assert r["qualifies"] is True
        # ADS capped at 1.00 (full), the three MD/Churn at 1.50 (full) → 100%
        assert r["variable_pct"] == 100.0
        assert r["kpi_statuses"] == {
            "ADS_Rev": "gana",
            "MD_Total": "gana",
            "MD_Pro": "gana",
            "Churn": "gana",
        }

    def test_below_qualifier_zeroes_everything(self):
        r = metrics.calcular_variable_score(
            att_ads_rev=1.00,
            att_md_total=1.50,
            att_md_pro=1.50,
            att_churn=1.50,
            productividad_pct=0.50,
        )
        assert r["qualifies"] is False
        assert r["variable_pct"] == 0
        assert all(v == 0 for v in r["contributions"].values())

    def test_below_min_bound_earns_zero_for_that_kpi(self):
        r = metrics.calcular_variable_score(
            att_ads_rev=0.70,   # below 0.80 min
            att_md_total=1.50,
            att_md_pro=1.50,
            att_churn=1.50,
            productividad_pct=0.95,
        )
        assert r["contributions"]["ADS_Rev"] == 0
        assert r["kpi_statuses"]["ADS_Rev"] == "no_gana"

    def test_none_kpi_excluded_from_denominator(self):
        r = metrics.calcular_variable_score(
            att_ads_rev=None,
            att_md_total=1.50,
            att_md_pro=1.50,
            att_churn=1.50,
            productividad_pct=0.95,
        )
        assert r["contributions"]["ADS_Rev"] is None
        assert r["kpi_statuses"]["ADS_Rev"] == "sin_dato"
        # Remaining three at max → 100%
        assert r["variable_pct"] == 100.0

    def test_partial_status_between_min_and_90(self):
        r = metrics.calcular_variable_score(
            att_ads_rev=0.85,   # >= 0.80 min but < 0.90
            att_md_total=1.50,
            att_md_pro=1.50,
            att_churn=1.50,
            productividad_pct=0.95,
        )
        assert r["kpi_statuses"]["ADS_Rev"] == "parcial"

    def test_qualifier_none_still_qualifies(self):
        r = metrics.calcular_variable_score(
            att_ads_rev=1.00,
            att_md_total=1.50,
            att_md_pro=1.50,
            att_churn=1.50,
            productividad_pct=None,
        )
        assert r["qualifies"] is True


class TestRevenueShareAds:
    @pytest.mark.parametrize(
        "att,pct,tier",
        [
            (None, 0, "gray"),
            (0.89, 0, "red"),
            (0.90, 10, "yellow"),
            (1.00, 10, "yellow"),
            (1.10, 20, "green"),
            (1.20, 20, "green"),
            (1.30, 30, "green"),
        ],
    )
    def test_tiers(self, att, pct, tier):
        r = metrics.calcular_revenue_share_ads(att)
        assert r["pct"] == pct
        assert r["tier"] == tier


# ── Quartiles ─────────────────────────────────────────────────────────────────
def test_assign_quartiles_ordering():
    scores = {f"f{i}": float(100 - i * 10) for i in range(8)}  # f0 best … f7 worst
    q = metrics.assign_quartiles(scores)
    assert q["f0"] == "Q1"
    assert q["f1"] == "Q1"
    assert q["f2"] == "Q2"
    assert q["f4"] == "Q3"
    assert q["f6"] == "Q4"
    assert q["f7"] == "Q4"


# ── Recommendations ───────────────────────────────────────────────────────────
class TestRecomendaciones:
    def test_all_green_returns_positive_message(self):
        sem = {k: "green" for k in [
            "Churn", "MD Total", "MD Pro", "Ads Revenue",
            "Pitch Integral", "No Contactados", "Net Rev Adj",
        ]}
        recs = metrics.generar_recomendaciones({}, sem)
        assert len(recs) == 1
        assert "verde" in recs[0].lower()

    def test_ads_risk_mentions_brands_over_70(self):
        farmer = {"brands_riesgo": ["Marca A", "Marca B", "Marca C", "Marca D"]}
        sem = {"Ads Revenue": "red"}
        recs = metrics.generar_recomendaciones(farmer, sem)
        joined = " ".join(recs)
        assert "70%" in joined
        assert "Marca A" in joined
        # Only first 3 brands are listed
        assert "Marca D" not in joined

    def test_md_red_without_follows(self):
        farmer = {"md_follows": 0, "md_contactados": 0}
        sem = {"MD Total": "red"}
        recs = metrics.generar_recomendaciones(farmer, sem)
        assert any("MD en rojo sin follows" in r for r in recs)
