"""
pages/11_Cartera.py
Optimizaciones aplicadas:
  1. Conversión de fechas Excel serial VECTORIZADA — sin .apply(), corre en C puro.
  2. @st.cache_data en procesar_recencia_cartera() — groupby pesado se ejecuta UNA sola vez.
  3. st.data_editor reemplaza el iframe de components.html() — nativo, sin concatenación
     de strings, sin cálculo manual de altura.
  4. Filtros maestros movidos al sidebar — canvas principal limpio para KPIs y charts.
"""

import io
import streamlit as st
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

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cartera — Rappi Farmers",
    page_icon="🗂️",
    layout="wide",
)
st.markdown(inject_global_css(), unsafe_allow_html=True)
email, is_supervisor = require_auth()
render_topbar()


# ── Auto-load from DB if session is fresh ─────────────────────────────────────
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
                _df = pd.read_json(io.StringIO(latest["productividad_raw"]))
                _df.columns = [int(c) for c in _df.columns]
                st.session_state["_productividad_raw"] = _df
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


# ── Bucket constants ──────────────────────────────────────────────────────────
BUCKET_CONFIG = {
    "Reciente":               {"color": "#00B341", "bg": "#D1FAE5", "emoji": "🟢"},
    "No reciente":            {"color": "#F59E0B", "bg": "#FEF3C7", "emoji": "🟡"},
    "Sin contacto reciente":  {"color": "#EF4444", "bg": "#FEE2E2", "emoji": "🔴"},
    "Imposible contacto":     {"color": "#7C3AED", "bg": "#EDE9FE", "emoji": "🚫"},
    "Sin contacto en el mes": {"color": "#6B7280", "bg": "#F3F4F6", "emoji": "⚫"},
}
BUCKET_ORDER = list(BUCKET_CONFIG.keys())


# ══════════════════════════════════════════════════════════════════════════════
# 1. CONVERSIÓN DE FECHAS VECTORIZADA
#    Tres estrategias en cascada, todas sin .apply():
#      A) datetime64 nativo  — uploads directos desde Excel
#      B) epoch-ms int64     — round-trip pd.to_json / pd.read_json
#      C) Excel serial float — celdas sin formato en Excel (ej. 46048 = 2026-01-15)
#         VECTORIZADO con pd.to_datetime(unit='D', origin='1899-12-30') sobre máscara bool
# ══════════════════════════════════════════════════════════════════════════════
def _to_dates_robust(series: pd.Series) -> pd.Series:
    """
    Convierte una Series a DatetimeSeries manejando los 3 formatos de entrada
    posibles. El path de Excel serial usa operaciones vectorizadas nativas de
    pandas (C speed), sin ningún .apply() en Python puro.
    """
    try:
        result = pd.to_datetime(series, errors="coerce")

        if pd.api.types.is_numeric_dtype(series):
            valid = result.dropna()
            # Si las fechas parseadas son sospechosamente antiguas (≈1970), fueron malinterpretadas
            if len(valid) > 0 and valid.dt.year.median() < 2000:

                # Estrategia B: epoch-ms (caso más frecuente tras JSON round-trip)
                r2 = pd.to_datetime(series, unit="ms", errors="coerce")
                v2 = r2.dropna()
                if len(v2) > 0 and v2.dt.year.median() >= 2000:
                    return r2

                # Estrategia C: Excel serial date — VECTORIZADA (sin .apply)
                # pd.to_datetime(n, unit='D', origin='1899-12-30') = 1899-12-30 + n días
                numeric = pd.to_numeric(series, errors="coerce")
                mask    = (numeric >= 20_000) & (numeric <= 60_000)  # rango ~1954–2064
                r3      = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
                if mask.any():
                    r3[mask] = pd.to_datetime(
                        numeric[mask].astype(int),
                        unit="D",
                        origin="1899-12-30",
                        errors="coerce",
                    )
                v3 = r3.dropna()
                if len(v3) > 0 and v3.dt.year.median() >= 2000:
                    return r3

        return result
    except Exception:
        return pd.Series(pd.NaT, index=series.index)


