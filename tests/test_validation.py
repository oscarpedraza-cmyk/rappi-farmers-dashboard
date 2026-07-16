"""Tests for the Sheet Maestro structure validator.

The point of this module is to turn silent corruption (an inserted column) and
silent gaps (an empty tab) into loud, specific messages — so the tests focus on
proving those two cases are actually caught.
"""
from __future__ import annotations

import io

import pandas as pd
import pytest

from core.validation import (
    ValidationIssue,
    format_issues,
    normalize_header,
    validate_workbook,
)
from tests.conftest import FakeSpreadsheet, _pad


# ── Header normalisation ──────────────────────────────────────────────────────
class TestNormalizeHeader:
    def test_hangul_filler_is_stripped(self):
        # The real MD tab uses U+3164 to keep a second "ATT %" distinct.
        # str.strip() does NOT remove it (it is category Lo, a letter).
        assert "ATT %ㅤ".strip() != "ATT %"
        assert normalize_header("ATT %ㅤ") == normalize_header("ATT %") == "att %"

    def test_case_and_whitespace_insensitive(self):
        assert normalize_header("  BRAND_owner_EMAIL ") == "brand_owner_email"
        assert normalize_header("% Att.  Bookings") == "% att. bookings"

    def test_nbsp_and_zero_width(self):
        assert normalize_header("Revenue Perdido") == "revenue perdido"
        assert normalize_header("Week​") == "week"

    def test_none_and_nan(self):
        assert normalize_header(None) == ""
        assert normalize_header(float("nan")) == ""

    def test_genuinely_different_headers_still_differ(self):
        assert normalize_header("ATT %") != normalize_header("TGT % MD PRO")


# ── Fixtures: a structurally valid workbook ───────────────────────────────────
def _valid_sheets() -> dict[str, list[list]]:
    """A workbook matching config.schema (only the checked positions matter)."""
    md = [
        _pad(["MONTH"], 11),
        _pad(["BRAND_OWNER_LEADER", "COUNTRY", "BRAND_OWNER_EMAIL", "MD TOTAL ($)",
              "MD TOTAL (%)", "TGT % MD TOTAL", "ATT %", "MD PRO ($)",
              "MD PRO (%)", "TGT % MD PRO", "ATT %ㅤ"], 11),
        _pad(["oscar", "AR", "fanny.landazabal@rappi.com", 1, 2, 3, 0.73, 5, 6, 7, 0.76], 11),
    ]
    ads = [
        _pad(["LIDER", "COUNTRY", "KAM", "b", "b", "b", "b", "Targets Bookings",
              "% Att. Bookings", "rg", "rr", "ra", "tr", "% Att. Revenue Real"], 14),
        _pad(["oscar", "AR", "fanny.landazabal@rappi.com", 1, 1, 1, 1, 1, 0.85,
              1, 1, 1, 1, 0.32], 14),
    ]
    churn = [
        _pad(["COUNTRY", "LEADER", "FARMER", "AVA", "x", "x", "x", "GROSS",
              "REACT", "NET", "g%", "n%", "TGT", "ATT - parcial"], 14),
        _pad(["AR", "oscar", "fanny.landazabal@rappi.com", 120, 0, 0, 0, 5, 2, 3,
              0, 0, 0, 0.96], 14),
    ]
    pi = [
        _pad(["WEEK", "Lider", "Farmer", "Brand", "Orden Recomendado",
              "Orden Real", "Prioridad BD", "Palanca", "% Palancas"], 9),
        _pad(["2026-07-06", "oscar", "fanny.landazabal@rappi.com", None,
              1, 2, 3, None, 0.66], 9),
    ]
    prod = [
        _pad(["a", "b", "Medio de Contacto", "d", "¿Contactado?", "f", "g", "h",
              "i", "Week", "k", "l", "m", "n", "Farmer", "Code"] + [f"c{i}" for i in range(16, 41)], 41),
        _pad(["x", "x", "Zoho Voice", "x", "SI", "x", "x", "x", "x", "2026-07-06",
              "x", "x", "x", "x", "fanny.landazabal@rappi.com", "S1"] + ["NO"] * 25, 41),
    ]
    prod[0][26], prod[0][35], prod[0][40] = "Markdown", "Ads", "Churn"
    pen = [
        _pad(["MONTH"], 13),
        _pad(["COUNTRY", "LEADER", "BRAND_OWNER_EMAIL", "Brand ID - Name",
              "Revenue", "GMV", "s0", "s1", "s2", "s3", "s4",
              "Penetración (Media)", "Revenue Perdido"], 13),
        _pad(["AR", "oscar", "fanny.landazabal@rappi.com", "AR1 - Pizza Hut",
              1000, 5000, 0, 0, 0, 0, 0, 0.85, 200], 13),
    ]
    cartera = [
        ["COUNTRY_BRAND_ID", "COUNTRY_STORE_ID", "COUNTRY", "BRAND_NAME",
         "STORE_NAME", "BRAND_OWNER_EMAIL", "BRAND_OWNER_LEADER",
         "BRAND_OWNER_SUBCLASIFICATION"],
        ["AR1", "S1", "AR", "Pizza Hut", "Sucursal 1",
         "fanny.landazabal@rappi.com", "oscar", "PRO"],
    ]
    return {"MD": md, "Ads": ads, "Churn": churn, "PI": pi,
            "Productividad": prod, "Penetración": pen, "Cartera": cartera}


