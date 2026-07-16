"""Validate a Sheet Maestro workbook before its numbers reach anyone.

The loader reads by column position, so a single inserted column in the source
silently produces wrong numbers for every farmer. This module checks the
workbook's shape first and reports problems as data, letting the caller decide
whether to warn or refuse.

Works against either source: a ``pd.ExcelFile`` or a
:class:`core.gsheet_source.GSheetWorkbook` — both expose ``sheet_names`` and
``parse()``.
"""
from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd

from config.schema import (
    CARTERA_FARMER_COLUMN_CANDIDATES,
    EXPECTED_DATA_SHEETS,
    SHEET_SCHEMAS,
)

logger = logging.getLogger(__name__)

Severity = Literal["error", "warning"]

# Invisible characters that show up in real spreadsheet headers and would break
# a naive equality check. U+3164 (Hangul Filler) is a real one: the Maestro's MD
# tab uses it to keep a second "ATT %" header distinct from the first. It is
# category Lo (a letter!), so str.strip() does not remove it.
#
# U+1160 must be listed next to U+3164: NFKC rewrites U+3164 -> U+1160, so
# stripping only the original codepoint *after* normalising silently misses it.
# Only truly zero-width characters belong here. A no-break space (U+00A0) must
# NOT: it is a space, and deleting it would join words ("Revenue Perdido" ->
# "revenueperdido"). NFKC already folds it to a plain space, which the final
# whitespace collapse then handles.
_INVISIBLE_CHARS = frozenset([
    "ㅤ",   # Hangul Filler
    "ᅠ",   # Hangul Jungseong Filler (what NFKC turns U+3164 into)
    "​",   # Zero width space
    "‌",   # Zero width non-joiner
    "‍",   # Zero width joiner
    "﻿",   # BOM / zero width no-break space
])


@dataclass(frozen=True)
class ValidationIssue:
    """One problem found in a workbook.

    Attributes:
        sheet: Worksheet the problem belongs to.
        severity: ``"error"`` means the numbers cannot be trusted;
            ``"warning"`` means something is off but parsing will still work.
        message: Human-readable description, safe to show in the UI.
    """

    sheet: str
    severity: Severity
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.sheet}: {self.message}"