# ══════════════════════════════════════════════════════════════════════════════
# 2. PROCESADOR DE RECENCIA CON @st.cache_data
#    Función pura: recibe df_prod (DataFrame) + ref_ts (Timestamp).
#    Streamlit hashea el contenido del DataFrame para determinar si el caché
#    sigue vigente. El groupby/aggregation pesado corre UNA sola vez; los
#    cambios de filtros en el sidebar NO relanzan esta función.
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(show_spinner=False)
def procesar_recencia_cartera(df_prod: pd.DataFrame, ref_ts: pd.Timestamp):
    """
    Procesa Productividad y retorna las estructuras de recencia listas para consumo.

    Retorna
    -------
    last_contact_fb    : dict[(farmer_email, brand_id) → pd.Timestamp]
    last_contact_brand : dict[brand_id → pd.Timestamp]
    brand_all_no       : set[brand_id] donde TODOS los follows del período fueron NO
    debug              : dict con información diagnóstica para el supervisor
    """
    last_contact_fb    = {}
    last_contact_brand = {}
    brand_all_no       = set()
    debug              = {}

    required = {4, 14, 15}
    if not required.issubset(set(df_prod.columns)):
        debug["error"] = f"Columnas faltantes en Productividad. Disponibles: {list(df_prod.columns[:20])}"
        return last_contact_fb, last_contact_brand, brand_all_no, debug

    # Columna de fecha: preferir col 10 (Date), caer a col 9 (Week/Date)
    date_col = 10 if 10 in df_prod.columns else (9 if 9 in df_prod.columns else None)
    if date_col is None:
        debug["error"] = "No se encontró columna de fecha (col 9 o 10) en Productividad."
        return last_contact_fb, last_contact_brand, brand_all_no, debug

    df_d = df_prod[[4, 14, 15, date_col]].copy()
    df_d.columns = ["contactado", "farmer", "code", "date"]
    df_d["date"] = _to_dates_robust(df_d["date"])

    # Si col 10 dio fechas malas (aún ~1970), probar col 9 como fallback
    _valid = df_d["date"].dropna()
    if (len(_valid) == 0 or _valid.dt.year.median() < 2000) and date_col == 10 and 9 in df_prod.columns:
        df_d["date"] = _to_dates_robust(df_prod[9])

    debug["date_col_used"] = date_col
    debug["raw_rows"]      = len(df_d)
    debug["valid_dates"]   = int(df_d["date"].notna().sum())
    debug["date_range"]    = (
        f"{df_d['date'].min().date()} → {df_d['date'].max().date()}"
        if df_d["date"].notna().any() else "ninguna"
    )
    debug["ref_date"] = str(ref_ts.date())
    debug["cutoff"]   = str((ref_ts - pd.Timedelta(days=30)).date())

    df_d["contactado"] = df_d["contactado"].astype(str).str.strip().str.upper()
    df_d["farmer"]     = df_d["farmer"].astype(str).str.strip().str.lower()
    df_d["code"]       = df_d["code"].astype(str)
    df_d = df_d.dropna(subset=["date", "code"])

    cutoff  = ref_ts - pd.Timedelta(days=30)
    df_30   = df_d[df_d["date"] >= cutoff].copy()

    debug["rows_in_30d"]  = len(df_30)
    debug["unique_codes"] = int(df_30["code"].nunique())

    # ── Último contacto por (farmer, brand) — vectorizado ────────────────────
    fb_max = (
        df_30.groupby(["farmer", "code"])["date"]
        .max()
        .reset_index()
    )
    last_contact_fb = {
        (row["farmer"], row["code"]): row["date"]
        for _, row in fb_max.iterrows()
    }

    # ── Último contacto por brand (cualquier farmer) — vectorizado ────────────
    last_contact_brand = df_30.groupby("code")["date"].max().to_dict()

    # ── Imposible contacto — vectorizado ─────────────────────────────────────
    # Marcas donde TODOS los follows en el período fueron ¿Contactado?=NO.
    # Estrategia: contar filas totales vs. filas con contactado != "NO" por código.
    # Los códigos sin ninguna fila en code_si (contactado≠NO) son imposibles.
    code_total = df_30.groupby("code")["contactado"].count()
    code_si    = (
        df_30[df_30["contactado"] != "NO"]
        .groupby("code")["contactado"]
        .count()
    )
    brand_all_no = set(code_total.index[~code_total.index.isin(code_si.index)].tolist())

    debug["last_contact_pairs"] = len(last_contact_fb)
    debug["imposible_codes"]    = len(brand_all_no)

    return last_contact_fb, last_contact_brand, brand_all_no, debug


