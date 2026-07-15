from __future__ import annotations

import logging
import math
import traceback

import pandas as pd
import numpy as np
from datetime import date

logger = logging.getLogger(__name__)


FARMERS_EMAILS = [
    "maira.franco@rappi.com",
    "micheel.espitia@rappi.com",
    "arnold.camino@rappi.com",
    "lady.bobativa@rappi.com",
    "fanny.landazabal@rappi.com",
    "claudia.pineda@rappi.com",
    "esteban.castano@rappi.com",
    "luisfernando.hernandez@rappi.com",
    "alejandro.salamanca@rappi.com",
    "angie.contreras@rappi.com",
    "diana.saavedra@rappi.com",
    "maria.pedraza@rappi.com",
    "sabas.ramirez@rappi.com",
]

# Farmers excluidos (renuncia, licencia, etc.) — no aparecen en el dashboard
EXCLUDED_EMAILS = {
    "vanesa.fernandez@rappi.com",   # renuncia voluntaria mayo 2026
    "luis.ibarra@rappi.com",        # salida julio 2026
}

FARMER_NAMES = {
    "maira.franco@rappi.com": "Maira Franco",
    "micheel.espitia@rappi.com": "Micheel Espitia",
    "arnold.camino@rappi.com": "Arnold Camino",
    "lady.bobativa@rappi.com": "Lady Bobativa",
    "fanny.landazabal@rappi.com": "Fanny Landazabal",
    "claudia.pineda@rappi.com": "Claudia Pineda",
    "esteban.castano@rappi.com": "Esteban Castaño",
    "luisfernando.hernandez@rappi.com": "Luis Fernando Hernández",
    "alejandro.salamanca@rappi.com": "Alejandro Salamanca",
    "angie.contreras@rappi.com": "Angie Contreras",
    "diana.saavedra@rappi.com": "Diana Saavedra",
    "maria.pedraza@rappi.com": "Maria Pedraza",
    "sabas.ramirez@rappi.com": "Sabas Ramirez",
}

SLACK_IDS = {
    "oscar.pedraza@rappi.com": "U09BXG9V64V",
    "maira.franco@rappi.com": "U0A2GM2TXTQ",
    "micheel.espitia@rappi.com": "U04KTCXR4SC",
    "arnold.camino@rappi.com": "U099GE8J2F9",
    "lady.bobativa@rappi.com": "U06JFH95KPD",
    "fanny.landazabal@rappi.com": "U09KHT8737C",
    "claudia.pineda@rappi.com": "U0A1PTFBB0B",
    "esteban.castano@rappi.com": "U09488QUV19",
    "luisfernando.hernandez@rappi.com": "UMEALSBS7",
    "alejandro.salamanca@rappi.com": "U095P47BZ5X",
    "angie.contreras@rappi.com": "U08H6NS5J2C",
    "diana.saavedra@rappi.com": "U0AAUHTG9DH",
    "maria.pedraza@rappi.com": "U09TT5M0CR2",
    "vanesa.fernandez@rappi.com": "U0AR2626PAA",
}


def _is_farmer_email(val):
    return isinstance(val, str) and "@rappi" in val.lower() and val.strip().lower() not in (
        "oscar.pedraza@rappi.com",
    )


def load_churn(xl):
    """
    Structure: header row 0, data from row 1.
    Col 0: COUNTRY | Col 1: LEADER | Col 2: FARMER
    Col 7: Gross Churn | Col 8: Reactivaciones | Col 9: Net Churn
    Col 10: Gross% | Col 11: Net% | Col 12: TGT | Col 13: ATT - parcial
    """
    try:
        df = xl.parse("Churn", header=None)
        df = df.iloc[1:].copy()
        df.columns = range(len(df.columns))
        df = df[df[2].apply(_is_farmer_email)].copy()
        df[2] = df[2].str.strip().str.lower()

        for col in [13, 8, 7, 9, 3]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        result = (
            df.set_index(2)[[13, 8, 7, 9, 3]]
            .rename(columns={13: "ATT_Churn", 8: "Reactivaciones",
                              7: "Gross_Churn", 9: "Net_Churn", 3: "Ava_Stores"})
            .to_dict("index")
        )
        return result
    except Exception as e:
        logger.error("[loader] Churn error: %s", e)
        return {}


