import streamlit as st
import streamlit.components.v1 as components
import io
import html as _html
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path
from datetime import date
import calendar

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.loader import refresh_net_rev_adj, FARMER_NAMES, FARMERS_EMAILS
from core.auth import require_auth, render_topbar
from core.style import inject_global_css

st.set_page_config(
    page_title="Cartera — Rappi Farmers",
    page_icon="🗂️",
    layout="wide",
)
st.markdown(inject_global_css(), unsafe_allow_html=True)
email, is_supervisor = require_auth()
render_topbar()


# ── Auto-load ─────────────────────────────────────────────────────────────────
if "farmers_data" not in st.session_state:
    from core.db import load_latest_state
    latest = load_latest_state()
    if latest:
        st.session_state["farmers_data"] = latest["farmers_data"]
        st.session_state["dia_corte"]    = latest["dia_corte"]
        st.session_state["dias_mes"]     = latest["dias_mes"]
        if latest.get("cartera_raw"):
            st.session_state["_cartera_raw"] = latest["cartera_raw"]
        if latest.get("productividad_raw"):
            try:
                df_raw = pd.read_json(io.StringIO(latest["productividad_raw"]))
                df_raw.columns = [int(c) for c in df_raw.columns]
                st.session_state["_productividad_raw"] = df_raw
            except Exception:
                pass
    else:
        st.warning("⏳ El supervisor aún no ha cargado datos. Vuelve más tarde o contacta a Oscar Pedraza.")
        st.stop()

farmers_data = st.session_state["farmers_data"]
dia_corte    = st.session_state.get("dia_corte", 13)
dias_mes     = st.session_state.get("dias_mes", 31)
try:
    refresh_net_rev_adj(farmers_data, dias_mes)
except Exception:
    pass


# ── Bucket config ──────────────────────────────────────────────────────────────
# Order matters: shown in this order in charts/filters
BUCKET_CONFIG = {
    "Reciente":               {"color": "#00B341", "bg": "#D1FAE5", "emoji": "🟢"},
    "No reciente":            {"color": "#F59E0B", "bg": "#FEF3C7", "emoji": "🟡"},
    "Sin contacto reciente":  {"color": "#EF4444", "bg": "#FEE2E2", "emoji": "🔴"},
    "Imposible contacto":     {"color": "#7C3AED", "bg": "#EDE9FE", "emoji": "🚫"},
    "Sin contacto en el mes": {"color": "#6B7280", "bg": "#F3F4F6", "emoji": "⚫"},
}
BUCKET_ORDER = list(BUCKET_CONFIG.keys())


def _to_dates_robust(series):
    """
    Convert a series to DatetimeSeries, handling three formats:
      1. datetime64 — from a fresh Excel upload (no conversion needed)
      2. int64 epoch-ms — from JSON round-trip via pd.read_json().
         pd.to_datetime(int64) interprets as nanoseconds → 1970 dates → wrong!
         Fix: detect median year < 2000 and retry with unit='ms'.
      3. float Excel serial — unformatted Excel date cells (e.g. 46048.0 = 2026-01-15)
    """
    try:
        result = pd.to_datetime(series, errors="coerce")

        if pd.api.types.is_numeric_dtype(series):
            valid = result.dropna()
            # If the parsed dates are suspiciously old (≈ 1970), they were misread
            if len(valid) > 0 and valid.dt.year.median() < 2000:
                # Attempt 2: epoch-ms (most common after JSON round-trip)
                r2 = pd.to_datetime(series, unit="ms", errors="coerce")
                v2 = r2.dropna()
                if len(v2) > 0 and v2.dt.year.median() >= 2000:
                    return r2

                # Attempt 3: Excel serial date (day count since 1899-12-30)
                from datetime import datetime as _dt, timedelta as _td
                def _from_excel(v):
                    try:
                        f = float(v)
                        if 20000 <= f <= 60000:   # ~1954-2064 range
                            return pd.Timestamp(_dt(1899, 12, 30) + _td(days=int(f)))
                    except Exception:
                        pass
                    return pd.NaT
                r3 = series.apply(_from_excel)
                v3 = r3.dropna()
                if len(v3) > 0 and v3.dt.year.median() >= 2000:
                    return r3

        return result
    except Exception:
        return pd.Series(pd.NaT, index=series.index)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="rb-page-header">
    <h1>🗂️ Cartera</h1>
    <p>Recencia de contacto por marca · Referencia: día de corte del mes</p>