def normalize_header(value: Any) -> str:
    """Reduce a header cell to a comparable form.

    Strips invisible characters, folds accents and casefolds, so ``"ATT %ㅤ"``,
    ``"att  %"`` and ``"ATT %"`` all compare equal — and ``"Penetracion"`` matches
    ``"Penetración"``, the same tolerance ``load_sheet_maestro`` already has for
    tab names. A genuinely different header still does not match.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = _strip_invisible(str(value))
    # NFKC first (unifies compatibility forms), then strip again: NFKC can *map*
    # an invisible character to a different invisible one.
    text = _strip_invisible(unicodedata.normalize("NFKC", text))
    # Fold accents: decompose, then drop the combining marks.
    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(text.split()).casefold()


def _strip_invisible(text: str) -> str:
    """Remove characters that are present but render as nothing."""
    return "".join(c for c in text if c not in _INVISIBLE_CHARS)


def validate_workbook(xl: Any) -> list[ValidationIssue]:
    """Check a workbook against the expected Sheet Maestro structure.

    Args:
        xl: A ``pd.ExcelFile`` or ``GSheetWorkbook``.

    Returns:
        Every issue found, worst first (errors before warnings). An empty list
        means the workbook matches what the loader expects.
    """
    issues: list[ValidationIssue] = []
    try:
        names = list(xl.sheet_names)
    except Exception as e:
        logger.error("[validation] cannot list sheets: %s", e)
        return [ValidationIssue("<workbook>", "error", f"No se pudieron leer las pestañas: {e}")]

    issues += _check_missing_sheets(names)
    issues += _check_positional_schemas(xl, names)
    issues += _check_empty_sheets(xl, names)
    issues += _check_cartera(xl, names)

    issues.sort(key=lambda i: 0 if i.severity == "error" else 1)
    return issues


def _check_missing_sheets(names: list[str]) -> list[ValidationIssue]:
    present = {normalize_header(n) for n in names}
    return [
        ValidationIssue(sheet, "error", "La pestaña no existe en el archivo.")
        for sheet in EXPECTED_DATA_SHEETS
        if normalize_header(sheet) not in present
    ]


def _resolve(names: list[str], wanted: str) -> str | None:
    """Find the real tab title matching `wanted`, tolerating case/accents drift."""
    target = normalize_header(wanted)
    return next((n for n in names if normalize_header(n) == target), None)


def _check_positional_schemas(xl: Any, names: list[str]) -> list[ValidationIssue]:
    """The core check: is the expected header still at the expected position?"""
    issues: list[ValidationIssue] = []
    for sheet, schema in SHEET_SCHEMAS.items():
        real_name = _resolve(names, sheet)
        if real_name is None:
            continue    # already reported by _check_missing_sheets

        try:
            df = xl.parse(real_name, header=None)
        except Exception as e:
            issues.append(ValidationIssue(sheet, "error", f"No se pudo leer: {e}"))
            continue

        if len(df) <= schema.header_row:
            continue    # empty sheet — reported by _check_empty_sheets

        header = df.iloc[schema.header_row].tolist()
        for idx, expected in schema.expected.items():
            if idx >= len(header):
                issues.append(ValidationIssue(
                    sheet, "error",
                    f"Falta la columna {idx} (se esperaba «{expected}»). "
                    f"La pestaña tiene {len(header)} columnas.",
                ))
                continue
            found = header[idx]
            if normalize_header(found) != normalize_header(expected):
                issues.append(ValidationIssue(
                    sheet, "error",
                    f"Columna {idx}: se esperaba «{expected}» pero hay «{found}». "
                    "¿Se insertó o movió una columna? Los datos leídos serían incorrectos.",
                ))
    return issues


def _check_empty_sheets(xl: Any, names: list[str]) -> list[ValidationIssue]:
    """Catch present-but-empty tabs.

    This is the check that flags an empty Churn tab — which silently removes
    25% of the compensation weight for every farmer.
    """
    issues: list[ValidationIssue] = []
    for sheet in EXPECTED_DATA_SHEETS:
        real_name = _resolve(names, sheet)
        if real_name is None:
            continue

        schema = SHEET_SCHEMAS.get(sheet)
        header_row = schema.header_row if schema else 0
        min_rows = schema.min_data_rows if schema else 1

        try:
            df = xl.parse(real_name, header=None)
        except Exception:
            continue    # reported elsewhere

        data_rows = max(len(df) - (header_row + 1), 0)
        if data_rows < min_rows:
            issues.append(ValidationIssue(
                sheet, "error",
                "La pestaña está vacía (0 filas de datos). "
                "Las métricas que dependen de ella se calcularán sin datos.",
            ))
    return issues


def _check_cartera(xl: Any, names: list[str]) -> list[ValidationIssue]:
    """Cartera is resolved by column name, so check presence rather than position."""
    real_name = _resolve(names, "Cartera")
    if real_name is None:
        return []
    try:
        df = xl.parse(real_name, header=0)
    except Exception as e:
        return [ValidationIssue("Cartera", "error", f"No se pudo leer: {e}")]

    cols = {normalize_header(c) for c in df.columns}
    if not any(c in cols for c in CARTERA_FARMER_COLUMN_CANDIDATES):
        return [ValidationIssue(
            "Cartera", "error",
            "No se encontró una columna de email del farmer "
            f"(se buscó: {', '.join(CARTERA_FARMER_COLUMN_CANDIDATES)}).",
        )]
    return []


def format_issues(issues: list[ValidationIssue]) -> str:
    """Render issues as a short plain-text block for logs or the UI."""
    if not issues:
        return "Estructura del Sheet Maestro correcta."
    return "\n".join(f"• {i}" for i in issues)