# ── Fecha de referencia ───────────────────────────────────────────────────────
today = date.today()
try:
    max_day  = calendar.monthrange(today.year, today.month)[1]
    ref_date = date(today.year, today.month, min(dia_corte, max_day))
except Exception:
    ref_date = today
ref_ts = pd.Timestamp(ref_date)


# ── Validar y parsear Cartera ─────────────────────────────────────────────────
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

# Coerción numérica una sola vez, antes de cualquier filtro
if GMV_COL:
    df_cart[GMV_COL] = pd.to_numeric(df_cart[GMV_COL], errors="coerce")
if ORDERS_COL:
    df_cart[ORDERS_COL] = pd.to_numeric(df_cart[ORDERS_COL], errors="coerce")


# ── Cargar Productividad + ejecutar procesador cacheado ───────────────────────
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

if df_prod is not None:
    last_contact_fb, last_contact_brand, brand_all_no, _prod_debug = procesar_recencia_cartera(
        df_prod, ref_ts
    )
else:
    last_contact_fb    = {}
    last_contact_brand = {}
    brand_all_no       = set()
    _prod_debug        = {"warning": "Productividad no disponible — recencia no calculada"}


# ── Asignación de buckets ─────────────────────────────────────────────────────
def assign_bucket(farmer_email, brand_id):
    """
    Retorna (bucket_name, days_int_or_None).

    Prioridad:
      1. Sin follow en 30d                        → Sin contacto en el mes
      2. Tiene follows pero TODOS son NO           → Imposible contacto
      3. Tiene follows con ≥1 SI, por recencia:
           días < 8                               → Reciente
           8 ≤ días < 20                          → No reciente
           20 ≤ días < 30                         → Sin contacto reciente
           días ≥ 30                              → Sin contacto en el mes
    """
    key  = (str(farmer_email).lower(), str(brand_id))
    last = last_contact_fb.get(key) or last_contact_brand.get(str(brand_id))

    if last is None or pd.isna(last):
        return "Sin contacto en el mes", None

    if str(brand_id) in brand_all_no:
        return "Imposible contacto", int(max((ref_ts - last).days, 0))

    days = int(max((ref_ts - last).days, 0))
    if days < 8:    return "Reciente", days
    elif days < 20: return "No reciente", days
    elif days < 30: return "Sin contacto reciente", days
    else:           return "Sin contacto en el mes", days


df_cart[["bucket", "days_since"]] = df_cart.apply(
    lambda r: pd.Series(assign_bucket(r[FARMER_COL], r[ID_COL])), axis=1
)


# ══════════════════════════════════════════════════════════════════════════════
# 4. SIDEBAR — FILTROS MAESTROS
#    Canvas principal queda exclusivamente para KPIs, charts y tabla de datos.
# ══════════════════════════════════════════════════════════════════════════════
farmer_emails_in_data = sorted(df_cart[FARMER_COL].unique())

with st.sidebar:
    st.markdown("---")
    st.markdown("### 🗂️ Filtros de Cartera")

    # Selector de farmer (solo supervisor)
    if is_supervisor:
        farmer_opts = ["⭐ Todo el equipo"] + [
            FARMER_NAMES.get(e, e.split("@")[0].title()) for e in farmer_emails_in_data
        ]
        sel = st.selectbox("👤 Farmer", farmer_opts, key="cartera_farmer_sel")
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

    # Filtro de estado (bucket)
    bucket_filter = st.multiselect(
        "📊 Estado",
        options=BUCKET_ORDER,
        default=BUCKET_ORDER,
        key="cartera_bucket_filter",
    )

    # Ordenamiento
    sort_sel = st.selectbox(
        "🔃 Ordenar por",
        ["Días sin contacto ↓", "GMV ↓", "Nombre ↑"],
        key="cartera_sort",
    )

    st.markdown("---")
    st.caption(f"📅 Referencia: día {dia_corte} del mes ({ref_date.isoformat()})")


# Guard: farmer sin marcas asignadas
if not is_supervisor and df_view.empty:
    st.info("📭 No hay marcas asignadas a tu cartera en este período.")
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# CANVAS PRINCIPAL — Header + KPIs + Charts + Tabla + Callouts
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="rb-page-header">
    <h1>🗂️ Cartera</h1>
    <p>Recencia de contacto por marca · Referencia: día de corte del mes</p>