def load_md(xl):
    """
    Structure: MONTH row 0, headers row 1, data from row 2.
    Col 0: LEADER | Col 1: COUNTRY | Col 2: FARMER
    Col 6: ATT % MD Total | Col 10: ATT % MD Pro
    Filter: col 2 has @rappi (excludes Total rows)
    """
    try:
        df = xl.parse("MD", header=None)
        df = df.iloc[2:].copy()
        df.columns = range(len(df.columns))
        df = df[df[2].apply(_is_farmer_email)].copy()
        df[2] = df[2].str.strip().str.lower()

        for col in [6, 10]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        result = (
            df.set_index(2)[[6, 10]]
            .rename(columns={6: "ATT_MD_Total", 10: "ATT_MD_Pro"})
            .to_dict("index")
        )
        return result
    except Exception as e:
        logger.error("[loader] MD error: %s", e)
        return {}


def load_ads(xl):
    """
    Structure: header row 0, data from row 1.
    Col 0: LIDER | Col 1: COUNTRY | Col 2: KAM (farmer)
    Col 8: % Att. Bookings | Col 13: % Att. Revenue Real
    Filter: col 2 has @rappi (excludes Total rows)
    """
    try:
        df = xl.parse("Ads", header=None)
        df = df.iloc[1:].copy()
        df.columns = range(len(df.columns))
        df = df[df[2].apply(_is_farmer_email)].copy()
        df[2] = df[2].str.strip().str.lower()

        for col in [8, 13]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        result = (
            df.set_index(2)[[8, 13]]
            .rename(columns={8: "ATT_Book", 13: "ATT_Rev_real"})
            .to_dict("index")
        )
        return result
    except Exception as e:
        logger.error("[loader] Ads error: %s", e)
        return {}


