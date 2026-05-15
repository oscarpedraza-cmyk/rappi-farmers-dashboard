import streamlit as st
import pandas as pd
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.auth import require_auth, render_topbar
from core.style import inject_global_css

st.set_page_config(page_title="Follow Track — Rappi Farmers", page_icon="🚀", layout="wide")
st.markdown(inject_global_css(), unsafe_allow_html=True)
email_auth, is_supervisor = require_auth()
render_topbar()


# ── Auto-load si session_state está vacío ─────────────────────────────────────
if "farmers_data" not in st.session_state:
    from core.db import load_latest_state
    latest = load_latest_state()
    if latest:
        st.session_state["farmers_data"] = latest["farmers_data"]
        st.session_state["dia_corte"]    = latest["dia_corte"]
        st.session_state["dias_mes"]     = latest["dias_mes"]
        if latest.get("att_prod_raw"):
            st.session_state["_att_prod_raw"] = latest["att_prod_raw"]
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

# ── Try to load Follow Track raw table ───────────────────────────────────────
att_raw_json = st.session_state.get("_att_prod_raw")

if att_raw_json:
    try:
        df = pd.read_json(io.StringIO(att_raw_json))
    except Exception as _parse_err:
        df = None
        if is_supervisor:
            st.error(f"❌ Error parseando ATT prod JSON: {_parse_err}")
else:
    df = None

# ── DEBUG: only visible to supervisor ────────────────────────────────────────
if is_supervisor:
    with st.expander("🔧 Debug — estado de datos (solo supervisores)", expanded=False):
        st.write("**`_att_prod_raw` en session_state:**", att_raw_json is not None)
        st.write("**`_sheet_names` en session_state:**",
                 st.session_state.get("_sheet_names", "no disponible"))
        if df is not None:
            st.write(f"**DataFrame cargado:** {len(df)} filas × {len(df.columns)} cols")
            st.write("**Columnas:**", list(df.columns))
            st.dataframe(df.head(3))
        from core.db import load_latest_state as _lls
        _ls = _lls()
        if _ls:
            st.write("**Claves en latest_state:**", list(_ls.keys()))
            st.write("**att_prod_raw en latest_state:**", bool(_ls.get("att_prod_raw")))
            st.write("**Actualizado por:**", _ls.get("updated_by"), "—", _ls.get("updated_at", "")[:19])