</div>
""", unsafe_allow_html=True)

# Expander de debug (solo supervisor)
if is_supervisor:
    with st.expander("🔧 Debug — Productividad × Cartera (solo supervisor)", expanded=False):
        st.json(_prod_debug)
        st.write(f"**`_productividad_raw` cargado:** {df_prod is not None}")
        if df_prod is not None:
            st.write(
                f"**Filas Productividad:** {len(df_prod)} · "
                f"**Columnas (≤20):** {[c for c in df_prod.columns if c <= 20]}"
            )

# ── KPI Metrics ───────────────────────────────────────────────────────────────
n_total    = len(df_view)
counts     = df_view["bucket"].value_counts()
n_rec      = int(counts.get("Reciente", 0))
n_no_rec   = int(counts.get("No reciente", 0))
n_sin_rec  = int(counts.get("Sin contacto reciente", 0))
n_impos    = int(counts.get("Imposible contacto", 0))
n_nunca    = int(counts.get("Sin contacto en el mes", 0))
pct_riesgo = round((n_sin_rec + n_impos + n_nunca) / max(n_total, 1) * 100, 1)

c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
with c1: st.metric("📦 Total",        f"{n_total:,}")
with c2: st.metric("🟢 Reciente",     n_rec,        help="Contactadas hace < 8 días")
with c3: st.metric("🟡 No reciente",  n_no_rec,     help="Último contacto hace 8–20 días")
with c4: st.metric("🔴 Sin reciente", n_sin_rec,    help="Último contacto hace 20–30 días")
with c5: st.metric("🚫 Imposible",    n_impos,
                   help="Tiene follows en el período pero TODOS dieron ¿Contactado?=NO")
with c6: st.metric("⚫ Sin contacto", n_nunca,      help="Sin ningún follow en los últimos 30 días")
with c7: st.metric("⚠️ % en riesgo",  f"{pct_riesgo}%",
                   delta=f"{n_sin_rec + n_impos + n_nunca} marcas", delta_color="inverse")

st.markdown("---")

# ── Charts ────────────────────────────────────────────────────────────────────
chart_col, breakdown_col = st.columns([1, 2])

with chart_col:
    st.markdown("### Distribución")
    fig_pie = go.Figure(go.Pie(
        labels=["Reciente", "No reciente", "Sin reciente", "Imposible", "Sin contacto"],
        values=[n_rec, n_no_rec, n_sin_rec, n_impos, n_nunca],
        hole=0.60,
        marker_colors=[BUCKET_CONFIG[b]["color"] for b in BUCKET_ORDER],
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
        height=270, margin=dict(l=0, r=0, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
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
                "sin_reciente": nr, "imposible": ni, "nunca": nn,
                "pct_riesgo":   round((nr + ni + nn) / max(nt, 1) * 100, 1),
            })
        df_fb = pd.DataFrame(fb_rows).sort_values("pct_riesgo", ascending=False)

        fig_fb = go.Figure()
        for col_key, label, color in [
            ("reciente",    "Reciente",               "#00B341"),
            ("no_reciente", "No reciente",             "#F59E0B"),
            ("sin_reciente","Sin contacto reciente",   "#EF4444"),
            ("imposible",   "Imposible contacto",      "#7C3AED"),
            ("nunca",       "Sin contacto en el mes",  "#9CA3AF"),
        ]:
            fig_fb.add_trace(go.Bar(
                y=df_fb["name"], x=df_fb[col_key],
                name=label, orientation="h", marker_color=color,
                hovertemplate=f"{label}: %{{x}}<extra>%{{y}}</extra>",
            ))
        fig_fb.update_layout(
            barmode="stack",
            height=max(220, len(df_fb) * 32),
            margin=dict(l=0, r=10, t=10, b=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=-0.28, font_size=10),
            xaxis=dict(title="Marcas"),
        )
        st.plotly_chart(fig_fb, use_container_width=True)
    else:
        if n_total > 0:
            st.markdown("### Cobertura de cartera")
            fig_g = go.Figure()
            for lbl, val, clr in [
                ("Reciente",               n_rec,     "#00B341"),
                ("No reciente",            n_no_rec,  "#F59E0B"),
                ("Sin contacto reciente",  n_sin_rec, "#EF4444"),
                ("Imposible contacto",     n_impos,   "#7C3AED"),
                ("Sin contacto en el mes", n_nunca,   "#9CA3AF"),
            ]:
                fig_g.add_trace(go.Bar(
                    x=[val], y=["Cartera"], orientation="h", name=lbl,
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


# ══════════════════════════════════════════════════════════════════════════════
# 3. TABLA DE MARCAS — st.data_editor
#    Reemplaza components.html() + concatenación de strings en bucle for.
#    Beneficios:
#      • Sin iframe de altura calculada manualmente
#      • Sin saturación de memoria del navegador con ~120KB de HTML concatenado
#      • Tipado nativo: Int64 nullable, float para GMV, str para categorías
#      • column_config: SelectboxColumn para Estado, NumberColumn con formato
#        monetario y de días, TextColumn para Marca con ancho grande
# ══════════════════════════════════════════════════════════════════════════════

# Aplicar filtros y ordenamiento (sidebar)
df_filtered = df_view[df_view["bucket"].isin(bucket_filter)].copy()

if sort_sel == "Días sin contacto ↓":
    df_filtered = df_filtered.sort_values("days_since", ascending=False, na_position="last")
elif sort_sel == "GMV ↓" and GMV_COL:
    df_filtered = df_filtered.sort_values(GMV_COL, ascending=False, na_position="last")
elif NAME_COL:
    df_filtered = df_filtered.sort_values(NAME_COL, ascending=True, na_position="last")

df_filtered = df_filtered.reset_index(drop=True)

# Fila de estado + botón CSV
info_col, dl_col = st.columns([4, 1])
with info_col:
    st.markdown(
        f"**{len(df_filtered):,} marcas** en los filtros seleccionados"
        + (" · mostrando las primeras **500**" if len(df_filtered) > 500 else "")
    )
with dl_col:
    @st.cache_data(show_spinner=False)
    def _to_csv(df):
        return df.to_csv(index=False).encode("utf-8")

    dl_cols = [c for c in [NAME_COL, COUNTRY_COL, FARMER_COL, "bucket", "days_since",
                            GMV_COL, ORDERS_COL, LIDER_COL] if c]
    st.download_button(
        "⬇️ CSV",
        data=_to_csv(df_filtered[dl_cols].rename(columns={
            "bucket":    "Estado",
            "days_since":"Días sin contacto",
            FARMER_COL:  "Farmer",
        })),
        file_name=f"cartera_{ref_date.isoformat()}.csv",
        mime="text/csv",
        use_container_width=True,
    )

# ── Construir DataFrame de visualización ─────────────────────────────────────
_rows    = df_filtered.head(500)
_emoji   = {b: cfg["emoji"] for b, cfg in BUCKET_CONFIG.items()}
_display = {}

if NAME_COL:
    _display["Marca"] = _rows[NAME_COL].fillna("—").astype(str)

if COUNTRY_COL:
    _display["País"] = _rows[COUNTRY_COL].fillna("—").astype(str)

# Columna Farmer solo para vista "Todo el equipo" del supervisor
if is_supervisor and view_email is None:
    _display["Farmer"] = _rows[FARMER_COL].map(
        lambda e: FARMER_NAMES.get(str(e), str(e).split("@")[0].title())
    )

# Estado con emoji para jerarquía visual (coincide con las opciones del SelectboxColumn)
_display["Estado"] = _rows["bucket"].map(lambda b: f"{_emoji.get(b, '⚪')} {b}")

# Días: Int64 nullable → NaN se muestra como celda vacía
_display["Días sin contacto"] = (
    pd.to_numeric(_rows["days_since"], errors="coerce").astype("Int64")
)

if GMV_COL:
    _display["GMV L28D"] = _rows[GMV_COL]

if ORDERS_COL:
    _display["Orders L28D"] = (
        pd.to_numeric(_rows[ORDERS_COL], errors="coerce").astype("Int64")
    )

if CAMBIO_COL:
    _display["Cambio cartera"] = _rows[CAMBIO_COL].fillna("").astype(str)

df_display = pd.DataFrame(_display)

# ── Configuración de columnas ─────────────────────────────────────────────────
col_cfg = {}

if "Marca" in df_display.columns:
    col_cfg["Marca"] = st.column_config.TextColumn("Marca", width="large")

if "País" in df_display.columns:
    col_cfg["País"] = st.column_config.TextColumn("País", width="small")

if "Farmer" in df_display.columns:
    col_cfg["Farmer"] = st.column_config.TextColumn("Farmer", width="medium")

# SelectboxColumn: muestra las opciones válidas del negocio con sus emojis
col_cfg["Estado"] = st.column_config.SelectboxColumn(
    "Estado",
    options=[f"{BUCKET_CONFIG[b]['emoji']} {b}" for b in BUCKET_ORDER],
    width="medium",
)

# NumberColumn con sufijo " días" — printf-style format
col_cfg["Días sin contacto"] = st.column_config.NumberColumn(
    "Días sin contacto",
    format="%d días",
    min_value=0,
    width="small",
)

if "GMV L28D" in df_display.columns:
    col_cfg["GMV L28D"] = st.column_config.NumberColumn(
        "GMV L28D",
        format="$%.0f",
        width="small",
    )

if "Orders L28D" in df_display.columns:
    col_cfg["Orders L28D"] = st.column_config.NumberColumn(
        "Orders L28D",
        format="%d",
        width="small",
    )

if "Cambio cartera" in df_display.columns:
    col_cfg["Cambio cartera"] = st.column_config.TextColumn("Cambio cartera", width="small")

# Renderizar tabla nativa — sin iframe, sin HTML manual, sin cálculo de altura
st.data_editor(
    df_display,
    column_config=col_cfg,
    disabled=True,             # solo lectura
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    key="cartera_table",
)


# ══════════════════════════════════════════════════════════════════════════════
# CALLOUT SECTIONS — Alertas por pérdida de GMV
# ══════════════════════════════════════════════════════════════════════════════

# ── Imposible contacto ────────────────────────────────────────────────────────
df_impos = df_view[df_view["bucket"] == "Imposible contacto"].copy()
if GMV_COL:
    df_impos = df_impos.sort_values(GMV_COL, ascending=False, na_position="last")

if not df_impos.empty:
    st.markdown("---")
    st.markdown("## 🚫 Imposible contacto — mayor GMV primero")
    st.caption(
        "Estas marcas tienen follows registrados en el período pero **todos** obtuvieron "
        "¿Contactado? = NO. El farmer está intentando pero no logra contactar."
    )
    for _, row in df_impos.head(20).iterrows():
        brand   = str(row.get(NAME_COL, "—")).strip() if NAME_COL else "—"
        days_r  = row.get("days_since")
        days_s  = f"{int(days_r)}d" if days_r is not None and not (isinstance(days_r, float) and pd.isna(days_r)) else "—"
        gmv_raw = row.get(GMV_COL) if GMV_COL else None
        try:
            gmv_s = f"${float(gmv_raw):,.0f}" if gmv_raw is not None and not pd.isna(gmv_raw) else "—"
        except Exception:
            gmv_s = "—"
        farmer_part = ""
        if is_supervisor and view_email is None:
            fn = FARMER_NAMES.get(
                str(row.get(FARMER_COL, "")),
                str(row.get(FARMER_COL, "")).split("@")[0].title()
            )
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
        "si la marca sigue activa, o si se puede intentar por otro canal "
        "(WhatsApp, email, visita presencial). "
        "Escalar al líder si persiste después de 3 intentos fallidos."
    )

# ── Sin contacto en el mes ────────────────────────────────────────────────────
df_nunca = df_view[df_view["bucket"] == "Sin contacto en el mes"].copy()
if GMV_COL:
    df_nunca = df_nunca.sort_values(GMV_COL, ascending=False, na_position="last")

if not df_nunca.empty:
    st.markdown("---")
    st.markdown("## ⚠️ Sin contacto en el mes — mayor GMV primero")
    st.caption("Estas marcas no tienen ningún follow registrado en los últimos 30 días.")
    for _, row in df_nunca.head(20).iterrows():
        brand   = str(row.get(NAME_COL, "—")).strip() if NAME_COL else "—"
        gmv_raw = row.get(GMV_COL) if GMV_COL else None
        try:
            gmv_s = f"${float(gmv_raw):,.0f}" if gmv_raw is not None and not pd.isna(gmv_raw) else "—"
        except Exception:
            gmv_s = "—"
        farmer_part = ""
        if is_supervisor and view_email is None:
            fn = FARMER_NAMES.get(
                str(row.get(FARMER_COL, "")),
                str(row.get(FARMER_COL, "")).split("@")[0].title()
            )
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
