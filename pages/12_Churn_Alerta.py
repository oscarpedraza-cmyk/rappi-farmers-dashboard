import streamlit as st
import io
import pandas as pd
from datetime import date
import calendar
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.loader import FARMER_NAMES, FARMERS_EMAILS, refresh_net_rev_adj
from core.auth import require_auth, render_topbar
from core.style import inject_global_css
from core.db import load_latest_state

st.set_page_config(
    page_title="Alerta Temprana de Churn — Rappi Farmers",
    page_icon="🚀",
    layout="wide",
)
st.markdown(inject_global_css(), unsafe_allow_html=True)
email, is_supervisor = require_auth()
render_topbar()

# ── Data bootstrap ────────────────────────────────────────────────────────────
if "farmers_data" not in st.session_state:
    latest = load_latest_state()
    if latest:
        st.session_state["farmers_data"] = latest["farmers_data"]
        st.session_state["dia_corte"]    = latest["dia_corte"]
        st.session_state["dias_mes"]     = latest["dias_mes"]
        if latest.get("productividad_raw"):
            try:
                _df = pd.read_json(io.StringIO(latest["productividad_raw"]))
                _df.columns = [int(c) for c in _df.columns]
                st.session_state["_productividad_raw"] = _df
            except Exception:
                pass
        if latest.get("cartera_raw"):
            st.session_state["_cartera_raw"] = latest["cartera_raw"]
    else:
        st.warning("⏳ El supervisor aún no ha cargado datos. Vuelve más tarde o contacta a Oscar Pedraza.")
        st.stop()

dia_corte = st.session_state.get("dia_corte", 13)
dias_mes  = st.session_state.get("dias_mes", 31)

today = date.today()
try:
    max_day  = calendar.monthrange(today.year, today.month)[1]
    ref_date = date(today.year, today.month, min(dia_corte, max_day))
except Exception:
    ref_date = today
ref_ts = pd.Timestamp(ref_date)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="rb-page-header">
    <h1>🚨 Alerta Temprana de Churn</h1>
    <p>Marcas con alto GMV sin contacto en 2+ semanas. Score = GMV_L28D × semanas_sin_contacto — prioriza dónde llamar hoy.</p>
