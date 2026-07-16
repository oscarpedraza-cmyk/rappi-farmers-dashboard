"""Read the Sheet Maestro directly from Google Sheets instead of an uploaded .xlsx.

The parsing functions in :mod:`core.loader` only ever touch two members of the
``pd.ExcelFile`` object they receive::

    xl.sheet_names          -> list[str]
    xl.parse(name, header=) -> pd.DataFrame

:class:`GSheetWorkbook` implements exactly that surface on top of a gspread
spreadsheet, so every ``load_*`` function keeps working unchanged (and stays
covered by the existing characterization tests) while the data source changes.

Matching pandas' behaviour is the whole game here. Three details matter:

1. **Numbers** — ``get_values()`` returns what the *user sees* ("0,00 %"), which
   is unparseable. We request ``UNFORMATTED_VALUE`` so numbers arrive as floats.
2. **Dates** — under ``UNFORMATTED_VALUE`` dates would arrive as Sheets serial
   numbers, which ``pd.to_datetime`` cannot read. We request
   ``FORMATTED_STRING`` for them so the WEEK columns still parse.
3. **Empty cells** — Sheets returns ``""`` where pandas returns ``NaN``. Left
   alone this silently breaks filters like ``df[3].notna()`` in
   ``load_penetracion``. We normalise ``""`` to ``None``.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Ask the Sheets API for raw numbers but human-readable dates (see module docstring).
_VALUE_RENDER = "UNFORMATTED_VALUE"
_DATETIME_RENDER = "FORMATTED_STRING"


class GSheetWorkbook:
    """A ``pd.ExcelFile``-compatible reader backed by a Google Spreadsheet.

    Only the surface used by :mod:`core.loader` and ``app.py`` is implemented:
    :attr:`sheet_names` and :meth:`parse`.

    Values are fetched lazily per worksheet and cached for the lifetime of the
    instance, so parsing eight tabs costs eight API calls, not eight per call.
    """

    def __init__(self, spreadsheet: Any) -> None:
        """
        Args:
            spreadsheet: An open ``gspread.Spreadsheet`` (or any object exposing
                ``worksheets()`` and ``worksheet(title)``).
        """
        self._sh = spreadsheet
        self._values_cache: dict[str, list[list[Any]]] = {}
        self._titles: list[str] | None = None

    # ── pd.ExcelFile-compatible surface ───────────────────────────────────────
    @property
    def sheet_names(self) -> list[str]:
        """Titles of every worksheet, in tab order (mirrors ExcelFile.sheet_names)."""
        if self._titles is None:
            self._titles = [ws.title for ws in self._sh.worksheets()]
        return self._titles

    def parse(
        self,
        sheet_name: str,
        header: int | None = 0,
        nrows: int | None = None,
        **_ignored: Any,
    ) -> pd.DataFrame:
        """Read one worksheet into a DataFrame, mimicking ``ExcelFile.parse``.

        Args:
            sheet_name: Worksheet title.
            header: Row index to use as column names, or ``None`` for integer
                columns (which is what most ``load_*`` functions rely on).
            nrows: Optional cap on returned rows (used for sheet probing).
            **_ignored: Accepted and discarded so callers can pass pandas-only
                kwargs without breaking.

        Returns:
            A DataFrame whose dtypes and empty-cell handling match what pandas
            produces from the equivalent .xlsx.
        """
        rows = self._raw_values(sheet_name)
        if not rows:
            return pd.DataFrame()

        rows = _rectangular(rows)

        if header is None:
            df = pd.DataFrame(rows)
        else:
            if header >= len(rows):
                return pd.DataFrame()
            columns = [str(c) for c in rows[header]]
            df = pd.DataFrame(rows[header + 1:], columns=columns)

        if nrows is not None:
            df = df.head(nrows)
        return df

    # ── Internals ─────────────────────────────────────────────────────────────
    def _raw_values(self, sheet_name: str) -> list[list[Any]]:
        """Fetch (and cache) a worksheet's values with pandas-like empty cells."""
        if sheet_name in self._values_cache:
            return self._values_cache[sheet_name]

        ws = self._sh.worksheet(sheet_name)
        try:
            values = ws.get_values(
                value_render_option=_VALUE_RENDER,
                date_time_render_option=_DATETIME_RENDER,
            )
        except TypeError:
            # Older gspread signatures don't accept the render options; fall back
            # rather than fail, and say so — formatted numbers may need coercion.
            logger.warning(
                "[gsheet_source] '%s': gspread rejected render options; "
                "falling back to formatted values", sheet_name,
            )
            values = ws.get_values()

        values = [[_clean_cell(c) for c in row] for row in (values or [])]
        self._values_cache[sheet_name] = values
        return values


def _clean_cell(value: Any) -> Any:
    """Normalise a Sheets cell to what pandas would produce for an .xlsx cell.

    Sheets sends ``""`` for a blank cell; pandas sends ``NaN``. Returning None
    keeps ``.notna()`` / ``.dropna()`` filters behaving identically.
    """
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _rectangular(rows: list[list[Any]]) -> list[list[Any]]:
    """Pad ragged rows to equal width.

    Sheets truncates trailing empty cells per row, so rows come back with
    different lengths; pandas always yields a rectangle.
    """
    width = max((len(r) for r in rows), default=0)
    return [list(r) + [None] * (width - len(r)) for r in rows]


# ── Opening a workbook ────────────────────────────────────────────────────────
def open_workbook(spreadsheet_id: str, client: Any = None) -> GSheetWorkbook | None:
    """Open a spreadsheet by id and wrap it as a :class:`GSheetWorkbook`.

    Args:
        spreadsheet_id: The id from the sheet URL
            (``/spreadsheets/d/<ID>/edit``).
        client: An authorised gspread client. When omitted, the shared client
            from :mod:`core.db` is used so credentials are configured in one place.

    Returns:
        The wrapped workbook, or None when auth fails or the sheet is
        unreachable (most often: the sheet was never shared with the service
        account). The reason is logged.
    """
    if client is None:
        from core.db import _gsheet_client
        client = _gsheet_client()
    if client is None:
        logger.warning(
            "[gsheet_source] no Google credentials available "
            "(GOOGLE_CREDS unset or invalid)"
        )
        return None

    try:
        return GSheetWorkbook(client.open_by_key(spreadsheet_id))
    except Exception as e:
        logger.error(
            "[gsheet_source] cannot open spreadsheet %s: %s "
            "(is it shared with the service account?)", spreadsheet_id, e,
        )
        return None
