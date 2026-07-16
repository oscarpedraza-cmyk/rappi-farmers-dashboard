"""Tests for the Google Sheets source adapter.

The headline tests are the equivalence ones: every ``load_*`` function must
return byte-for-byte the same result whether it is fed a real .xlsx or the
GSheetWorkbook adapter. That is what makes swapping the data source safe.
"""
from __future__ import annotations

import pandas as pd
import pytest

from core import loader
from core.gsheet_source import GSheetWorkbook, _clean_cell, _rectangular, open_workbook


# ── ExcelFile-compatible surface ──────────────────────────────────────────────
class TestSheetNames:
    def test_lists_all_tabs(self, gxl):
        assert set(gxl.sheet_names) == {"MD", "Ads", "Churn", "Penetración", "Gaps"}

    def test_is_cached(self, gxl, fake_spreadsheet):
        gxl.sheet_names
        fake_spreadsheet._ws.clear()      # a second fetch would now fail/return []
        assert "MD" in gxl.sheet_names    # served from cache


class TestParse:
    def test_header_none_gives_integer_columns(self, gxl):
        df = gxl.parse("MD", header=None)
        assert list(df.columns) == list(range(11))
        assert df.iloc[0, 0] == "MONTH"

    def test_header_zero_uses_first_row_as_columns(self, gxl):
        df = gxl.parse("Churn", header=0)
        assert df.columns[2] == "FARMER"
        assert df.iloc[0]["FARMER"] == "fanny.landazabal@rappi.com"

    def test_nrows_caps_result(self, gxl):
        assert len(gxl.parse("MD", header=0, nrows=2)) == 2

    def test_unknown_kwargs_are_ignored(self, gxl):
        # callers may pass pandas-only kwargs; must not raise
        df = gxl.parse("MD", header=None, dtype=str, usecols=[0])
        assert not df.empty

    def test_values_are_fetched_once_per_sheet(self, gxl, fake_spreadsheet):
        calls = {"n": 0}
        original = fake_spreadsheet._ws["MD"].get_values

        def counting(**kwargs):
            calls["n"] += 1
            return original(**kwargs)

        fake_spreadsheet._ws["MD"].get_values = counting
        gxl.parse("MD", header=None)
        gxl.parse("MD", header=None)
        assert calls["n"] == 1


# ── The pandas-compatibility details that matter ──────────────────────────────
class TestCellNormalisation:
    def test_blank_becomes_none_not_empty_string(self):
        # This is the one that silently breaks df[3].notna() in load_penetracion
        assert _clean_cell("") is None
        assert _clean_cell("   ") is None

    def test_real_values_pass_through(self):
        assert _clean_cell(0.7353) == 0.7353
        assert _clean_cell("Pizza Hut") == "Pizza Hut"
        assert _clean_cell(0) == 0        # zero must NOT be treated as blank

    def test_blanks_are_na_in_dataframe(self, gxl):
        df = gxl.parse("MD", header=None)
        # row 0 is ["MONTH", blank, blank, …] → must behave like NaN for pandas
        assert df.iloc[0, 1] is None or pd.isna(df.iloc[0, 1])
        assert not df.iloc[0].notna().all()

    def test_midrow_blank_matches_pandas_dropna(self, xl, gxl):
        """The case that actually bites in production.

        load_productividad counts unique accounts with
        ``sub[store_col].dropna().unique()``. A blank store arriving as ""
        instead of NaN silently counts as a real account and inflates the
        denominator of pct_no_contactados. Trailing blanks are truncated by the
        API, so only a mid-row gap like this one exercises the normalisation.
        """
        from_gsheet = gxl.parse("Gaps", header=0)["store"].dropna().tolist()
        from_xlsx = xl.parse("Gaps", header=0)["store"].dropna().tolist()
        assert from_gsheet == from_xlsx == ["S2"]

    def test_midrow_blank_matches_pandas_notna(self, xl, gxl):
        assert (
            gxl.parse("Gaps", header=0)["store"].notna().tolist()
            == xl.parse("Gaps", header=0)["store"].notna().tolist()
            == [False, True]
        )


class TestRectangular:
    def test_pads_ragged_rows(self):
        assert _rectangular([[1], [1, 2, 3]]) == [[1, None, None], [1, 2, 3]]

    def test_empty_input(self):
        assert _rectangular([]) == []

    def test_truncated_trailing_blanks_are_restored(self, gxl):
        # FakeWorksheet truncates trailing blanks like the real API does;
        # the adapter must pad them back so column indices stay aligned.
        df = gxl.parse("MD", header=None)
        assert df.shape[1] == 11


# ── Equivalence: .xlsx vs Google Sheets ───────────────────────────────────────
class TestSourceEquivalence:
    """Same data, two sources, identical loader output."""

    def test_load_md_identical(self, xl, gxl):
        assert loader.load_md(gxl) == loader.load_md(xl)

    def test_load_ads_identical(self, xl, gxl):
        assert loader.load_ads(gxl) == loader.load_ads(xl)

    def test_load_churn_identical(self, xl, gxl):
        assert loader.load_churn(gxl) == loader.load_churn(xl)

    def test_load_penetracion_identical(self, xl, gxl):
        assert loader.load_penetracion(gxl) == loader.load_penetracion(xl)

    def test_md_values_are_real_numbers_not_display_strings(self, gxl):
        # Guards against the "0,00 %" formatted-string trap.
        md = loader.load_md(gxl)
        assert md["fanny.landazabal@rappi.com"]["ATT_MD_Total"] == pytest.approx(0.7353)

    def test_penetracion_risk_filter_survives_the_source_swap(self, gxl):
        brands = loader.load_penetracion(gxl)["fanny.landazabal@rappi.com"]
        assert brands == ["Pizza Hut"]     # Burger (15%) and Total excluded


# ── open_workbook ─────────────────────────────────────────────────────────────
class TestOpenWorkbook:
    def test_returns_none_without_credentials(self, monkeypatch, caplog):
        monkeypatch.setattr("core.db._gsheet_client", lambda: None)
        assert open_workbook("some-id") is None
        assert "no Google credentials" in caplog.text

    def test_returns_none_when_sheet_unreachable(self, caplog):
        class Boom:
            def open_by_key(self, _key):
                raise PermissionError("The caller does not have permission")

        assert open_workbook("some-id", client=Boom()) is None
        assert "shared with the service account" in caplog.text

    def test_wraps_spreadsheet_on_success(self, fake_spreadsheet):
        class Client:
            def open_by_key(self, _key):
                return fake_spreadsheet

        wb = open_workbook("some-id", client=Client())
        assert isinstance(wb, GSheetWorkbook)
        assert "MD" in wb.sheet_names