def load_pi(xl):
    """
    Reads Pitch Integral from the PI sheet.

    Strategy A — 'Total' aggregate row:
      Some sheet versions have a summary row per farmer where col 3 = 'Total'.
      We look for that row and read % Palancas from col 10 (or nearby).

    Strategy B — average across all weeks:
      If no 'Total' row exists, the monthly PI is the average of all weekly
      per-farmer rows. We detect the pitch column automatically.

    Returns {farmer_email: {"Pitch_Pct": float, "_pi_rows": [weekly floats]}}
    """
    try:
        df = xl.parse("PI", header=None)
        df = df.iloc[1:].copy()
        df.columns = range(len(df.columns))
        n_cols = len(df.columns)

        # ── Find farmer-email column (try 2, then 1, 0, 3) ──────────────────
        farmer_col = None
        for c in [2, 1, 3, 0]:
            if c < n_cols and df[c].apply(_is_farmer_email).any():
                farmer_col = c
                break
        if farmer_col is None:
            logger.warning("[loader] PI: no se encontró columna de email farmer")
            return {}

        df_all = df[df[farmer_col].apply(_is_farmer_email)].copy()
        df_all[farmer_col] = df_all[farmer_col].str.strip().str.lower()

        # ── Strategy A: look for 'Total' tag in neighbouring columns ─────────
        for tag_col in [3, 4, farmer_col + 1, farmer_col + 2]:
            if tag_col == farmer_col or tag_col >= n_cols:
                continue
            mask_total = df_all[tag_col].astype(str).str.strip().str.lower() == "total"
            if mask_total.sum() < 1:
                continue
            df_total = df_all[mask_total].copy()
            # Try pitch columns 10, 9, 11, 8 — accept first with plausible decimals
            for pitch_col in [10, 9, 11, 8, 7]:
                if pitch_col >= n_cols:
                    continue
                vals = pd.to_numeric(df_total[pitch_col], errors="coerce")
                valid = vals.dropna()
                if not valid.empty and valid.between(0, 1.5).mean() >= 0.5:
                    df_total = df_total.copy()
                    df_total["_v"] = pd.to_numeric(df_total[pitch_col], errors="coerce")
                    result = {}
                    for rec in df_total[[farmer_col, "_v"]].to_dict("records"):
                        farmer = rec[farmer_col]
                        v = rec["_v"]
                        result[farmer] = {"Pitch_Pct": v if pd.notna(v) else None,
                                          "_pi_rows": [v] if pd.notna(v) else []}
                    logger.info("[loader] PI: Strategy A → %d farmers (tag_col=%d, pitch_col=%d)",
                                len(result), tag_col, pitch_col)
                    return result

        # ── Strategy B: average all rows per farmer ───────────────────────────
        # Find the column whose values (for farmer rows) are mostly in [0, 1]
        best_pitch_col = None
        best_coverage  = 0
        for pitch_col in [10, 9, 11, 8, 7, 12]:
            if pitch_col >= n_cols:
                continue
            vals = pd.to_numeric(df_all[pitch_col], errors="coerce")
            in_range = vals.between(0, 1).sum()
            coverage = in_range / max(len(df_all), 1)
            if coverage > best_coverage:
                best_coverage  = coverage
                best_pitch_col = pitch_col

        if best_pitch_col is None or best_coverage < 0.3:
            logger.warning("[loader] PI: Strategy B no encontró columna válida (best_coverage=%.2f)", best_coverage)
            return {}

        df_all["_val"] = pd.to_numeric(df_all[best_pitch_col], errors="coerce")
        result = {}
        for farmer, group in df_all.groupby(farmer_col):
            weekly_vals = group["_val"].dropna().tolist()
            avg = float(np.nanmean(weekly_vals)) if weekly_vals else None
            result[farmer] = {"Pitch_Pct": round(avg, 4) if avg is not None else None,
                              "_pi_rows": weekly_vals}
        logger.info("[loader] PI: Strategy B → %d farmers (pitch_col=%d, coverage=%.0%%)",
                    len(result), best_pitch_col, best_coverage * 100)
        return result

    except Exception as e:
        logger.error("[loader] PI error: %s", e, exc_info=True)
        return {}


