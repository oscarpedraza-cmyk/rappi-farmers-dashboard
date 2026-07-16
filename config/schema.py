"""Expected Sheet Maestro structure, used to validate a workbook before parsing.

Why this exists
---------------
``core.loader`` reads the Maestro **by column position** (``col 6`` is MD Total,
``col 13`` is Ads Revenue, …). That is fast and works, but it fails *silently*:
insert one column in the source sheet and every farmer gets wrong numbers with
no error anywhere. The risk grows once the source is a live Google Sheet that
several people can edit.

These schemas pin the header text expected at each position that the loader
actually reads, so :func:`core.validation.validate_workbook` can turn silent
corruption into a loud, specific message.

Only sheets read positionally are listed. ``Cartera`` is resolved by column
*name* in the loader, so it is validated differently (presence, not position).

All header names below were verified against a real Sheet_Maestro_Farmers.xlsx
(July 2026). ``Churn`` is intentionally absent: the tab was empty in the source,
so its headers could not be verified — guessing would produce false alarms.
The emptiness itself is reported by the validator's empty-sheet check.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SheetSchema:
    """Expected layout of one worksheet.

    Attributes:
        header_row: 0-based index of the row holding the column headers.
        expected: ``{column_index: expected_header_text}`` for the positions the
            loader depends on. Comparison is normalised (see
            :func:`core.validation.normalize_header`), so casing and invisible
            characters do not cause false alarms.
        min_data_rows: Fewest data rows for the sheet to be considered usable.
    """

    header_row: int
    expected: dict[int, str] = field(default_factory=dict)
    min_data_rows: int = 1


SHEET_SCHEMAS: dict[str, SheetSchema] = {
    "MD": SheetSchema(
        header_row=1,
        # NOTE: col 10 is literally "ATT %ㅤ" in the source — a Hangul Filler
        # keeps it distinct from col 6's "ATT %". Normalisation strips it, so both
        # compare as "att %"; position is what tells them apart.
        expected={2: "BRAND_OWNER_EMAIL", 6: "ATT %", 10: "ATT %"},
    ),
    "Ads": SheetSchema(
        header_row=0,
        expected={2: "KAM", 8: "% Att. Bookings", 13: "% Att. Revenue Real"},
    ),
    "PI": SheetSchema(
        header_row=0,
        expected={2: "Farmer", 8: "% Palancas"},
    ),
    "Penetración": SheetSchema(
        header_row=1,
        expected={
            2: "BRAND_OWNER_EMAIL",
            3: "Brand ID - Name",
            4: "Revenue",
            11: "Penetración (Media)",
            12: "Revenue Perdido",
        },
    ),
    "Productividad": SheetSchema(
        header_row=0,
        expected={
            2: "Medio de Contacto",
            4: "¿Contactado?",
            9: "Week",
            14: "Farmer",
            15: "Code",
            26: "Markdown",
            35: "Ads",
            40: "Churn",
        },
    ),
}

# Sheets the app needs but which are resolved by column name, not position.
# The loader looks for a column containing "email_nuevo" and falls back to
# BRAND_OWNER_EMAIL; at least one of these must be present.
CARTERA_FARMER_COLUMN_CANDIDATES: tuple[str, ...] = (
    "brand_owner_email_nuevo",
    "brand_owner_email",
)

# Tabs expected to carry data. Listed separately from SHEET_SCHEMAS because a
# tab can be present-but-empty, which is its own (silent) failure mode: an empty
# Churn tab makes ATT_Churn None, and calcular_variable_score then drops Churn's
# 25% weight from the denominator without telling anyone.
EXPECTED_DATA_SHEETS: tuple[str, ...] = (
    "MD", "Ads", "Churn", "PI", "Productividad", "Penetración", "Cartera",
)