</div>
""", unsafe_allow_html=True)

# ── Check cartera data ────────────────────────────────────────────────────────
cartera_json = st.session_state.get("_cartera_raw")
if not cartera_json:
    st.error("""
    **Sin datos de Cartera.**

    Para habilitar esta vista:
    1. Ve a la página principal (sidebar)
    2. Carga el Sheet Maestro que incluya la pestaña **Cartera**
    3. Los datos quedarán disponibles para todo el equipo automáticamente
    """)
    st.stop()

# ── Parse cartera ─────────────────────────────────────────────────────────────
try:
    df_cart = pd.read_json(io.StringIO(cartera_json))
    df_cart.columns = [str(c).strip() for c in df_cart.columns]
except Exception as e:
    st.error(f"❌ Error al leer datos de cartera: {e}")
    st.stop()

_cols_lower = {c.lower(): c for c in df_cart.columns}
FARMER_COL  = _cols_lower.get("brand_owner_email_nuevo")
ID_COL      = _cols_lower.get("country_brand_id")
NAME_COL    = _cols_lower.get("brand_name")
COUNTRY_COL = _cols_lower.get("country")
GMV_COL     = _cols_lower.get("gmv_l28d")
ORDERS_COL  = _cols_lower.get("orders_l28d")
LIDER_COL   = _cols_lower.get("lider")
CAMBIO_COL  = _cols_lower.get("cambio_cartera")

if not FARMER_COL or not ID_COL:
    st.error(
        "❌ No se encontraron columnas necesarias en la hoja Cartera. "
        "Se esperan: **COUNTRY_BRAND_ID** y **BRAND_OWNER_EMAIL_NUEVO**. "
        f"Columnas encontradas: {', '.join(df_cart.columns.tolist())}"
    )
    st.stop()

df_cart[FARMER_COL] = df_cart[FARMER_COL].astype(str).str.strip().str.lower()
df_cart = df_cart[df_cart[FARMER_COL].isin(set(FARMERS_EMAILS))].copy()

if df_cart.empty:
    st.warning("No se encontraron marcas asignadas a farmers del equipo activo.")
    st.stop()

# ── Reference date = dia_corte of current month ───────────────────────────────
today = date.today()
try:
    max_day  = calendar.monthrange(today.year, today.month)[1]
    ref_date = date(today.year, today.month, min(dia_corte, max_day))
except Exception:
    ref_date = today

ref_ts = pd.Timestamp(ref_date)

# ── Process Productividad for contact recency + imposible contacto ─────────────
# Productividad column mapping (int columns, header=0 stripped):
#   col 4  = ¿Contactado?   (SI / NO)
#   col 9  = Week / Date (also a date column — used as fallback)
#   col 10 = Date
#   col 14 = Farmer email
#   col 15 = Code (COUNTRY_BRAND_ID)

last_contact_fb    = {}   # (farmer, code)  → latest contact Timestamp in last 30d
last_contact_brand = {}   # code            → latest contact Timestamp in last 30d
brand_all_no       = set()  # codes where EVERY follow in last 30d was NO (imposible)

# Load _productividad_raw — might not be in session_state if page was loaded
# directly (navigated from a different session context without upload).
df_prod = st.session_state.get("_productividad_raw")
if df_prod is None:
    try:
        from core.db import load_latest_state as _lls
        _ls = _lls()
        if _ls and _ls.get("productividad_raw"):
            _df = pd.read_json(io.StringIO(_ls["productividad_raw"]))
            _df.columns = [int(c) for c in _df.columns]
            df_prod = _df
            st.session_state["_productividad_raw"] = df_prod
    except Exception:
        pass

_prod_debug = {}   # filled for supervisor debug expander

if df_prod is not None and all(c in df_prod.columns for c in [4, 14, 15]):
    try:
        # Try col 10 (Date) first; fall back to col 9 (also a date field)
        _date_col = 10 if 10 in df_prod.columns else (9 if 9 in df_prod.columns else None)

        if _date_col is not None:
            df_d = df_prod[[4, 14, 15, _date_col]].copy()
            df_d.columns = ["contactado", "farmer", "code", "date"]
            df_d["date"] = _to_dates_robust(df_d["date"])

            # If col 10 gave bad dates (still 1970), try col 9 as fallback
            _valid = df_d["date"].dropna()
            if (len(_valid) == 0 or _valid.dt.year.median() < 2000) and _date_col == 10 and 9 in df_prod.columns:
                df_d["date"] = _to_dates_robust(df_prod[9])

            _prod_debug["date_col_used"] = _date_col
            _prod_debug["raw_rows"]      = len(df_d)
            _prod_debug["valid_dates"]   = int(df_d["date"].notna().sum())
            _prod_debug["date_range"]    = (
                f"{df_d['date'].min().date()} → {df_d['date'].max().date()}"
                if df_d["date"].notna().any() else "ninguna"
            )
            _prod_debug["ref_date"]      = str(ref_date)
            _prod_debug["cutoff"]        = str((ref_ts - pd.Timedelta(days=30)).date())

            df_d["contactado"] = df_d["contactado"].astype(str).str.strip().str.upper()
            df_d = df_d.dropna(subset=["date", "code"])

            cutoff = ref_ts - pd.Timedelta(days=30)
            df_d_30 = df_d[df_d["date"] >= cutoff].copy()

            _prod_debug["rows_in_30d"]  = len(df_d_30)
            _prod_debug["unique_codes"] = df_d_30["code"].nunique()

            # Last contact per (farmer, brand)
            for (farmer, code), grp in df_d_30.groupby(["farmer", "code"]):
                last_contact_fb[(str(farmer).lower(), str(code))] = grp["date"].max()

            # Last contact per brand (any farmer)
            for code, grp in df_d_30.groupby("code"):
                last_contact_brand[str(code)] = grp["date"].max()

            # Imposible contacto: has follows in period but ALL are NO
            for code, grp in df_d_30.groupby("code"):
                has_si = (grp["contactado"] != "NO").any()
                has_no = (grp["contactado"] == "NO").any()
                if has_no and not has_si:
                    brand_all_no.add(str(code))

            _prod_debug["last_contact_pairs"] = len(last_contact_fb)
            _prod_debug["imposible_codes"]    = len(brand_all_no)

    except Exception as _e:
        _prod_debug["error"] = str(_e)

# ── Supervisor debug expander ─────────────────────────────────────────────────
if is_supervisor:
    with st.expander("🔧 Debug — Productividad × Cartera (solo supervisor)", expanded=False):
        st.json(_prod_debug)
        st.write(f"**`_productividad_raw` en session_state:** {df_prod is not None}")
        if df_prod is not None:
            st.write(f"**Filas en Productividad:** {len(df_prod)} · "
                     f"**Columnas disponibles (muestra):** {[c for c in df_prod.columns if c <= 20]}")
        st.write(f"**Pares (farmer, brand) con contacto en 30d:** {len(last_contact_fb)}")
        st.write(f"**Marcas con imposible contacto:** {len(brand_all_no)}")


def assign_bucket(farmer_email, brand_id):
    """
    Returns (bucket_name, days_since_int_or_None).

    Priority:
      1. No follow in last 30d               → Sin contacto en el mes
      2. Has follows, ALL are NO             → Imposible contacto
      3. Has follows with ≥1 SI, recency:
           days < 8                          → Reciente
           8 ≤ days < 20                     → No reciente
           20 ≤ days < 30                    → Sin contacto reciente
           days ≥ 30                         → Sin contacto en el mes
    """
    key  = (str(farmer_email).lower(), str(brand_id))
    last = last_contact_fb.get(key)
    if last is None:
        last = last_contact_brand.get(str(brand_id))

    # 1. No record in last 30 days
    if last is None or pd.isna(last):
        return "Sin contacto en el mes", None

    # 2. Has records but all NO
    if str(brand_id) in brand_all_no:
        days = int(max((ref_ts - last).days, 0))
        return "Imposible contacto", days

    # 3. Normal recency
    days = int(max((ref_ts - last).days, 0))
    if days < 8:   return "Reciente", days
    elif days < 20: return "No reciente", days
    elif days < 30: return "Sin contacto reciente", days
    else:           return "Sin contacto en el mes", days


df_cart[["bucket", "days_since"]] = df_cart.apply(
    lambda r: pd.Series(assign_bucket(r[FARMER_COL], r[ID_COL])), axis=1
)

# ── Farmer selector ────────────────────────────────────────────────────────────
farmer_emails_in_data = sorted(df_cart[FARMER_COL].unique())

if is_supervisor:
    farmer_display_opts = ["⭐ Todo el equipo"] + [
        FARMER_NAMES.get(e, e.split("@")[0].title()) for e in farmer_emails_in_data
    ]
    sel = st.selectbox(
        "👤 Ver cartera de", farmer_display_opts,
        key="cartera_farmer_sel", label_visibility="collapsed",
    )
    if sel == "⭐ Todo el equipo":
        df_view    = df_cart.copy()
        view_email = None
    else:
        view_email = next(
            (e for e in farmer_emails_in_data
             if FARMER_NAMES.get(e, e.split("@")[0].title()) == sel),
            None,
        )
        df_view = df_cart[df_cart[FARMER_COL] == view_email].copy() if view_email else df_cart.copy()
else:
    df_view    = df_cart[df_cart[FARMER_COL] == email.lower()].copy()
    view_email = email.lower()
    if df_view.empty:
        st.info("📭 No hay marcas asignadas a tu cartera en este período.")
        st.stop()

# ── KPI Cards ─────────────────────────────────────────────────────────────────
n_total    = len(df_view)
counts     = df_view["bucket"].value_counts()
n_rec      = int(counts.get("Reciente", 0))
n_no_rec   = int(counts.get("No reciente", 0))
n_sin_rec  = int(counts.get("Sin contacto reciente", 0))
n_impos    = int(counts.get("Imposible contacto", 0))
n_nunca    = int(counts.get("Sin contacto en el mes", 0))
pct_riesgo = round((n_sin_rec + n_impos + n_nunca) / max(n_total, 1) * 100, 1)

c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
with c1: st.metric("📦 Total", f"{n_total:,}")
with c2: st.metric("🟢 Reciente", n_rec,       help="Contactadas hace < 8 días")
with c3: st.metric("🟡 No reciente", n_no_rec,  help="Último contacto hace 8–20 días")
with c4: st.metric("🔴 Sin reciente", n_sin_rec, help="Último contacto hace 20–30 días")
with c5: st.metric("🚫 Imposible", n_impos,
                   help="Tiene follows en el período pero TODOS dieron ¿Contactado?=NO")
with c6: st.metric("⚫ Sin contacto", n_nunca,  help="Sin ningún follow en los últimos 30 días")
with c7: st.metric("⚠️ % en riesgo", f"{pct_riesgo}%",
                   delta=f"{n_sin_rec + n_impos + n_nunca} marcas",
                   delta_color="inverse")

st.markdown("---")

# ── Charts row ────────────────────────────────────────────────────────────────
chart_col, breakdown_col = st.columns([1, 2])

with chart_col:
    st.markdown("### Distribución")
    values_pie   = [n_rec, n_no_rec, n_sin_rec, n_impos, n_nunca]
    colors_pie   = [BUCKET_CONFIG[b]["color"] for b in BUCKET_ORDER]
    labels_short = ["Reciente", "No reciente", "Sin reciente", "Imposible", "Sin contacto"]

    fig_pie = go.Figure(go.Pie(
        labels=labels_short,
        values=values_pie,
        hole=0.60,
        marker_colors=colors_pie,
        textinfo="percent+value",
        textfont_size=11,
        hovertemplate="%{label}: %{value} marcas (%{percent})<extra></extra>",
        sort=False,
    ))
    fig_pie.add_annotation(
        text=f"<b>{n_total}</b><br>marcas",
        x=0.5, y=0.5, font_size=14, showarrow=False, font_color="#374151",
    )
    fig_pie.update_layout(
        height=270,
        margin=dict(l=0, r=0, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(fig_pie, use_container_width=True)

with breakdown_col:
    if is_supervisor and view_email is None and len(farmer_emails_in_data) > 1:
        st.markdown("### Riesgo por farmer")
        fb_rows = []
        for fe in farmer_emails_in_data:
            sub = df_cart[df_cart[FARMER_COL] == fe]
            nt  = len(sub)
            nr  = int((sub["bucket"] == "Sin contacto reciente").sum())
            ni  = int((sub["bucket"] == "Imposible contacto").sum())
            nn  = int((sub["bucket"] == "Sin contacto en el mes").sum())
            fb_rows.append({
                "name":         FARMER_NAMES.get(fe, fe.split("@")[0].title()),
                "reciente":     int((sub["bucket"] == "Reciente").sum()),
                "no_reciente":  int((sub["bucket"] == "No reciente").sum()),
                "sin_reciente": nr,
                "imposible":    ni,
                "nunca":        nn,
                "pct_riesgo":   round((nr + ni + nn) / max(nt, 1) * 100, 1),
            })
        df_fb = pd.DataFrame(fb_rows).sort_values("pct_riesgo", ascending=False)

        bucket_bar_map = [
            ("reciente",    "Reciente",               "#00B341"),
            ("no_reciente", "No reciente",             "#F59E0B"),
            ("sin_reciente","Sin contacto reciente",   "#EF4444"),
            ("imposible",   "Imposible contacto",      "#7C3AED"),
            ("nunca",       "Sin contacto en el mes",  "#9CA3AF"),
        ]
        fig_fb = go.Figure()
        for col_key, label, color in bucket_bar_map:
            fig_fb.add_trace(go.Bar(
                y=df_fb["name"], x=df_fb[col_key],
                name=label, orientation="h",
                marker_color=color,
                hovertemplate=f"{label}: %{{x}}<extra>%{{y}}</extra>",
            ))
        fig_fb.update_layout(
            barmode="stack",
            height=max(220, len(df_fb) * 32),
            margin=dict(l=0, r=10, t=10, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=-0.28, font_size=10),
            xaxis=dict(title="Marcas"),
        )
        st.plotly_chart(fig_fb, use_container_width=True)

    else:
        # Single-farmer gauge bar
        if n_total > 0:
            st.markdown("### Cobertura de cartera")
            gauge_data = [
                ("Reciente",               n_rec,     "#00B341"),
                ("No reciente",            n_no_rec,  "#F59E0B"),
                ("Sin contacto reciente",  n_sin_rec, "#EF4444"),
                ("Imposible contacto",     n_impos,   "#7C3AED"),
                ("Sin contacto en el mes", n_nunca,   "#9CA3AF"),
            ]
            fig_g = go.Figure()
            for lbl, val, clr in gauge_data:
                fig_g.add_trace(go.Bar(
                    x=[val], y=["Cartera"],
                    orientation="h", name=lbl,
                    marker_color=clr,
                    text=f"{val}" if val > 0 else "",
                    textposition="inside", insidetextanchor="middle",
                    hovertemplate=f"{lbl}: %{{x}} marcas<extra></extra>",
                ))
            fig_g.update_layout(
                barmode="stack", height=110,
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                showlegend=True, legend=dict(orientation="h", y=-1.0, font_size=10),
                xaxis=dict(showticklabels=False, showgrid=False),
                yaxis=dict(showticklabels=False),
            )
            st.plotly_chart(fig_g, use_container_width=True)

st.markdown("---")

# ── Filters & sort ────────────────────────────────────────────────────────────
fcol1, fcol2 = st.columns([3, 1])
with fcol1:
    bucket_filter = st.multiselect(
        "Estado", options=BUCKET_ORDER, default=BUCKET_ORDER,
        key="cartera_bucket_filter", label_visibility="collapsed",
    )
with fcol2:
    sort_sel = st.selectbox(
        "Ordenar por",
        ["Días sin contacto ↓", "GMV ↓", "Nombre ↑"],
        key="cartera_sort", label_visibility="collapsed",
    )

df_filtered = df_view[df_view["bucket"].isin(bucket_filter)].copy()

if sort_sel == "Días sin contacto ↓":
    df_filtered = df_filtered.sort_values("days_since", ascending=False, na_position="last")
elif sort_sel == "GMV ↓" and GMV_COL:
    df_filtered[GMV_COL] = pd.to_numeric(df_filtered[GMV_COL], errors="coerce")
    df_filtered = df_filtered.sort_values(GMV_COL, ascending=False, na_position="last")
elif NAME_COL:
    df_filtered = df_filtered.sort_values(NAME_COL, ascending=True, na_position="last")

df_filtered = df_filtered.reset_index(drop=True)

st.markdown(
    f"**{len(df_filtered):,} marcas** en los filtros seleccionados"
    + (" · mostrando las primeras **500**" if len(df_filtered) > 500 else "")
)

# ── Download CSV ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _to_csv(df):
    return df.to_csv(index=False).encode("utf-8")

dl_cols = [c for c in [NAME_COL, COUNTRY_COL, FARMER_COL, "bucket", "days_since",
                        GMV_COL, ORDERS_COL, LIDER_COL] if c]
st.download_button(
    "⬇️ Descargar CSV",
    data=_to_csv(df_filtered[dl_cols].rename(columns={
        "bucket":    "Estado",
        "days_since":"Días sin contacto",
        FARMER_COL:  "Farmer",
    })),
    file_name=f"cartera_{ref_date.isoformat()}.csv",
    mime="text/csv",
)

st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)

# ── Table ─────────────────────────────────────────────────────────────────────
# Note: st.components.v1.html() is used instead of st.markdown() to avoid
# the Markdown parser mangling large HTML or choking on special chars (&, <, >)
# in brand names.  All user-supplied text is passed through html.escape().

rows_html = ""
for i, (_, row) in enumerate(df_filtered.head(500).iterrows()):
    bg     = "#FFFFFF" if i % 2 == 0 else "#FAFBFC"
    bucket = row["bucket"]
    cfg    = BUCKET_CONFIG.get(bucket, {"color": "#9CA3AF", "bg": "#F3F4F6", "emoji": "⚪"})
    clr    = cfg["color"]
    bg_bdg = cfg["bg"]

    days     = row.get("days_since")
    days_str = (f"{int(days)}d"
                if days is not None and not (isinstance(days, float) and pd.isna(days))
                else "—")

    # Escape all user-supplied text to prevent HTML injection / broken table
    brand   = _html.escape(str(row.get(NAME_COL,    "—")).strip()) if NAME_COL else "—"
    country = _html.escape(str(row.get(COUNTRY_COL, "—")).strip()) if COUNTRY_COL else "—"

    try:
        gmv_raw = row.get(GMV_COL) if GMV_COL else None
        gmv_str = f"${float(gmv_raw):,.0f}" if gmv_raw is not None and not pd.isna(gmv_raw) else "—"
    except Exception:
        gmv_str = "—"

    try:
        ord_raw = row.get(ORDERS_COL) if ORDERS_COL else None
        ord_str = f"{int(float(ord_raw)):,}" if ord_raw is not None and not pd.isna(ord_raw) else "—"
    except Exception:
        ord_str = "—"

    cambio = str(row.get(CAMBIO_COL, "")).strip() if CAMBIO_COL else ""
    cambio_badge = ""
    if cambio and cambio.lower() not in ("nan", "no", ""):
        cambio_badge = (
            f'<span style="background:#EFF6FF;color:#3B82F6;border-radius:14px;'
            f'padding:2px 8px;font-size:0.7rem;font-weight:600;margin-left:4px">'
            f'🔄 {_html.escape(cambio)}</span>'
        )

    badge = (
        f'<span style="background:{bg_bdg};color:{clr};border-radius:20px;'
        f'padding:3px 10px;font-size:0.72rem;font-weight:700;white-space:nowrap">'
        f'{cfg["emoji"]} {bucket}</span>'
    )

    farmer_em   = row.get(FARMER_COL, "")
    farmer_name = _html.escape(
        FARMER_NAMES.get(str(farmer_em), str(farmer_em).split("@")[0].title())
    ) if is_supervisor and view_email is None else ""
    farmer_td = (
        f'<td style="padding:10px 12px;color:#6B7280;font-size:0.78rem">{farmer_name}</td>'
        if is_supervisor and view_email is None else ""
    )

    rows_html += (
        f'<tr style="background:{bg};border-bottom:1px solid #F3F4F6">'
        f'<td style="padding:10px 14px;font-weight:600;color:#1A1A1A;font-size:0.85rem">{brand}{cambio_badge}</td>'
        f'<td style="padding:10px;color:#6B7280;font-size:0.82rem;text-align:center">{country}</td>'
        f'{farmer_td}'
        f'<td style="padding:10px;text-align:center">{badge}</td>'
        f'<td style="padding:10px;text-align:center;font-weight:700;color:{clr};font-size:0.92rem">{days_str}</td>'
        f'<td style="padding:10px;text-align:right;color:#374151;font-size:0.82rem">{gmv_str}</td>'
        f'<td style="padding:10px;text-align:right;color:#374151;font-size:0.82rem">{ord_str}</td>'
        f'</tr>'
    )

farmer_th_html = (
    '<th style="padding:10px 12px;text-align:left">Farmer</th>'
    if is_supervisor and view_email is None else ""
)

# Render via components.html to bypass Markdown parser completely
_table_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:transparent}}
.wrap{{border-radius:12px;border:1px solid #E5E7EB;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.06);overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:0.84rem;background:#FFF}}
thead tr{{background:#F9FAFB;border-bottom:2px solid #E5E7EB}}
th{{padding:10px;color:#6B7280;font-size:0.68rem;text-transform:uppercase;letter-spacing:.8px;font-weight:600;white-space:nowrap}}
th:first-child{{padding-left:14px;text-align:left}}
</style></head>
<body>
<div class="wrap">
<table>
<thead><tr>
<th style="text-align:left;padding-left:14px">Marca</th>
<th>País</th>
{farmer_th_html}
<th>Estado</th>
<th>Días</th>
<th style="text-align:right">GMV L28D</th>
<th style="text-align:right">Orders L28D</th>
</tr></thead>
<tbody>{rows_html}</tbody>
</table>
</div>
</body></html>"""