def load_productividad(xl):
    """
    Structure: header row 0, data from row 1.
    Col 2: Medio de Contacto | Col 4: ¿Contactado?
    Col 9: Week | Col 14: Farmer | Col 15: Code (store ID)
    Col 26: Markdown | Col 35: Ads | Col 40: Churn
    Qualifier: only Zoho Voice, Treble, Videoconferencia count as effective contacts

    New metrics:
      pct_no_contactados_cuentas: % unique accounts (col 15) with ≥1 "NO" / total accounts
      recurrencia_no_contacto:    % accounts that were "NO" in 2+ different weeks
      weekly_no_contacto:         [{week, total_cuentas, no_cuentas, pct}] for sparkline
    """
    EFFECTIVE_PATTERN = r"zoho voice|treble|videoconferencia|meets|meet"

    def _palanca_stats(sub: pd.DataFrame, mask_col: int, contact_col: int) -> tuple[int, int]:
        p = sub[sub[mask_col].astype(str).str.upper() == "SI"]
        return len(p), int((p[contact_col].astype(str).str.upper() != "NO").sum())

    try:
        df = xl.parse("Productividad", header=0)
        df.columns = range(len(df.columns))
        farmer_col  = 14
        contact_col = 4
        medio_col   = 2
        week_col    = 9
        store_col   = 15   # Code (store ID)
        md_col, ads_col, churn_col = 26, 35, 40

        df = df[df[farmer_col].apply(lambda v: isinstance(v, str) and "@rappi" in v.lower())].copy()
        df[farmer_col] = df[farmer_col].str.strip().str.lower()

        # Parse week as isoweek number for grouping
        df["_week"] = pd.to_datetime(df[week_col], errors="coerce").dt.isocalendar().week.astype("Int64")

        rows = {}
        for farmer, sub in df.groupby(farmer_col):
            total = len(sub)
            contactado_series = sub[contact_col].astype(str).str.upper()
            no_cont = int((contactado_series == "NO").sum())
            pct_no_cont = round(no_cont / total * 100, 1) if total > 0 else 0

            # ── Qualifier: Zoho Voice + Treble + Videoconferencia only ──────────
            effective_mask = sub[medio_col].astype(str).str.lower().str.contains(
                EFFECTIVE_PATTERN, na=False
            )
            effective_sub = sub[effective_mask]
            total_eff = len(effective_sub)
            if total_eff > 0:
                contacted_eff = int((effective_sub[contact_col].astype(str).str.upper() != "NO").sum())
                productividad_pct = round(contacted_eff / total_eff, 4)
            else:
                productividad_pct = None

            # ── Palanca stats ────────────────────────────────────────────────────
            churn_tot, churn_cont = _palanca_stats(sub, churn_col, contact_col)
            md_tot,    md_cont    = _palanca_stats(sub, md_col, contact_col)
            ads_tot,   ads_cont   = _palanca_stats(sub, ads_col, contact_col)

            # ── Recurrencia de no contacto (por cuenta única) ────────────────────
            # % accounts with ≥1 NO / total unique accounts
            all_accounts = sub[store_col].dropna().unique()
            n_accounts   = len(all_accounts)

            cuentas_con_no = int(
                sub[sub[contact_col].astype(str).str.upper() == "NO"][store_col]
                .dropna().nunique()
            )
            pct_cuentas_no = round(cuentas_con_no / n_accounts * 100, 1) if n_accounts > 0 else 0

            # % accounts that were NO in 2+ distinct weeks (recurrentes)
            recurrentes = 0
            sub_no = sub[sub[contact_col].astype(str).str.upper() == "NO"].copy()
            if not sub_no.empty and "_week" in sub_no.columns:
                weeks_per_account = sub_no.groupby(store_col)["_week"].nunique()
                recurrentes = int((weeks_per_account >= 2).sum())
            pct_recurrencia = round(recurrentes / n_accounts * 100, 1) if n_accounts > 0 else 0

            # Weekly breakdown for sparkline / detail table
            weekly_no = []
            if "_week" in sub.columns:
                for wk, wg in sub.groupby("_week"):
                    wk_accounts = wg[store_col].dropna().nunique()
                    wk_no       = wg[wg[contact_col].astype(str).str.upper() == "NO"][store_col].dropna().nunique()
                    wk_pct      = round(wk_no / wk_accounts * 100, 1) if wk_accounts > 0 else 0
                    weekly_no.append({
                        "week":           int(wk),
                        "total_cuentas":  int(wk_accounts),
                        "no_cuentas":     int(wk_no),
                        "pct":            wk_pct,
                    })
                weekly_no.sort(key=lambda x: x["week"])

            rows[farmer] = {
                "total_follows":              total,
                "no_contactados":             no_cont,
                "pct_no_contactados":         pct_no_cont,
                "productividad_pct":          productividad_pct,
                "churn_follows":              churn_tot,
                "churn_contactados":          churn_cont,
                "md_follows":                 md_tot,
                "md_contactados":             md_cont,
                "ads_follows":                ads_tot,
                "ads_contactados":            ads_cont,
                # New — recurrencia
                "total_cuentas":              n_accounts,
                "cuentas_no_contactadas":     cuentas_con_no,
                "pct_cuentas_no_contactadas": pct_cuentas_no,
                "cuentas_recurrentes_no":     recurrentes,
                "pct_recurrencia_no":         pct_recurrencia,
                "weekly_no_contacto":         weekly_no,
            }
        return rows
    except Exception as e:
        logger.error("[loader] Productividad error: %s", e, exc_info=True)
        return {}