</div>
""", unsafe_allow_html=True)

# ── Cartera check ─────────────────────────────────────────────────────────────
cartera_json = st.session_state.get("_cartera_raw")
df_prod      = st.session_state.get("_productividad_raw")

if not cartera_json:
    st.error("**Sin datos de Cartera.** Carga el Sheet Maestro con la pestaña **Cartera**.")
    st.stop()

try:
    df_cart = pd.read_json(io.StringIO(cartera_json))
    df_cart.columns = [str(c).strip() for c in df_cart.columns]
except Exception as e:
    st.error(f"❌ Error al leer Cartera: {e}")
    st.stop()

_cols_lower = {c.lower(): c for c in df_cart.columns}
FARMER_COL  = _cols_lower.get("brand_owner_email_nuevo")
ID_COL      = _cols_lower.get("country_brand_id")
NAME_COL    = _cols_lower.get("brand_name")
COUNTRY_COL = _cols_lower.get("country")
GMV_COL     = _cols_lower.get("gmv_l28d")
ORDERS_COL  = _cols_lower.get("orders_l28d")

if not FARMER_COL or not ID_COL:
    st.error(
        "❌ Columnas **BRAND_OWNER_EMAIL_NUEVO** o **COUNTRY_BRAND_ID** no encontradas en Cartera. "
        f"Columnas disponibles: {', '.join(df_cart.columns.tolist())}"
    )
    st.stop()

df_cart[FARMER_COL] = df_cart[FARMER_COL].astype(str).str.strip().str.lower()
df_cart = df_cart[df_cart[FARMER_COL].isin(set(FARMERS_EMAILS))].copy()

if GMV_COL:
    df_cart[GMV_COL] = pd.to_numeric(df_cart[GMV_COL], errors="coerce").fillna(0)
if ORDERS_COL:
    df_cart[ORDERS_COL] = pd.to_numeric(df_cart[ORDERS_COL], errors="coerce").fillna(0)
if ID_COL:
    df_cart[ID_COL] = df_cart[ID_COL].astype(str)

# ── Recencia desde Productividad ──────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def compute_last_contact(df_prod_json: str, ref_str: str) -> dict:
    """Returns dict[brand_id → last_contact_timestamp] for last 30 days."""
    ref = pd.Timestamp(ref_str)
    try:
        df = pd.read_json(io.StringIO(df_prod_json))
        df.columns = [int(c) if str(c).isdigit() else c for c in df.columns]
    except Exception:
        return {}

    required = {4, 14, 15}
    if not required.issubset(set(df.columns)):
        return {}

    date_col = 10 if 10 in df.columns else (9 if 9 in df.columns else None)
    if date_col is None:
        return {}

    dfd = df[[15, date_col]].copy()
    dfd.columns = ["code", "date"]
    dfd["date"] = pd.to_datetime(dfd["date"], errors="coerce")

    # Fallback for epoch-ms (post JSON round-trip)
    numeric = pd.to_numeric(df[date_col], errors="coerce")
    mask_bad = dfd["date"].notna() & (dfd["date"].dt.year < 2000)
    if mask_bad.any():
        dfd.loc[mask_bad, "date"] = pd.to_datetime(
            numeric[mask_bad], unit="ms", errors="coerce"
        )
    # Fallback for Excel serial
    mask_nat = dfd["date"].isna() & numeric.between(20_000, 60_000)
    if mask_nat.any():
        dfd.loc[mask_nat, "date"] = pd.to_datetime(
            numeric[mask_nat].astype(int), unit="D", origin="1899-12-30", errors="coerce"
        )

    dfd["code"] = dfd["code"].astype(str)
    dfd = dfd.dropna(subset=["date"])
    cutoff = ref - pd.Timedelta(days=30)
    df_30  = dfd[dfd["date"] >= cutoff]
    return df_30.groupby("code")["date"].max().to_dict()


# Convert productividad DataFrame → JSON for cache key
_prod_json_key = None
if df_prod is not None:
    try:
        _prod_json_key = df_prod.to_json()
    except Exception:
        pass

last_contact_brand: dict = {}
if _prod_json_key:
    last_contact_brand = compute_last_contact(_prod_json_key, str(ref_ts))
else:
    st.warning("⚠️ Sin datos de Productividad — la recencia se mostrará como 'desconocida'.")

# ── Calcular días sin contacto y score ───────────────────────────────────────
def _days_since(brand_id: str) -> float | None:
    ts = last_contact_brand.get(str(brand_id))
    if ts is None:
        return None
    delta = (ref_ts - pd.Timestamp(ts)).days
    return max(0, delta)

df_cart["days_since"] = df_cart[ID_COL].apply(_days_since)
df_cart["semanas_sc"] = df_cart["days_since"].apply(
    lambda d: round(d / 7, 1) if pd.notna(d) else None
)
gmv_vals = df_cart[GMV_COL] if GMV_COL else pd.Series(0.0, index=df_cart.index)
df_cart["score"] = (
    gmv_vals.where(df_cart["semanas_sc"].notna(), 0.0) * df_cart["semanas_sc"].fillna(0.0)
).astype(float)

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 Filtros")
    if is_supervisor:
        farmer_opts = ["Todos"] + [
            FARMER_NAMES.get(e, e.split("@")[0].title())
            for e in sorted(set(df_cart[FARMER_COL].unique()))
        ]
        sel_farmer = st.selectbox("Farmer", farmer_opts, key="churn_farmer")
    else:
        sel_farmer = FARMER_NAMES.get(email.strip().lower(), email)

    min_weeks = st.slider("Mín. semanas sin contacto", 1, 8, 2, key="churn_weeks")
    min_gmv   = st.number_input("Mín. GMV L28D ($)", min_value=0, value=0, step=500,
                                key="churn_min_gmv")

# ── Filtrar ───────────────────────────────────────────────────────────────────
mask_weeks = df_cart["semanas_sc"] >= min_weeks
mask_gmv   = (gmv_vals >= min_gmv) if min_gmv > 0 else pd.Series(True, index=df_cart.index)
df_risk = df_cart[mask_weeks & mask_gmv].copy()

if is_supervisor and sel_farmer != "Todos":
    email_sel = next((e for e, n in FARMER_NAMES.items() if n == sel_farmer), None)
    if email_sel:
        df_risk = df_risk[df_risk[FARMER_COL] == email_sel]
elif not is_supervisor:
    df_risk = df_risk[df_risk[FARMER_COL] == email.strip().lower()]

df_risk = df_risk.sort_values("score", ascending=False).reset_index(drop=True)

# ── KPIs ─────────────────────────────────────────────────────────────────────
total_riesgo  = len(df_risk)
gmv_riesgo    = float(gmv_vals[df_risk.index].sum()) if GMV_COL else 0.0
avg_weeks     = df_risk["semanas_sc"].mean() if not df_risk.empty else 0.0
max_score     = float(df_risk["score"].max()) if not df_risk.empty else 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("🚨 Marcas en alerta",    total_riesgo)
c2.metric("💰 GMV en riesgo L28D", f"${gmv_riesgo:,.0f}")
c3.metric("📅 Sem. prom. sin contacto", f"{avg_weeks:.1f}" if total_riesgo else "—")
c4.metric("🔥 Score máximo",        f"{max_score:,.0f}" if total_riesgo else "—")

st.markdown("---")

# ── Tabla principal ───────────────────────────────────────────────────────────
if df_risk.empty:
    st.success("✅ No hay marcas en alerta con los filtros seleccionados.")
else:
    st.markdown(f"### {total_riesgo} marcas en riesgo de churn")

    disp: dict = {}
    if NAME_COL:
        disp["Marca"]   = df_risk[NAME_COL].fillna("—").astype(str)
    if COUNTRY_COL:
        disp["País"]    = df_risk[COUNTRY_COL].fillna("—").astype(str)
    disp["Farmer"]      = df_risk[FARMER_COL].map(
        lambda e: FARMER_NAMES.get(e, e.split("@")[0].title())
    )
    if GMV_COL:
        disp["GMV L28D"]  = gmv_vals[df_risk.index].values
    if ORDERS_COL:
        disp["Orders L28D"] = df_risk[ORDERS_COL].values
    disp["Sem. sin contacto"] = df_risk["semanas_sc"].values
    disp["Score"]             = df_risk["score"].round(0).values

    df_disp = pd.DataFrame(disp)
    max_sc   = float(df_disp["Score"].max()) if not df_disp.empty else 1.0

    col_cfg = {
        "Marca":            st.column_config.TextColumn("Marca", width="large"),
        "País":             st.column_config.TextColumn("País", width="small"),
        "Farmer":           st.column_config.TextColumn("Farmer", width="medium"),
        "GMV L28D":         st.column_config.NumberColumn("💰 GMV L28D", format="$%,.0f"),
        "Orders L28D":      st.column_config.NumberColumn("Orders L28D", format="%d"),
        "Sem. sin contacto":st.column_config.NumberColumn("⏱ Sem. sin contacto", format="%.1f"),
        "Score":            st.column_config.ProgressColumn(
                                "🔥 Score riesgo", format="%.0f",
                                min_value=0, max_value=max_sc),
    }
    st.data_editor(df_disp, use_container_width=True, hide_index=True,
                   disabled=True, column_config=col_cfg)

    st.caption("Score = GMV L28D × semanas sin contacto — mayor score = mayor urgencia de llamar hoy")

    # ── Top alerta por farmer (callout) ───────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📞 Llamadas prioritarias por farmer")
    farmer_top = (
        df_risk.groupby(FARMER_COL, group_keys=False)
        .apply(lambda g: g.nlargest(1, "score"))
    )
    top_sorted = farmer_top.sort_values("score", ascending=False).copy()
    if GMV_COL:
        top_sorted["_gmv"] = gmv_vals
    for rec in top_sorted.to_dict("records"):
        fname  = FARMER_NAMES.get(rec[FARMER_COL], rec[FARMER_COL])
        brand  = str(rec[NAME_COL]) if NAME_COL else "—"
        gmv_v  = float(rec.get("_gmv") or 0) if GMV_COL else 0
        weeks  = rec["semanas_sc"]
        score  = rec["score"]
        color  = "#EF4444" if weeks >= 4 else "#F59E0B"
        st.markdown(
            f"<div style='background:#FEF2F2;border-left:4px solid {color};"
            f"border-radius:8px;padding:0.6rem 1rem;margin-bottom:0.4rem'>"
            f"<b>{fname}</b> — <b>{brand}</b>: "
            f"<span style='color:{color}'>⏱ {weeks:.1f} sem. sin contacto</span> · "
            f"💰 ${gmv_v:,.0f} GMV · Score: {score:,.0f}"
            f"</div>",
            unsafe_allow_html=True,
        )