# ── FOLLOW TRACK VIEW ─────────────────────────────────────────────────────────
if df is not None and not df.empty:

    n = len(df)
    medals = ["🥇", "🥈", "🥉"]

    def _find_col(dataframe, *hints):
        """Case-insensitive column finder."""
        for hint in hints:
            for col in dataframe.columns:
                if hint.lower() in str(col).lower():
                    return col
        return None

    col_farmer   = _find_col(df, "farmer", "email", "correo")
    col_pais     = _find_col(df, "país", "pais", "país", "country")
    col_lider    = _find_col(df, "líder", "lider", "leader")
    col_meta     = _find_col(df, "meta", "target", "goal")
    col_comp     = _find_col(df, "completado", "complete")
    col_desc_dia = _find_col(df, "desc. día", "desc día", "desc dia", "descdia")
    col_desc_fol = _find_col(df, "desc. follow", "desc follow", "descfollow")
    col_pend     = _find_col(df, "pendiente", "pending")
    col_pct      = _find_col(df, "cumpl", "% cumpl", "pct")
    col_estado   = _find_col(df, "estado", "status", "state")

    def fmt_num(row, col, color):
        if col is None:
            return '<span style="color:#D1D5DB">—</span>'
        v = row.get(col) if hasattr(row, "get") else row[col]
        if pd.isna(v):
            return '<span style="color:#D1D5DB">—</span>'
        try:
            return f'<span style="color:{color};font-weight:700">{int(float(v))}</span>'
        except Exception:
            return f'<span style="color:{color}">{v}</span>'

    def fmt_pct(row, col):
        if col is None:
            return '<span style="color:#D1D5DB">—</span>'
        v = row.get(col) if hasattr(row, "get") else row[col]
        if pd.isna(v):
            return '<span style="color:#D1D5DB">—</span>'
        try:
            vf = float(str(v).replace("%", "").strip())
            c = "#00B341" if vf >= 90 else "#F59E0B" if vf >= 70 else "#EF4444"
            return f'<span style="color:{c};font-weight:700">{vf:.1f}%</span>'
        except Exception:
            return f'<span style="font-weight:600">{v}</span>'

    def fmt_estado(row, col):
        if col is None:
            return ""
        v = row.get(col) if hasattr(row, "get") else row[col]
        if pd.isna(v):
            return ""
        s = str(v).strip()
        if not s or s.lower() == "nan":
            return ""
        s_low = s.lower()
        if "crít" in s_low or "critic" in s_low or "x" in s_low:
            return (f'<span style="background:#FEE2E2;color:#EF4444;border-radius:20px;'
                    f'padding:4px 14px;font-size:0.75rem;font-weight:700;white-space:nowrap">'
                    f'✗ Crítico</span>')
        if "ok" in s_low or "bien" in s_low or "cumple" in s_low:
            return (f'<span style="background:#D1FAE5;color:#00B341;border-radius:20px;'
                    f'padding:4px 14px;font-size:0.75rem;font-weight:700">✓ OK</span>')
        return (f'<span style="background:#FEE2E2;color:#EF4444;border-radius:20px;'
                f'padding:4px 14px;font-size:0.75rem;font-weight:700">{s}</span>')

    # Build rows
    rows_html = ""
    for i, (_, row) in enumerate(df.iterrows()):
        rank   = i + 1
        medal  = medals[i] if i < 3 else str(rank)
        bg     = "#FFFFFF" if i % 2 == 0 else "#FAFBFC"

        farmer_val = str(row[col_farmer]).strip() if col_farmer and pd.notna(row[col_farmer]) else "—"
        pais_val   = str(row[col_pais]).strip()   if col_pais   and pd.notna(row[col_pais])   else "—"
        lider_val  = str(row[col_lider]).strip()  if col_lider  and pd.notna(row[col_lider])  else "—"

        rows_html += f"""
        <tr style="background:{bg};border-bottom:1px solid #F3F4F6">
            <td style="padding:13px 16px;text-align:center;font-size:1.05rem">{medal}</td>
            <td style="padding:13px 16px;color:#4A6CF7;font-weight:600;font-size:0.84rem">{farmer_val}</td>
            <td style="padding:13px 16px;color:#374151;font-size:0.84rem">{pais_val}</td>
            <td style="padding:13px 16px;color:#374151;font-size:0.84rem">{lider_val}</td>
            <td style="padding:13px 16px;text-align:center">{fmt_num(row, col_meta,     '#4A90D9')}</td>
            <td style="padding:13px 16px;text-align:center">{fmt_num(row, col_comp,     '#00B341')}</td>
            <td style="padding:13px 16px;text-align:center">{fmt_num(row, col_desc_dia, '#F59E0B')}</td>
            <td style="padding:13px 16px;text-align:center">{fmt_num(row, col_desc_fol, '#F59E0B')}</td>
            <td style="padding:13px 16px;text-align:center">{fmt_num(row, col_pend,     '#F59E0B')}</td>
            <td style="padding:13px 16px;text-align:center">{fmt_pct(row, col_pct)}</td>
            <td style="padding:13px 16px;text-align:center">{fmt_estado(row, col_estado)}</td>
        </tr>"""

    st.markdown(f"""
    <div style="border-radius:14px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.10);margin-bottom:2rem">
        <div style="background:#1A1A2E;padding:1.3rem 1.8rem">
            <div style="font-size:1.6rem;font-weight:900;color:white;letter-spacing:-0.5px;margin:0">
                Follow <span style="color:#FF6B00">Track</span>
            </div>
            <div style="color:rgba(255,255,255,0.55);font-size:0.82rem;margin-top:3px">
                Ranking del Equipo &nbsp;·&nbsp; {n} farmers
            </div>
        </div>
        <div style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse;font-size:0.84rem;background:white">
            <thead>
                <tr style="background:#F8F9FA;border-bottom:2px solid #E5E7EB">
                    <th style="padding:11px 16px;text-align:center;color:#6B7280;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.8px;font-weight:600">#</th>
                    <th style="padding:11px 16px;text-align:left;color:#6B7280;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.8px;font-weight:600">FARMER</th>
                    <th style="padding:11px 16px;text-align:left;color:#6B7280;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.8px;font-weight:600">PAÍS</th>
                    <th style="padding:11px 16px;text-align:left;color:#6B7280;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.8px;font-weight:600">LÍDER</th>
                    <th style="padding:11px 16px;text-align:center;color:#6B7280;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.8px;font-weight:600">META</th>
                    <th style="padding:11px 16px;text-align:center;color:#6B7280;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.8px;font-weight:600">COMPLETADOS</th>
                    <th style="padding:11px 16px;text-align:center;color:#6B7280;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.8px;font-weight:600">DESC. DÍA</th>
                    <th style="padding:11px 16px;text-align:center;color:#6B7280;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.8px;font-weight:600">DESC. FOLLOWS</th>
                    <th style="padding:11px 16px;text-align:center;color:#6B7280;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.8px;font-weight:600">PENDIENTES</th>
                    <th style="padding:11px 16px;text-align:center;color:#6B7280;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.8px;font-weight:600">% CUMPL.</th>
                    <th style="padding:11px 16px;text-align:center;color:#6B7280;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.8px;font-weight:600">ESTADO</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── FALLBACK: productividad desde hoja Productividad ─────────────────────────
else:
    st.markdown("""
    <div class="rb-page-header">
        <h1>📋 ATT Productividad</h1>
        <p>Contactos efectivos por farmer: Zoho Voice + Treble + Videoconferencia.</p>
    </div>
    """, unsafe_allow_html=True)

    st.info("📂 Sube el archivo con la pestaña **ATT productividad** para ver el Follow Track. Mostrando datos de la hoja Productividad como referencia.")

    prod_rows = []
    for em, data in farmers_data.items():
        p     = data.get("productividad_pct")
        pct_nc = data.get("pct_no_contactados")
        prod_rows.append({
            "Farmer":          data.get("name", em),
            "Productividad %": f"{p*100:.1f}" if p is not None else None,
            "Qualifier":       "✅ OK" if (p is not None and p >= 0.90)
                               else ("⛔ PIERDE VARIABLE" if p is not None else "⚪ Sin dato"),
            "Follows totales": int(data.get("total_follows") or 0),
            "Sin contactar":   int(data.get("no_contactados") or 0),
            "% Sin contactar": f"{pct_nc:.1f}" if pct_nc is not None else None,
            "_prod_num":       round(p * 100, 1) if p is not None else None,
        })

    df_fb = pd.DataFrame(prod_rows).sort_values("_prod_num", ascending=False, na_position="last")

    def color_p(val):
        try:
            v = float(val)
            if v >= 90: return "color:#00B341;font-weight:bold"
            if v >= 80: return "color:#F59E0B;font-weight:bold"
            return "color:#EF4444;font-weight:bold"
        except: return ""

    display_cols = ["Farmer", "Productividad %", "Qualifier", "Follows totales", "Sin contactar", "% Sin contactar"]
    st.dataframe(df_fb[display_cols].style.map(color_p, subset=["Productividad %"]),
                 use_container_width=True, hide_index=True)
