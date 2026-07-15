"""
core/style.py — Rappi Farmers Design System (Auditor PRO Theme)
"""
from __future__ import annotations

# ── Design tokens ─────────────────────────────────────────────────────────────
BG_PAGE    = "#f1f5f9"   # slate-100 canvas — mismo que Auditor PRO
BG_CARD    = "#FFFFFF"   # card / surface
BG_CARD_2  = "#f8fafc"   # muted card / alternating rows
BG_NAV     = "#FFFFFF"   # topbar
BG_SIDEBAR = "#FFFFFF"   # sidebar
C_RED      = "#ff441f"   # Rappi coral
C_RED_DARK = "#e03a17"   # hover
C_RED_SOFT = "#fff7ed"   # coral warm tint (auditor PRO #fff7ed)
C_GREEN    = "#16A34A"   # success
C_AMBER    = "#D97706"   # warning
C_BLUE     = "#2563EB"   # info
C_TEXT     = "#0F172A"   # primary text
C_TEXT_2   = "#334155"   # secondary
C_MUTED    = "#64748B"   # muted
C_MUTED_2  = "#94a3b8"   # very muted — section labels
C_BORDER   = "#E2E8F0"   # border
C_BORDER_2 = "#CBD5E1"   # stronger border
C_SHADOW   = "rgba(15,23,42,0.05)"
C_BG_RED   = "#FEF2F2"
C_BG_YEL   = "#FFFBEB"
C_BG_GRN   = "#F0FDF4"
C_GRAD     = "linear-gradient(135deg,#ff441f,#ff6b47)"  # Rappi gradient