_n_rows  = min(len(df_filtered), 500)
_row_px  = 46   # approximate row height in pixels
_head_px = 54   # header height
_pad_px  = 4
_height  = _head_px + _n_rows * _row_px + _pad_px
components.html(_table_html, height=_height, scrolling=False)

# ── Imposible contacto callout ─────────────────────────────────────────────────
df_impos = df_view[df_view["bucket"] == "Imposible contacto"].copy()
if GMV_COL:
    df_impos[GMV_COL] = pd.to_numeric(df_impos[GMV_COL], errors="coerce")
    df_impos = df_impos.sort_values(GMV_COL, ascending=False, na_position="last")

if not df_impos.empty:
    st.markdown("---")
    st.markdown("## 🚫 Imposible contacto — mayor GMV primero")
    st.caption(
        "Estas marcas tienen follows registrados en el período pero **todos** obtuvieron "
        "¿Contactado? = NO. El farmer está intentando pero no logra contactar."
    )
    top_i = df_impos.head(20)
    for _, row in top_i.iterrows():
        brand   = str(row.get(NAME_COL, "—")).strip() if NAME_COL else "—"
        days_r  = row.get("days_since")
        days_s  = f"{int(days_r)}d" if days_r is not None and not (isinstance(days_r, float) and pd.isna(days_r)) else "—"
        gmv_raw = row.get(GMV_COL) if GMV_COL else None
        try:
            gmv_s = f"${float(gmv_raw):,.0f}" if gmv_raw is not None and not pd.isna(gmv_raw) else "—"
        except Exception:
            gmv_s = "—"
        farmer_raw  = row.get(FARMER_COL, "")
        farmer_part = ""
        if is_supervisor and view_email is None:
            fn = FARMER_NAMES.get(str(farmer_raw), str(farmer_raw).split("@")[0].title())
            farmer_part = f" · <span style='color:#6B7280'>{fn}</span>"
        st.markdown(
            f"- **{brand}** · GMV: <span style='color:#7C3AED;font-weight:700'>{gmv_s}</span>"
            f" · Último intento: {days_s}{farmer_part}",
            unsafe_allow_html=True,
        )
    if len(df_impos) > 20:
        st.caption(f"... y {len(df_impos) - 20} más. Descarga el CSV para la lista completa.")
    st.warning(
        "💡 **Acción sugerida:** revisar si el número de contacto es correcto, "
        "si la marca sigue activa, o si se puede intentar por otro canal (WhatsApp, email, visita presencial). "
        "Escalar al líder si persiste después de 3 intentos fallidos."
    )