def load_penetracion(xl):
    """
    Structure: MONTH row 0, headers row 1, data from row 2.
    Col 0: COUNTRY | Col 1: LEADER | Col 2: BRAND_OWNER_EMAIL (farmer)
    Col 3: Brand ID - Name | Col 4: Revenue | Col 5: GMV
    Col 6-10: # stores by penetration bucket (0%, 0-30%, 30-50%, 50-70%, 70%+)
    Col 11: Penetración (Media) | Col 12: Revenue Perdido

    Brands at risk = those with Penetración (Media) < 0.70 (haven't reached target).
    Sorted by Revenue Perdido descending to show highest-impact first.
    """
    try:
        df = xl.parse("Penetración", header=None)
        df = df.iloc[2:].copy()
        df.columns = range(len(df.columns))

        # Keep only brand-level rows: farmer email in col 2, brand name (not Total/NaN) in col 3
        mask = (
            df[2].apply(lambda v: isinstance(v, str) and "@rappi" in v.lower()) &
            df[3].notna() &
            (~df[3].astype(str).str.strip().isin(["nan", "Total", ""]))
        )
        df = df[mask].copy()
        df[2] = df[2].str.strip().str.lower()

        df["pen_media"]  = pd.to_numeric(df[11], errors="coerce").fillna(0)
        df["rev_perdido"] = pd.to_numeric(df[12], errors="coerce").fillna(0)
        df["revenue"]    = pd.to_numeric(df[4],  errors="coerce").fillna(0)
        df["brand_name"] = df[3].astype(str).apply(
            lambda b: b.split(" - ", 1)[1].strip() if " - " in b else b.strip()
        )

        brands_at_risk = {}
        for farmer, sub in df.groupby(2):
            # Brands not yet at 70% penetration, with any revenue (active brands)
            at_risk_sub = sub[
                (sub["pen_media"] < 0.70) & (sub["revenue"] > 0)
            ].sort_values("rev_perdido", ascending=False)

            if not at_risk_sub.empty:
                # Top 10 by revenue perdido (most impactful)
                brands_at_risk[farmer] = at_risk_sub["brand_name"].head(10).tolist()
        return brands_at_risk
    except Exception as e:
        logger.error("[loader] Penetración error: %s", e)
        return {}


def load_att_productividad(xl):
    """
    Reads the 'ATT productividad' sheet.
    Expects farmer emails (col 14 like Productividad, or col 2 like other sheets)
    and an ATT value somewhere nearby.
    Returns {farmer_email: {"ATT_Prod_Sheet": float, "raw_row": dict}}
    """
    try:
        df = xl.parse("ATT productividad", header=0)
        df.columns = range(len(df.columns))

        # Try to find farmer email column (14 like Productividad, then 2)
        farmer_col = None
        for col_candidate in [14, 2, 1, 0]:
            if col_candidate < len(df.columns):
                mask = df[col_candidate].apply(
                    lambda v: isinstance(v, str) and "@rappi" in v.lower()
                )
                if mask.sum() >= 1:
                    farmer_col = col_candidate
                    break

        if farmer_col is None:
            logger.warning("[loader] ATT productividad: no se encontró columna de email farmer")
            return {}

        df = df[df[farmer_col].apply(
            lambda v: isinstance(v, str) and "@rappi" in v.lower()
        )].copy()
        df[farmer_col] = df[farmer_col].str.strip().str.lower()

        # Convert all numeric columns upfront to avoid per-cell to_numeric calls
        n_cols = len(df.columns)
        numeric_df = df.copy()
        for c in range(n_cols):
            if c != farmer_col:
                numeric_df[c] = pd.to_numeric(df[c], errors="coerce")

        result = {}
        for tup in numeric_df.itertuples(index=False, name=None):
            farmer = tup[farmer_col]
            att_val = next(
                (tup[c] for c in range(n_cols)
                 if c != farmer_col and not pd.isna(tup[c]) and 0 <= tup[c] <= 2.5),
                None,
            )
            result[farmer] = {
                "ATT_Prod_Sheet": att_val,
                "row_data": {str(c): tup[c] for c in range(n_cols)},
            }
        return result
    except Exception as e:
        logger.error("[loader] ATT productividad error: %s", e)
        return {}


