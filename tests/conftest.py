"""Shared pytest fixtures and path setup for the test suite.

Ensures the project root is importable so ``import core.xxx`` works when pytest
is invoked from anywhere, and defines one synthetic Sheet Maestro dataset that
is served through BOTH sources (.xlsx and the Google Sheets adapter). Sharing a
single dataset is what makes the equivalence tests meaningful.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── Synthetic Sheet Maestro (mirrors real column positions per tab) ───────────
def _pad(row: list, width: int) -> list:
    return row + [None] * (width - len(row))


# MD: row0 MONTH, row1 headers, data from row2. col2=email, col6=Total, col10=Pro
_MD = [
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
_ADS = [
    _pad(["LIDER", "COUNTRY", "KAM", "b", "b", "b", "b", "TGT",
          "ATT_BOOK", "rg", "rr", "ra", "tr", "ATT_REV"], 14),
    _pad(["oscar", "AR", "fanny.landazabal@rappi.com", 1, 1, 1, 1, 1,
          0.8554, 1, 1, 1, 1, 0.3282], 14),
    _pad(["oscar", "AR", "Total", 1, 1, 1, 1, 1, 0.9, 1, 1, 1, 1, 0.9], 14),
]

# Churn: row0 headers, data from row1.
# col2=email col3=ava col7=gross col8=react col9=net col13=ATT
_CHURN = [
    _pad(["COUNTRY", "LEADER", "FARMER", "AVA", "x", "x", "x", "GROSS",
          "REACT", "NET", "g%", "n%", "TGT", "ATT"], 14),
    _pad(["AR", "oscar", "fanny.landazabal@rappi.com", 120, 0, 0, 0, 5,
          2, 3, 0, 0, 0, 0.9600], 14),
]

# Penetración: row0 MONTH, row1 headers, data from row2.
# col2=email col3="ID - Name" col4=revenue col11=pen_media col12=rev_perdido
_PEN = [
    _pad(["MONTH"], 13),
    _pad(["COUNTRY", "LEADER", "EMAIL", "BRAND", "REV", "GMV",
          "s0", "s1", "s2", "s3", "s4", "PEN", "REVLOST"], 13),
    # high penetration (>70%) → belongs in brands_riesgo
    _pad(["AR", "oscar", "fanny.landazabal@rappi.com", "AR1 - Pizza Hut",
          1000, 5000, 0, 0, 0, 0, 0, 0.85, 200], 13),
    # low penetration → must NOT appear
    _pad(["AR", "oscar", "fanny.landazabal@rappi.com", "AR2 - Burger",
          800, 4000, 0, 0, 0, 0, 0, 0.15, 50], 13),
    # Total row → filtered out
    _pad(["AR", "oscar", "fanny.landazabal@rappi.com", "Total",
          1800, 9000, 0, 0, 0, 0, 0, 0.5, 250], 13),
]

# Gaps: a sheet with MID-ROW blanks. The Sheets API truncates *trailing* blanks
# (so those never reach cell normalisation), which means only a mid-row gap
# exercises the ""-vs-NaN behaviour that load_productividad's
# `sub[store_col].dropna().unique()` and load_cartera's `dropna(how="all")`
# depend on. Without this sheet the source-equivalence tests pass even when
# normalisation is broken.
_GAPS = [
    ["id", "store", "flag"],
    ["r1", None, "SI"],     # blank store, mid-row → must behave as NaN
    ["r2", "S2", "NO"],
]

MAESTRO_SHEETS: dict[str, list[list[Any]]] = {
    "MD": _MD,
    "Ads": _ADS,
    "Churn": _CHURN,
    "Penetración": _PEN,
    "Gaps": _GAPS,
}


# ── Source 1: a real .xlsx parsed by pandas ───────────────────────────────────
@pytest.fixture
def xl() -> pd.ExcelFile:
    """The synthetic Sheet Maestro as a pandas ExcelFile (the current source)."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, rows in MAESTRO_SHEETS.items():
            pd.DataFrame(rows).to_excel(writer, sheet_name=name, header=False, index=False)
    buf.seek(0)
    return pd.ExcelFile(buf, engine="openpyxl")


# ── Source 2: a fake Google Spreadsheet behind the adapter ────────────────────
class FakeWorksheet:
    """Mimics gspread: blanks come back as "" and trailing blanks are truncated."""

    def __init__(self, title: str, rows: list[list[Any]]) -> None:
        self.title = title
        self._rows = rows

    def get_values(self, **_kwargs: Any) -> list[list[Any]]:
        out = []
        for row in self._rows:
            cells = ["" if c is None else c for c in row]
            while cells and cells[-1] == "":   # Sheets truncates trailing blanks
                cells.pop()
            out.append(cells)
        return out


class FakeSpreadsheet:
    def __init__(self, sheets: dict[str, list[list[Any]]]) -> None:
        self._ws = {name: FakeWorksheet(name, rows) for name, rows in sheets.items()}

    def worksheets(self) -> list[FakeWorksheet]:
        return list(self._ws.values())

    def worksheet(self, title: str) -> FakeWorksheet:
        if title not in self._ws:
            raise ValueError(f"Worksheet not found: {title}")
        return self._ws[title]


@pytest.fixture
def fake_spreadsheet() -> FakeSpreadsheet:
    return FakeSpreadsheet(MAESTRO_SHEETS)


@pytest.fixture
def gxl(fake_spreadsheet: FakeSpreadsheet):
    """The same Sheet Maestro served through the Google Sheets adapter."""
    from core.gsheet_source import GSheetWorkbook
    return GSheetWorkbook(fake_spreadsheet)
