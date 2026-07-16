"""Characterization tests for core.loader.

The synthetic Sheet Maestro fixture (``xl``) lives in conftest.py and mirrors the
real column layout, so parsing behaviour is locked without depending on any
private file on disk.
"""
from __future__ import annotations

import pytest

from core import loader


# ── _is_farmer_email ──────────────────────────────────────────────────────────
class TestIsFarmerEmail:
    def test_valid(self):
        assert loader._is_farmer_email("fanny.landazabal@rappi.com") is True

    def test_supervisor_excluded(self):
        assert loader._is_farmer_email("oscar.pedraza@rappi.com") is False

    def test_non_string(self):
        assert loader._is_farmer_email(None) is False
        assert loader._is_farmer_email(123) is False

    def test_non_rappi(self):
        assert loader._is_farmer_email("someone@gmail.com") is False


# ── load_md ───────────────────────────────────────────────────────────────────
def test_load_md_reads_correct_columns(xl):
    result = loader.load_md(xl)
    assert "Total" not in result  # non-email rows filtered
    fanny = result["fanny.landazabal@rappi.com"]
    assert fanny["ATT_MD_Total"] == pytest.approx(0.7353)
    assert fanny["ATT_MD_Pro"] == pytest.approx(0.7611)
    alex = result["alejandro.salamanca@rappi.com"]
    assert alex["ATT_MD_Total"] == pytest.approx(0.6852)
    assert alex["ATT_MD_Pro"] == pytest.approx(0.7260)


# ── load_ads ──────────────────────────────────────────────────────────────────
def test_load_ads_reads_correct_columns(xl):
    result = loader.load_ads(xl)
    fanny = result["fanny.landazabal@rappi.com"]
    assert fanny["ATT_Book"] == pytest.approx(0.8554)
    assert fanny["ATT_Rev_real"] == pytest.approx(0.3282)


# ── load_churn ────────────────────────────────────────────────────────────────
def test_load_churn_reads_correct_columns(xl):
    result = loader.load_churn(xl)
    fanny = result["fanny.landazabal@rappi.com"]
    assert fanny["ATT_Churn"] == pytest.approx(0.9600)
    assert fanny["Reactivaciones"] == 2
    assert fanny["Gross_Churn"] == 5
    assert fanny["Net_Churn"] == 3
    assert fanny["Ava_Stores"] == 120


# ── load_penetracion ──────────────────────────────────────────────────────────
def test_load_penetracion_only_high_risk_brands(xl):
    result = loader.load_penetracion(xl)
    brands = result["fanny.landazabal@rappi.com"]
    assert "Pizza Hut" in brands       # 85% penetration → risk
    assert "Burger" not in brands      # 15% penetration → not risk
    assert "Total" not in brands


# ── refresh_net_rev_adj ───────────────────────────────────────────────────────
class TestRefreshNetRevAdj:
    def test_none_stays_none(self):
        data = {"f@rappi.com": {"ATT_Rev_real": None}}
        loader.refresh_net_rev_adj(data, dias_mes=30)
        assert data["f@rappi.com"]["Net_Rev_Adj"] is None

    def test_numeric_produces_float(self):
        data = {"f@rappi.com": {"ATT_Rev_real": 1.0}}
        loader.refresh_net_rev_adj(data, dias_mes=30)
        val = data["f@rappi.com"]["Net_Rev_Adj"]
        assert isinstance(val, float)
        # value = att*100 - progreso; att*100 = 100 so it must be <= 100
        assert val <= 100.0


# ── Public constants must remain stable (imported by auth.py, db.py) ──────────
def test_public_constants_present():
    assert "fanny.landazabal@rappi.com" in loader.FARMERS_EMAILS
    assert isinstance(loader.EXCLUDED_EMAILS, set)
    assert loader.FARMER_NAMES["fanny.landazabal@rappi.com"] == "Fanny Landazabal"
    assert "oscar.pedraza@rappi.com" in loader.SLACK_IDS
