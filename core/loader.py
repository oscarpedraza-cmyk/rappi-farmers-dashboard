import pandas as pd
import numpy as np
from datetime import date


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
    "luis.ibarra@rappi.com",
    "angie.contreras@rappi.com",
    "diana.saavedra@rappi.com",
    "maria.pedraza@rappi.com",
    "sabas.ramirez@rappi.com",
]

# Farmers excluidos (renuncia, licencia, etc.) — no aparecen en el dashboard
EXCLUDED_EMAILS = {
    "vanesa.fernandez@rappi.com",   # renuncia voluntaria mayo 2026
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
    "luis.ibarra@rappi.com": "Luis Ibarra",
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
    "luis.ibarra@rappi.com": "U09NYKPPNG5",
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

        result = {}
        for _, row in df.iterrows():
            farmer = row[2]
            result[farmer] = {
                "ATT_Churn":    pd.to_numeric(row[13], errors="coerce"),
                "Reactivaciones": pd.to_numeric(row[8], errors="coerce"),
                "Gross_Churn":  pd.to_numeric(row[7], errors="coerce"),
                "Net_Churn":    pd.to_numeric(row[9], errors="coerce"),
                "Ava_Stores":   pd.to_numeric(row[3], errors="coerce"),
            }
        return result
    except Exception as e:
        print(f"[loader] Churn error: {e}")
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

        result = {}
        for _, row in df.iterrows():
            farmer = row[2]
            result[farmer] = {
                "ATT_MD_Total": pd.to_numeric(row[6], errors="coerce"),
                "ATT_MD_Pro":   pd.to_numeric(row[10], errors="coerce"),
            }
        return result
    except Exception as e:
        print(f"[loader] MD error: {e}")
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

        result = {}
        for _, row in df.iterrows():
            farmer = row[2]
            result[farmer] = {
                "ATT_Book":     pd.to_numeric(row[8], errors="coerce"),
                "ATT_Rev_real": pd.to_numeric(row[13], errors="coerce"),
            }
        return result
    except Exception as e:
        print(f"[loader] Ads error: {e}")
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
            print("[loader] PI: no se encontró columna de email farmer")
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
                    result = {}
                    for idx, row in df_total.iterrows():
                        farmer = row[farmer_col]
                        v = pd.to_numeric(row[pitch_col], errors="coerce")
                        result[farmer] = {"Pitch_Pct": v if pd.notna(v) else None,
                                          "_pi_rows": [v] if pd.notna(v) else []}
                    print(f"[loader] PI: Strategy A → {len(result)} farmers (tag_col={tag_col}, pitch_col={pitch_col})")
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
            print(f"[loader] PI: Strategy B no encontró columna válida (best_coverage={best_coverage:.2f})")
            return {}

        df_all["_val"] = pd.to_numeric(df_all[best_pitch_col], errors="coerce")
        result = {}
        for farmer, group in df_all.groupby(farmer_col):
            weekly_vals = group["_val"].dropna().tolist()
            avg = float(np.nanmean(weekly_vals)) if weekly_vals else None
            result[farmer] = {"Pitch_Pct": round(avg, 4) if avg is not None else None,
                              "_pi_rows": weekly_vals}
        print(f"[loader] PI: Strategy B → {len(result)} farmers (pitch_col={best_pitch_col}, coverage={best_coverage:.0%})")
        return result

    except Exception as e:
        import traceback
        print(f"[loader] PI error: {e}")
        traceback.print_exc()
        return {}


def load_productividad(xl):
    """
    Structure: header row 0, data from row 1.
    Col 2: Medio de Contacto | Col 4: ¿Contactado?
    Col 14: Farmer | Col 26: Markdown | Col 35: Ads | Col 40: Churn
    Qualifier: only Zoho Voice, Treble, Videoconferencia count as effective contacts
    """
    EFFECTIVE_PATTERN = r"zoho voice|treble|videoconferencia|meets|meet"

    try:
        df = xl.parse("Productividad", header=0)
        df.columns = range(len(df.columns))
        farmer_col, contact_col, md_col, ads_col, churn_col, medio_col = 14, 4, 26, 35, 40, 2

        df = df[df[farmer_col].apply(lambda v: isinstance(v, str) and "@rappi" in v.lower())].copy()
        df[farmer_col] = df[farmer_col].str.strip().str.lower()

        rows = {}
        for farmer, sub in df.groupby(farmer_col):
            total = len(sub)
            contactado_series = sub[contact_col].astype(str).str.upper()
            no_cont = int((contactado_series == "NO").sum())
            pct_no_cont = round(no_cont / total * 100, 1) if total > 0 else 0

            # Qualifier: Zoho Voice + Treble + Videoconferencia only
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

            def palanca_stats(mask_col):
                p = sub[sub[mask_col].astype(str).str.upper() == "SI"]
                total_p = len(p)
                cont_p = int((p[contact_col].astype(str).str.upper() != "NO").sum())
                return total_p, cont_p

            churn_tot, churn_cont = palanca_stats(churn_col)
            md_tot, md_cont = palanca_stats(md_col)
            ads_tot, ads_cont = palanca_stats(ads_col)

            rows[farmer] = {
                "total_follows": total,
                "no_contactados": no_cont,
                "pct_no_contactados": pct_no_cont,
                "productividad_pct": productividad_pct,
                "churn_follows": churn_tot, "churn_contactados": churn_cont,
                "md_follows": md_tot, "md_contactados": md_cont,
                "ads_follows": ads_tot, "ads_contactados": ads_cont,
            }
        return rows
    except Exception as e:
        import traceback
        print(f"[loader] Productividad error: {e}")
        traceback.print_exc()
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
        print(f"[loader] Penetración error: {e}")
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
            print("[loader] ATT productividad: no se encontró columna de email farmer")
            return {}

        df = df[df[farmer_col].apply(
            lambda v: isinstance(v, str) and "@rappi" in v.lower()
        )].copy()
        df[farmer_col] = df[farmer_col].str.strip().str.lower()

        # Store the entire row so the page can display whatever it finds
        result = {}
        for _, row in df.iterrows():
            farmer = row[farmer_col]
            # Try to find an ATT decimal column (values between 0 and 2)
            att_val = None
            for c in range(len(df.columns)):
                if c == farmer_col:
                    continue
                v = pd.to_numeric(row[c], errors="coerce")
                if pd.notna(v) and 0 <= v <= 2.5:
                    att_val = v
                    break
            result[farmer] = {
                "ATT_Prod_Sheet": att_val,
                "row_data": {str(c): row[c] for c in range(len(df.columns))},
            }
        return result
    except Exception as e:
        print(f"[loader] ATT productividad error: {e}")
        return {}


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
        if row["ATT_Rev_real"] is not None and not (isinstance(row["ATT_Rev_real"], float) and np.isnan(row["ATT_Rev_real"])):
            row["Net_Rev_Adj"] = row["ATT_Rev_real"] * 100 - progreso_pct
        else:
            row["Net_Rev_Adj"] = None

        # PI
        p = pi.get(farmer, {})
        row["Pitch_Pct"]  = p.get("Pitch_Pct")
        row["_pi_rows"]   = p.get("_pi_rows", [])   # weekly values for trend chart

        # Productividad
        pr = prod.get(farmer, {})
        row["total_follows"]        = pr.get("total_follows")
        row["no_contactados"]       = pr.get("no_contactados")
        row["pct_no_contactados"]   = pr.get("pct_no_contactados")
        row["productividad_pct"]    = pr.get("productividad_pct")
        row["churn_follows"]        = pr.get("churn_follows")
        row["churn_contactados"]    = pr.get("churn_contactados")
        row["md_follows"]           = pr.get("md_follows")
        row["md_contactados"]       = pr.get("md_contactados")
        row["ads_follows"]          = pr.get("ads_follows")
        row["ads_contactados"]      = pr.get("ads_contactados")

        # Penetración
        row["brands_riesgo"] = penetracion.get(farmer, [])

        # ATT Productividad sheet (new tab)
        ap = att_prod_data.get(farmer, {})
        row["ATT_Prod_Sheet"] = ap.get("ATT_Prod_Sheet")
        row["_att_prod_row"]  = ap.get("row_data", {})

        farmers_data[farmer] = row

    return farmers_data
