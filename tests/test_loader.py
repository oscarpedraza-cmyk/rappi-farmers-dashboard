"""Characterization tests for core.loader.

A small synthetic .xlsx fixture is built in-memory that mirrors the real Sheet
Maestro column layout, so parsing behaviour is locked without depending on any
private file on disk.
"""
from __future__ import annotations

import io

import pandas as pd
import pytest

from core import loader


# ── Fixture: synthetic Sheet Maestro ──────────────────────────────────────────
def _pad(row: list, width: int) -> list:
    return row + [None] * (width - len(row))


def _build_workbook() -> pd.ExcelFile:
    """Return a pd.ExcelFile mirroring the real column positions per sheet."""
    # MD: row0 MONTH, row1 headers, data from row2. col2=email, col6=Total, col10=Pro
    md_rows = [
        _pad(["MONTH"], 11),
        _pad(["LEADER", "COUNTRY", "EMAIL", "MD$", "MD%", "TGT", "ATT_TOT",
              "PRO$", "PRO%", "TGT2", "ATT_PRO"], 11),
        _pad(["oscar", "AR", "fanny.landazabal@rappi.com", 1, 2, 3, 0.7353,
              5, 6, 7, 0.7611], 11),
        _pad(["oscar", "AR", "alejandro.salamanca@rappi.com", 1, 2, 3, 0.6852,
              5, 6, 7, 0.7260], 11),
        _pad(["oscar", "AR", "Total", 1, 2, 3, 0.99, 5, 6, 7, 0.99], 11),
    ]

    # Ads: row0 headers, data from row1. col2=email, col8=bookings, col13=rev
    ads_rows = [
        _pad(["LIDER", "COUNTRY", "KAM", "b", "b", "b", "b", "TGT",
              "ATT_BOOK", "rg", "rr", "ra", "tr", "ATT_REV"], 14),
        _pad(["oscar", "AR", "fanny.landazabal@rappi.com", 1, 1, 1, 1, 1,
              0.8554, 1, 1, 1, 1, 0.3282], 14),
        _pad(["oscar", "AR", "Total", 1, 1, 1, 1, 1, 0.9, 1, 1, 1, 1, 0.9], 14),
    ]

    # Churn: row0 headers, data from row1.
    # col2=email col3=ava col7=gross col8=react col9=net col13=ATT
    churn_rows = [
        _pad(["COUNTRY", "LEADER", "FARMER", "AVA", "x", "x", "x", "GROSS",
              "REACT", "NET", "g%", "n%", "TGT", "ATT"], 14),
        _pad(["AR", "oscar", "fanny.landazabal@rappi.com", 120, 0, 0, 0, 5,
              2, 3, 0, 0, 0, 0.9600], 14),
    ]

    # Penetración: row0 MONTH, row1 headers, data from row2.
    # col2=email col3="ID - Name" col4=revenue col11=pen_media col12=rev_perdido
    pen_rows = [
        _pad(["MONTH"], 13),
        _pad(["COUNTRY", "LEADER", "EMAIL", "BRAND", "REV", "GMV",
              "s0", "s1", "s2", "s3", "s4", "PEN", "REVLOST"], 13),
        # brand with high penetration (>70%) → should appear in brands_riesgo
        _pad(["AR", "oscar", "fanny.landazabal@rappi.com", "AR1 - Pizza Hut",
              1000, 5000, 0, 0, 0, 0, 0, 0.85, 200], 13),
        # brand with low penetration → should NOT appear
        _pad(["AR", "oscar", "fanny.landazabal@rappi.com", "AR2 - Burger",
              800, 4000, 0, 0, 0, 0, 0, 0.15, 50], 13),
        # Total row → filtered out
        _pad(["AR", "oscar", "fanny.landazabal@rappi.com", "Total",
              1800, 9000, 0, 0, 0, 0, 0, 0.5, 250], 13),
    ]

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(md_rows).to_excel(writer, sheet_name="MD", header=False, index=False)
        pd.DataFrame(ads_rows).to_excel(writer, sheet_name="Ads", header=False, index=False)
        pd.DataFrame(churn_rows).to_excel(writer, sheet_name="Churn", header=False, index=False)
        pd.DataFrame(pen_rows).to_excel(writer, sheet_name="Penetración", header=False, index=False)
    buf.seek(0)
    return pd.ExcelFile(buf, engine="openpyxl")


@pytest.fixture
def xl():
    return _build_workbook()


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