def inject_global_css() -> str:
    return f"""
<style>
/* ── Base ────────────────────────────────────────────────────────────────────── */
html, body, [class*="css"], [class*="st-"] {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif !important;
    font-size: 13px;
    color: {C_TEXT};
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}}

/* ── Keyframes ───────────────────────────────────────────────────────────────── */
@keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(4px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes pulse {{
    0%, 100% {{ box-shadow: 0 0 0 0 rgba(22,163,74,0.4); }}
    50%       {{ box-shadow: 0 0 0 4px rgba(22,163,74,0); }}
}}
@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }}
}}

/* ── Page ────────────────────────────────────────────────────────────────────── */
.stApp {{ background: {BG_PAGE} !important; }}
.main .block-container {{
    background: {BG_PAGE} !important;
    padding-top: 0.35rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 1440px !important;
}}

/* ── Hide Streamlit chrome ───────────────────────────────────────────────────── */
#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent !important; box-shadow: none !important; }}
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {{ visibility: hidden !important; }}

/* ── Sidebar FIJO ────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {{
    transform: translateX(0) !important;
    visibility: visible !important;
    min-width: 240px !important;
    width: 240px !important;
    position: relative !important;
}}
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}

section[data-testid="stSidebar"],
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] {{
    background: {BG_SIDEBAR} !important;
    background-color: {BG_SIDEBAR} !important;
}}
[data-testid="stSidebar"] > div:first-child {{
    border-right: 1px solid {C_BORDER} !important;
}}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span {{ color: {C_MUTED} !important; }}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{ color: {C_TEXT} !important; }}
[data-testid="stSidebar"] hr {{
    border: none !important;
    border-top: 1px solid {C_BORDER} !important;
}}
[data-testid="stSidebar"] .stButton > button {{
    background: {BG_PAGE} !important;
    color: {C_MUTED} !important;
    border: 1px solid {C_BORDER} !important;
    box-shadow: none !important;
}}

/* ── Sidebar nav ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebarNav"]::before {{
    content: "PÁGINAS";
    display: block;
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 1.6px;
    color: {C_MUTED_2};
    padding: 0 0.85rem 0.3rem;
    text-transform: uppercase;
}}
[data-testid="stSidebarNav"] a {{
    color: {C_MUTED} !important;
    border-radius: 7px !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    padding: 0.35rem 0.8rem !important;
    transition: background 0.15s, color 0.15s;
}}
[data-testid="stSidebarNav"] a:hover {{
    background: {C_RED_SOFT} !important;
    color: {C_RED} !important;
}}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: {C_RED} !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
}}
[data-testid="stSidebarNav"] svg {{ display: none; }}

/* ── Sidebar brand footer ────────────────────────────────────────────────────── */
.rb-sidebar-footer {{
    font-size: 0.68rem;
    color: {C_MUTED_2};
    padding: 0.4rem 0.3rem 0.2rem;
    letter-spacing: 0.2px;
    line-height: 1.5;
}}
.rb-sidebar-footer strong {{ color: {C_RED}; }}

/* ── Topbar ──────────────────────────────────────────────────────────────────── */
.rb-topbar {{
    background: {BG_CARD};
    border-bottom: 1px solid {C_BORDER};
    padding: 0.55rem 1rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
    animation: fadeIn 0.2s ease both;
    border-radius: 10px;
    border: 1px solid {C_BORDER};
}}
.rb-topbar-brand {{ display: flex; align-items: center; gap: 10px; }}
.rb-topbar-brand .rb-brand-icon {{
    width: 32px; height: 32px; border-radius: 8px;
    background: {C_GRAD};
    display: flex; align-items: center; justify-content: center;
    font-weight: 900; color: white; font-size: 14px;
    flex-shrink: 0;
}}
.rb-topbar-brand .brand-name {{
    font-size: 14px; font-weight: 800;
    color: {C_TEXT} !important; letter-spacing: -0.3px; line-height: 1;
}}
.rb-topbar-brand .brand-sub {{
    font-size: 9px; color: {C_MUTED_2}; text-transform: uppercase;
    letter-spacing: 0.07em; margin-top: 2px;
}}
.rb-user-badge {{
    display: flex; align-items: center; gap: 7px;
    background: {BG_CARD_2}; border: 1px solid {C_BORDER};
    border-radius: 20px; padding: 4px 10px 4px 6px;
}}
.rb-user-badge .user-avatar {{
    width: 24px; height: 24px; border-radius: 50%;
    background: {C_GRAD};
    display: flex; align-items: center; justify-content: center;
    color: white; font-weight: 900; font-size: 10px; flex-shrink: 0;
}}
.rb-user-badge .user-name {{
    font-size: 11px; font-weight: 700; color: {C_TEXT_2};
    max-width: 110px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}
.rb-user-badge .user-role {{
    font-size: 10px; color: {C_MUTED_2};
}}
.rb-status-dot {{
    width: 7px; height: 7px; background: {C_GREEN}; border-radius: 50%;
    animation: pulse 2.5s ease-in-out infinite;
}}
.rb-meta-chip {{
    font-size: 10px; color: {C_MUTED}; background: {BG_CARD_2};
    border: 1px solid {C_BORDER}; border-radius: 5px; padding: 2px 8px;
}}

/* ── Logout button ───────────────────────────────────────────────────────────── */
.rb-logout-btn .stButton > button {{
    background: {BG_PAGE} !important;
    border: 1px solid {C_BORDER} !important;
    color: {C_MUTED} !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    padding: 5px 11px !important;
    box-shadow: none !important;
    min-height: 0 !important;
    line-height: 1.4 !important;
    border-radius: 8px !important;
}}
.rb-logout-btn .stButton > button:hover {{
    background: #fef2f2 !important;
    color: {C_RED} !important;
    border-color: rgba(255,68,31,0.35) !important;
    box-shadow: none !important;
    transform: none !important;
}}

/* ── Page header ─────────────────────────────────────────────────────────────── */
.rb-page-header {{
    background: {BG_CARD};
    border: 1.5px solid {C_BORDER};
    border-left: 3px solid {C_RED};
    border-radius: 14px;
    padding: 0.85rem 1.2rem;
    margin-bottom: 1rem;
    animation: fadeIn 0.2s ease both;
}}
.rb-page-header h1 {{
    margin: 0; font-size: 15px; font-weight: 800; color: {C_TEXT}; letter-spacing: -0.3px;
}}
.rb-page-header p {{
    margin: 0.2rem 0 0; font-size: 12px; color: {C_MUTED}; line-height: 1.5;
}}

/* ── Cards ───────────────────────────────────────────────────────────────────── */
.rb-card {{
    background: {BG_CARD};
    border: 1.5px solid {C_BORDER};
    border-radius: 14px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.75rem;
    animation: fadeIn 0.25s ease both;
}}

/* ── Section title — Auditor PRO style (UPPERCASE + trailing line) ─────────── */
.rb-section-title {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 10px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: {C_MUTED_2};
    margin: 1.1rem 0 0.65rem;
}}
.rb-section-title::after {{
    content: '';
    flex: 1;
    height: 1px;
    background: {C_BORDER};
}}
.rb-caption {{ font-size: 11px; color: {C_MUTED_2}; }}

/* ── KPI metric card ─────────────────────────────────────────────────────────── */
.rb-metric {{
    background: {BG_CARD_2};
    border: 1.5px solid {C_BORDER};
    border-radius: 13px;
    padding: 14px 16px;
    text-align: left;
    animation: fadeIn 0.25s ease both;
}}
.rb-metric .rb-metric-label {{
    font-size: 9px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.05em; color: {C_MUTED_2}; margin-bottom: 5px;
}}
.rb-metric .rb-metric-value {{
    font-size: 17px; font-weight: 900; color: {C_TEXT};
    line-height: 1.1; font-variant-numeric: tabular-nums;
}}
.rb-metric .rb-metric-sub {{
    font-size: 11px; color: {C_MUTED}; margin-top: 3px;
}}

/* ── Stat block ──────────────────────────────────────────────────────────────── */
.rb-stat {{
    background: {BG_CARD}; border: 1.5px solid {C_BORDER};
    border-radius: 14px; padding: 14px 16px;
}}
.rb-stat-label {{
    font-size: 9px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.05em; color: {C_MUTED_2}; margin-bottom: 4px;
}}
.rb-stat-value {{
    font-size: 22px; font-weight: 900; color: {C_TEXT}; line-height: 1;
    font-variant-numeric: tabular-nums;
}}
.rb-stat-delta {{ font-size: 12px; margin-top: 4px; font-weight: 600; }}

/* ── Upload status row ───────────────────────────────────────────────────────── */
.rb-upload-row {{
    display: grid;
    grid-template-columns: 2fr 1fr 1fr 1fr 1fr;
    gap: 0;
    align-items: center;
    padding: 10px 14px;
    border-bottom: 1px solid {C_BORDER};
    font-size: 12px;
}}
.rb-upload-row:last-child {{ border-bottom: none; }}
.rb-upload-row:hover {{ background: {BG_CARD_2}; }}
.rb-upload-header {{
    background: {BG_PAGE}; font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.07em; color: {C_MUTED_2};
}}

/* ── Filter bar ──────────────────────────────────────────────────────────────── */
.rb-filter-bar {{
    background: {BG_CARD};
    border: 1.5px solid {C_BORDER};
    border-radius: 14px;
    padding: 12px 16px;
    margin-bottom: 1rem;
}}
.rb-filter-title {{
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: {C_MUTED_2}; margin-bottom: 0.5rem;
}}

/* ── Upload section ──────────────────────────────────────────────────────────── */
.rb-upload-section {{
    background: {BG_CARD}; border: 1.5px solid {C_BORDER};
    border-radius: 14px; padding: 1rem 1.2rem;
    margin-bottom: 0.75rem;
}}

/* ── Semáforo table ──────────────────────────────────────────────────────────── */
.semaforo-table tr:hover td {{ background: {C_RED_SOFT} !important; transition: background 0.12s; }}
.semaforo-table {{ border-radius: 14px; overflow: hidden; }}

/* ── Last update banner ──────────────────────────────────────────────────────── */
.last-update-banner {{
    background: {BG_CARD}; border-left: 3px solid {C_RED};
    border-radius: 0 8px 8px 0; padding: 6px 14px;
    margin-bottom: 12px; font-size: 12px; color: {C_TEXT};
}}

/* ── Native Streamlit metrics ────────────────────────────────────────────────── */
[data-testid="metric-container"] {{
    background: {BG_CARD_2} !important;
    border: 1.5px solid {C_BORDER} !important;
    border-radius: 13px !important;
    padding: 14px 16px !important;
    animation: fadeIn 0.25s ease both !important;
}}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{
    font-weight: 900 !important; color: {C_TEXT} !important;
    font-variant-numeric: tabular-nums !important;
    font-size: 1.4rem !important;
}}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {{
    font-size: 9px !important; font-weight: 700 !important;
    color: {C_MUTED_2} !important; text-transform: uppercase;
    letter-spacing: 0.05em;
}}
[data-testid="metric-container"] [data-testid="stMetricDelta"] svg {{ display: none; }}

/* ── Buttons ─────────────────────────────────────────────────────────────────── */
.stButton > button {{
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 12px !important;
    transition: all 0.15s ease !important;
    background: {C_GRAD} !important;
    border: none !important;
    color: white !important;
}}
.stButton > button:hover {{
    opacity: 0.9 !important;
    box-shadow: 0 4px 12px rgba(255,68,31,0.3) !important;
    transform: translateY(-1px) !important;
}}
.stButton > button:active {{
    transform: translateY(0) !important;
    box-shadow: none !important;
}}

/* ── Secondary / ghost button ────────────────────────────────────────────────── */
.rb-btn-secondary .stButton > button {{
    background: {BG_PAGE} !important;
    color: {C_MUTED} !important;
    border: 1px solid {C_BORDER} !important;
    font-weight: 700 !important;
    box-shadow: none !important;
}}
.rb-btn-secondary .stButton > button:hover {{
    background: {C_BORDER} !important;
    transform: none !important;
    box-shadow: none !important;
}}

/* ── File uploader ────────────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {{
    background: {C_RED_SOFT} !important;
    border: 2px dashed rgba(255,68,31,0.3) !important;
    border-radius: 12px !important;
    transition: border-color 0.15s, background 0.15s;
}}
[data-testid="stFileUploader"]:hover {{
    background: rgba(255,68,31,0.07) !important;
    border-color: {C_RED} !important;
}}
[data-testid="stFileUploaderDropzone"] button span:first-child {{ display: none !important; }}
[data-testid="stFileUploaderDropzone"] button {{ min-width: 90px !important; }}
[data-testid="stFileUploaderDropzoneInstructions"] > div > span:last-child {{ display: none !important; }}

/* ── Tabs ─────────────────────────────────────────────────────────────────────── */
[data-testid="stTab"] {{
    font-weight: 600 !important; font-size: 12px !important; color: {C_MUTED} !important;
}}
[data-testid="stTab"]:hover {{ color: {C_RED} !important; }}
[data-testid="stTab"][aria-selected="true"] {{
    border-bottom: 2.5px solid {C_RED} !important; color: {C_RED} !important;
}}

/* ── Dataframe — dark header, auditor PRO style ──────────────────────────────── */
[data-testid="stDataFrame"] thead tr th,
[data-testid="stDataEditor"] thead tr th {{
    background: {C_TEXT} !important;
    color: white !important;
    font-size: 10px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    padding: 9px 12px !important;
}}
[data-testid="stDataFrame"] tbody tr,
[data-testid="stDataEditor"] tbody tr {{
    border-bottom: 1px solid {C_BORDER} !important;
}}
[data-testid="stDataFrame"] tbody tr:nth-child(even),
[data-testid="stDataEditor"] tbody tr:nth-child(even) {{
    background: {BG_CARD_2} !important;
}}
[data-testid="stDataFrame"] tbody tr:hover,
[data-testid="stDataEditor"] tbody tr:hover {{
    background: {C_RED_SOFT} !important;
}}

/* ── Inputs ──────────────────────────────────────────────────────────────────── */
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] > div > div {{
    border-radius: 8px !important; border-color: {C_BORDER} !important;
    font-size: 13px !important;
    transition: border-color 0.15s, box-shadow 0.15s;
}}
[data-testid="stNumberInput"] input:focus-visible,
[data-testid="stTextInput"] input:focus-visible {{
    border-color: {C_RED} !important;
    box-shadow: 0 0 0 3px rgba(255,68,31,0.12) !important;
    outline: none;
}}
[data-testid="stSelectbox"] > div > div:focus-within,
[data-testid="stMultiSelect"] > div > div:focus-within {{
    border-color: {C_RED} !important;
    box-shadow: 0 0 0 2px rgba(255,68,31,0.12) !important;
}}
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {{
    background: {C_RED_SOFT} !important;
    border-color: rgba(255,68,31,0.25) !important;
    color: {C_RED} !important;
    font-size: 11px !important;
    border-radius: 5px !important;
}}

/* ── Radio buttons ───────────────────────────────────────────────────────────── */
[data-testid="stRadio"] label,
[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {{
    font-size: 12px !important;
    color: {C_TEXT_2} !important;
}}

/* ── Expander ────────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    background: {BG_CARD} !important; border: 1.5px solid {C_BORDER} !important;
    border-radius: 14px !important;
}}
[data-testid="stExpander"] details > summary {{
    list-style: none; cursor: pointer; display: flex;
    align-items: center; padding: 10px 14px;
    border-radius: 12px; user-select: none; gap: 6px;
    background: {BG_CARD_2};
}}
[data-testid="stExpander"] details > summary::-webkit-details-marker {{ display: none; }}
[data-testid="stExpander"] details > summary > :first-child {{
    font-size: 0 !important; width: 14px !important; min-width: 14px !important;
    height: 14px !important; overflow: hidden;
}}
[data-testid="stExpander"] details > summary > :first-child svg {{
    width: 14px !important; height: 14px !important; display: block;
}}
[data-testid="stExpander"] details > summary::before {{
    content: ''; display: inline-block; width: 5px; height: 5px;
    border-right: 1.5px solid {C_MUTED}; border-bottom: 1.5px solid {C_MUTED};
    transform: rotate(-45deg); flex-shrink: 0; transition: transform 0.12s ease;
}}
[data-testid="stExpander"] details[open] > summary::before {{ transform: rotate(45deg); }}

/* ── Plotly ──────────────────────────────────────────────────────────────────── */
.js-plotly-plot {{ background: {BG_CARD} !important; border-radius: 14px !important; }}

/* ── Alerts ──────────────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {{
    border-radius: 10px !important; font-size: 12px !important;
    border-left-width: 3px !important;
}}
[data-testid="stAlert"] [data-testid="stMarkdownContainer"] {{
    font-size: 12px !important;
}}

/* ── HR divider ──────────────────────────────────────────────────────────────── */
hr {{
    border: none !important;
    border-top: 1px solid {C_BORDER} !important;
    margin: 0.7rem 0 !important;
    opacity: 1 !important;
}}

/* ── Section headings (markdown ## ###) ──────────────────────────────────────── */
.main .block-container h1,
.main .block-container h2,
.main .block-container h3,
.main .block-container h4 {{
    font-family: 'Segoe UI', system-ui, sans-serif !important;
}}
.main .block-container h1 {{
    font-size: 15px !important; font-weight: 800 !important;
    color: {C_TEXT} !important; letter-spacing: -0.3px !important;
    margin: 1rem 0 0.5rem !important;
    padding-bottom: 8px !important;
    border-bottom: 1px solid {C_BORDER} !important;
}}
.main .block-container h2 {{
    font-size: 13px !important; font-weight: 800 !important;
    color: {C_TEXT} !important; margin: 0.9rem 0 0.4rem !important;
}}
.main .block-container h3 {{
    font-size: 12px !important; font-weight: 700 !important;
    color: {C_TEXT_2} !important; margin: 0.7rem 0 0.35rem !important;
}}
.main .block-container h4 {{
    font-size: 10px !important; font-weight: 700 !important;
    color: {C_MUTED_2} !important; text-transform: uppercase !important;
    letter-spacing: 0.07em !important; margin: 0.65rem 0 0.3rem !important;
}}

/* ── Caption text ────────────────────────────────────────────────────────────── */
.stCaption {{ color: {C_MUTED_2} !important; font-size: 11px !important; }}

/* ── Empty state ─────────────────────────────────────────────────────────────── */
.rb-empty-state {{
    background: {BG_CARD};
    border: 2px dashed {C_BORDER};
    border-radius: 24px;
    padding: 56px 32px;
    text-align: center;
    margin: 1rem 0;
}}
.rb-empty-state .rb-empty-icon {{ font-size: 3.25rem; margin-bottom: 0.75rem; }}
.rb-empty-state h3 {{
    color: {C_TEXT} !important; font-size: 15px !important;
    font-weight: 800 !important; margin: 0 0 0.4rem !important;
    border: none !important; padding: 0 !important;
}}
.rb-empty-state p {{ color: {C_MUTED}; font-size: 12px; margin: 0; line-height: 1.6; }}

/* ── Scrollbar ───────────────────────────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 4px; height: 4px; }}
::-webkit-scrollbar-track {{ background: {BG_PAGE}; }}
::-webkit-scrollbar-thumb {{ background: {C_BORDER_2}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {C_MUTED_2}; }}

/* ── Staggered metric animation ──────────────────────────────────────────────── */
[data-testid="column"]:nth-child(1) [data-testid="metric-container"] {{ animation-delay: 0.04s; }}
[data-testid="column"]:nth-child(2) [data-testid="metric-container"] {{ animation-delay: 0.08s; }}
[data-testid="column"]:nth-child(3) [data-testid="metric-container"] {{ animation-delay: 0.12s; }}
[data-testid="column"]:nth-child(4) [data-testid="metric-container"] {{ animation-delay: 0.16s; }}
[data-testid="column"]:nth-child(5) [data-testid="metric-container"] {{ animation-delay: 0.20s; }}
</style>

<script>
(function() {{
    if (window._rappiArrowMo) {{ window._rappiArrowMo.disconnect(); }}
    function fixArrows() {{
        document.querySelectorAll('[data-testid="stExpander"] details > summary').forEach(function(s) {{
            var w = document.createTreeWalker(s, NodeFilter.SHOW_TEXT, null, false), n;
            while ((n = w.nextNode())) {{ if (/_?arrow_/.test(n.textContent)) n.textContent = ''; }}
        }});
    }}
    var _p = false;
    var mo = new MutationObserver(function() {{
        if (!_p) {{ _p = true; requestAnimationFrame(function() {{ _p = false; fixArrows(); }}); }}
    }});
    window._rappiArrowMo = mo;
    function attach() {{ fixArrows(); mo.observe(document.body, {{ childList: true, subtree: true }}); }}
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', attach);
    else attach();
    [300, 800].forEach(function(ms) {{ setTimeout(fixArrows, ms); }});
}})();
</script>
"""