def refresh_net_rev_adj(farmers_data: dict, dias_mes: int = 31) -> None:
    """
    Recalculate Net_Rev_Adj for every farmer using TODAY's date as the pace denominator.
    Call this after loading farmers_data so the metric is always current (not frozen at
    upload date).

    Safe: each farmer wrapped in try/except; uses math.isnan (no pd.NA ambiguity).
    """
    today_dia    = date.today().day
    progreso_hoy = ((today_dia - 1) / max(dias_mes, 1)) * 100
    for fdata in farmers_data.values():
        try:
            att = fdata.get("ATT_Rev_real")
            if att is None:
                fdata["Net_Rev_Adj"] = None
            else:
                att_f = float(att)
                fdata["Net_Rev_Adj"] = None if math.isnan(att_f) else round(att_f * 100 - progreso_hoy, 2)
        except Exception:
            fdata["Net_Rev_Adj"] = None


def load_cartera(xl):
    """
    Parse the Cartera sheet and return it as a JSON string.
    Expected columns (header row 0):
      COUNTRY | COUNTRY_BRAND_ID | BRAND_NAME | LEAD_PERF | BRAND_CITY
      BRAND_OWNER_EMAIL_ANTERIOR | BRAND_OWNER_ROLE_ANTERIOR
      BRAND_OWNER_EMAIL_NUEVO (current farmer) | BRAND_OWNER_ROLE_NUEVO
      CAMBIO_CARTERA | CAMBIO_SEGMENTO | LIDER | GMV_L28D | ORDERS_L28D
    """
    try:
        df = xl.parse("Cartera", header=0)
        df = df.dropna(how="all")
        # Normalize column names (strip whitespace)
        df.columns = [str(c).strip() for c in df.columns]
        # Normalize current-farmer email column
        farmer_col = next(
            (c for c in df.columns if "email_nuevo" in c.lower()), None
        )
        if farmer_col:
            df[farmer_col] = df[farmer_col].astype(str).str.strip().str.lower()
        logger.info("[loader] Cartera: %d filas, columnas: %s", len(df), list(df.columns))
        return df.to_json()
    except Exception as e:
        logger.error("[loader] Cartera error: %s", e, exc_info=True)
        return None