def _to_excel(sheets: dict[str, list[list]]) -> pd.ExcelFile:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for name, rows in sheets.items():
            pd.DataFrame(rows).to_excel(w, sheet_name=name, header=False, index=False)
    buf.seek(0)
    return pd.ExcelFile(buf, engine="openpyxl")


@pytest.fixture
def valid_xl() -> pd.ExcelFile:
    return _to_excel(_valid_sheets())


# ── Happy path ────────────────────────────────────────────────────────────────
def test_valid_workbook_has_no_issues(valid_xl):
    assert validate_workbook(valid_xl) == []


def test_valid_workbook_through_gsheet_adapter():
    """Validation must work identically against the Google Sheets source."""
    from core.gsheet_source import GSheetWorkbook
    wb = GSheetWorkbook(FakeSpreadsheet(_valid_sheets()))
    assert validate_workbook(wb) == []


# ── The failure this whole module exists for ──────────────────────────────────
class TestInsertedColumn:
    def test_inserted_column_in_md_is_caught(self):
        sheets = _valid_sheets()
        # Simulate someone inserting a column before "ATT %": everything shifts.
        for row in sheets["MD"]:
            row.insert(4, "NUEVA COLUMNA")
        issues = validate_workbook(_to_excel(sheets))
        md_errors = [i for i in issues if i.sheet == "MD" and i.severity == "error"]
        assert md_errors, "an inserted column must not pass silently"
        assert any("Columna 6" in i.message for i in md_errors)
        assert any("se insertó o movió" in i.message.lower() for i in md_errors)

    def test_renamed_column_is_caught(self):
        sheets = _valid_sheets()
        sheets["Ads"][0][13] = "Revenue Ajustado"      # not what the loader expects
        issues = validate_workbook(_to_excel(sheets))
        assert any(i.sheet == "Ads" and "Columna 13" in i.message for i in issues)

    def test_cosmetic_header_edit_is_tolerated(self):
        sheets = _valid_sheets()
        sheets["MD"][1][6] = "  att %  "               # spacing/case only
        assert validate_workbook(_to_excel(sheets)) == []


# ── The failure that is happening in production right now ─────────────────────
class TestEmptySheet:
    def test_empty_churn_is_caught(self):
        sheets = _valid_sheets()
        sheets["Churn"] = [sheets["Churn"][0]]         # headers only, no data
        issues = validate_workbook(_to_excel(sheets))
        churn = [i for i in issues if i.sheet == "Churn"]
        assert churn, "an empty Churn tab silently drops 25% of the comp weight"
        assert churn[0].severity == "error"
        assert "vacía" in churn[0].message

    def test_completely_blank_sheet_is_caught(self):
        sheets = _valid_sheets()
        sheets["PI"] = [[None]]
        assert any(i.sheet == "PI" for i in validate_workbook(_to_excel(sheets)))


# ── Missing sheets / Cartera ──────────────────────────────────────────────────
class TestMissingSheets:
    def test_missing_tab_is_reported(self):
        sheets = _valid_sheets()
        del sheets["Penetración"]
        issues = validate_workbook(_to_excel(sheets))
        assert any(i.sheet == "Penetración" and "no existe" in i.message for i in issues)

    def test_accent_drift_in_tab_name_is_tolerated(self):
        sheets = _valid_sheets()
        sheets["Penetracion"] = sheets.pop("Penetración")   # no accent
        issues = validate_workbook(_to_excel(sheets))
        assert not any(i.sheet == "Penetración" and "no existe" in i.message for i in issues)


class TestCartera:
    def test_accepts_brand_owner_email(self, valid_xl):
        assert not [i for i in validate_workbook(valid_xl) if i.sheet == "Cartera"]

    def test_accepts_legacy_email_nuevo(self):
        sheets = _valid_sheets()
        sheets["Cartera"][0][5] = "BRAND_OWNER_EMAIL_NUEVO"
        assert not [i for i in validate_workbook(_to_excel(sheets)) if i.sheet == "Cartera"]

    def test_missing_farmer_column_is_caught(self):
        sheets = _valid_sheets()
        sheets["Cartera"][0][5] = "ALGUNA_OTRA_COSA"
        issues = validate_workbook(_to_excel(sheets))
        assert any(i.sheet == "Cartera" and "email del farmer" in i.message for i in issues)


# ── Reporting ─────────────────────────────────────────────────────────────────
class TestFormatting:
    def test_errors_sort_before_warnings(self):
        issues = [
            ValidationIssue("A", "warning", "w"),
            ValidationIssue("B", "error", "e"),
        ]
        issues.sort(key=lambda i: 0 if i.severity == "error" else 1)
        assert issues[0].severity == "error"

    def test_format_empty(self):
        assert "correcta" in format_issues([])

    def test_format_lists_issues(self):
        out = format_issues([ValidationIssue("MD", "error", "boom")])
        assert "MD" in out and "boom" in out and "ERROR" in out