# ── Sin contacto en el mes callout ────────────────────────────────────────────
df_nunca = df_view[df_view["bucket"] == "Sin contacto en el mes"].copy()
if GMV_COL:
    df_nunca[GMV_COL] = pd.to_numeric(df_nunca[GMV_COL], errors="coerce")
    df_nunca = df_nunca.sort_values(GMV_COL, ascending=False, na_position="last")

if not df_nunca.empty:
    st.markdown("---")
    st.markdown("## ⚠️ Sin contacto en el mes — mayor GMV primero")
    st.caption("Estas marcas no tienen ningún follow registrado en los últimos 30 días.")
    top_risk = df_nunca.head(20)
    for _, row in top_risk.iterrows():
        brand   = str(row.get(NAME_COL, "—")).strip() if NAME_COL else "—"
        gmv_raw = row.get(GMV_COL) if GMV_COL else None
        try:
            gmv_s = f"${float(gmv_raw):,.0f}" if gmv_raw is not None and not pd.isna(gmv_raw) else "—"
        except Exception:
            gmv_s = "—"
        farmer_raw  = row.get(FARMER_COL, "")
        farmer_part = ""
        if is_supervisor and view_email is None:
            fn = FARMER_NAMES.get(str(farmer_raw), str(farmer_raw).split("@")[0].title())
            farmer_part = f" · <span style='color:#6B7280'>{fn}</span>"
        st.markdown(
            f"- **{brand}** · GMV: <span style='color:#EF4444;font-weight:700'>{gmv_s}</span>{farmer_part}",
            unsafe_allow_html=True,
        )
    if len(df_nunca) > 20:
        st.caption(f"... y {len(df_nunca) - 20} más. Descarga el CSV para la lista completa.")
    st.info(
        "💡 **Acción sugerida:** contactar esta semana y registrar el follow en Productividad. "
        "Priorizar por mayor GMV para proteger revenue."
    )