def load_sheet_maestro(file_obj, dia_corte: int, dias_mes: int = 30) -> dict:
    xl = pd.ExcelFile(file_obj, engine="openpyxl")
    sheets = xl.sheet_names

    churn   = load_churn(xl)        if "Churn" in sheets        else {}
    md      = load_md(xl)           if "MD" in sheets           else {}
    ads     = load_ads(xl)          if "Ads" in sheets          else {}
    pi      = load_pi(xl)           if "PI" in sheets           else {}
    prod    = load_productividad(xl) if "Productividad" in sheets else {}
    pen_raw = "Penetración" if "Penetración" in sheets else ("Penetracion" if "Penetracion" in sheets else None)
    penetracion = load_penetracion(xl) if pen_raw else {}

    # New: ATT Productividad sheet (optional)
    att_prod_sheet_name = next(
        (s for s in sheets if s.lower().strip() == "att productividad"), None
    )
    att_prod_data = load_att_productividad(xl) if att_prod_sheet_name else {}

    progreso_pct = ((dia_corte - 1) / dias_mes) * 100

    # Collect all known farmers from data + default list
    all_farmers = set(FARMERS_EMAILS)
    for src in [churn, md, ads, pi, prod, att_prod_data]:
        all_farmers |= set(src.keys())
    all_farmers = {
        f for f in all_farmers
        if "@rappi" in f
        and "oscar.pedraza" not in f
        and f not in EXCLUDED_EMAILS
        and f in set(FARMERS_EMAILS)   # solo farmers del equipo activo
    }

    farmers_data = {}
    for farmer in all_farmers:
        name = FARMER_NAMES.get(farmer, farmer.split("@")[0].replace(".", " ").title())

        row = {
            "email": farmer,
            "name": name,
            "slack_id": SLACK_IDS.get(farmer),
            "progreso_pct": progreso_pct,
            "dia_corte": dia_corte,
        }

        # Churn
        c = churn.get(farmer, {})
        row["ATT_Churn"]      = c.get("ATT_Churn")
        row["Reactivaciones"] = c.get("Reactivaciones")
        row["Gross_Churn"]    = c.get("Gross_Churn")
        row["Net_Churn"]      = c.get("Net_Churn")
        row["Ava_Stores"]     = c.get("Ava_Stores")

        # MD
        m = md.get(farmer, {})
        row["ATT_MD_Total"] = m.get("ATT_MD_Total")
        row["ATT_MD_Pro"]   = m.get("ATT_MD_Pro")

        # Ads
        a = ads.get(farmer, {})
        row["ATT_Book"]     = a.get("ATT_Book")
        row["ATT_Rev_real"] = a.get("ATT_Rev_real")

        # Net Revenue ajustado
        # Use pd.isna() to catch both None and np.nan (returned by pd.to_numeric)
        _ads_rev = row["ATT_Rev_real"]
        if _ads_rev is not None and not pd.isna(_ads_rev):
            row["Net_Rev_Adj"] = float(_ads_rev) * 100 - progreso_pct
        else:
            row["ATT_Rev_real"] = None   # normalise NaN → None for downstream code
            row["Net_Rev_Adj"]  = None

        # PI
        p = pi.get(farmer, {})
        row["Pitch_Pct"]  = p.get("Pitch_Pct")
        row["_pi_rows"]   = p.get("_pi_rows", [])   # weekly values for trend chart

        # Productividad
        pr = prod.get(farmer, {})
        row["total_follows"]              = pr.get("total_follows")
        row["no_contactados"]             = pr.get("no_contactados")
        row["pct_no_contactados"]         = pr.get("pct_no_contactados")
        row["productividad_pct"]          = pr.get("productividad_pct")
        row["churn_follows"]              = pr.get("churn_follows")
        row["churn_contactados"]          = pr.get("churn_contactados")
        row["md_follows"]                 = pr.get("md_follows")
        row["md_contactados"]             = pr.get("md_contactados")
        row["ads_follows"]                = pr.get("ads_follows")
        row["ads_contactados"]            = pr.get("ads_contactados")
        # Recurrencia de no contacto (nuevas métricas)
        row["total_cuentas"]              = pr.get("total_cuentas")
        row["cuentas_no_contactadas"]     = pr.get("cuentas_no_contactadas")
        row["pct_cuentas_no_contactadas"] = pr.get("pct_cuentas_no_contactadas")
        row["cuentas_recurrentes_no"]     = pr.get("cuentas_recurrentes_no")
        row["pct_recurrencia_no"]         = pr.get("pct_recurrencia_no")
        row["weekly_no_contacto"]         = pr.get("weekly_no_contacto", [])

        # Penetración
        row["brands_riesgo"] = penetracion.get(farmer, [])

        # ATT Productividad sheet (new tab)
        ap = att_prod_data.get(farmer, {})
        row["ATT_Prod_Sheet"] = ap.get("ATT_Prod_Sheet")
        row["_att_prod_row"]  = ap.get("row_data", {})

        farmers_data[farmer] = row

    return farmers_data
