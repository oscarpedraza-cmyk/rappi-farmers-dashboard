"""
core/style.py — Rappi Farmers Design System (Executive Edition)
Clean, minimal executive aesthetic with Rappi coral identity.
"""
from __future__ import annotations

# ── Design tokens ─────────────────────────────────────────────────────────────
BG_PAGE    = "#F8F9FB"   # page canvas — ultra-light blue-white
BG_CARD    = "#FFFFFF"   # card / chart surface
BG_NAV     = "#FFFFFF"   # top navbar
BG_SIDEBAR = "#FFFFFF"   # sidebar
C_RED      = "#FF441B"   # Rappi coral — primary accent
C_RED_DARK = "#E03A16"   # hover / pressed
C_RED_SOFT = "#FFF1EE"   # coral tint
C_GREEN    = "#16A34A"   # success (more refined green)
C_AMBER    = "#D97706"   # warning (deeper amber)
C_BLUE     = "#2563EB"   # info
C_TEXT     = "#0F172A"   # primary text (darker for contrast)
C_TEXT_2   = "#334155"   # secondary text
C_MUTED    = "#64748B"   # muted text
C_BORDER   = "#E2E8F0"   # borders (slightly cooler)
C_BORDER_2 = "#CBD5E1"   # stronger border
C_SHADOW   = "rgba(15,23,42,0.05)"  # base shadow
C_BG_RED   = "#FEF2F2"
C_BG_YEL   = "#FFFBEB"
C_BG_GRN   = "#F0FDF4"


def inject_global_css() -> str:
    return f"""
<style>
/* ── Fonts ──────────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,300..900;1,14..32,300..900&display=swap');

html, body, [class*="css"], [class*="st-"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    font-size: 14px;
    color: {C_TEXT};
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}}

/* ── Keyframes ───────────────────────────────────────────────────────────────── */
@keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(6px); }}
    to   {{ opacity: 1; transform: translateY(0);   }}
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
    padding-top: 0.4rem !important;
    padding-left: 1.6rem !important;
    padding-right: 1.6rem !important;
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
[data-testid="stSidebar"] hr {{ border-color: {C_BORDER} !important; }}
[data-testid="stSidebar"] .stButton > button {{
    background: {C_RED_SOFT} !important;
    color: {C_RED} !important;
    border: 1px solid rgba(255,68,27,0.2) !important;
}}

/* Nav links */
[data-testid="stSidebarNav"] a {{
    color: {C_MUTED} !important;
    border-radius: 7px !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    padding: 0.38rem 0.8rem !important;
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

/* ── Top Navbar ──────────────────────────────────────────────────────────────── */
.rb-topbar {{
    background: {BG_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 0.65rem 1.2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
    box-shadow: 0 1px 2px {C_SHADOW};
    animation: fadeIn 0.25s ease both;
}}
.rb-topbar-brand {{ display: flex; align-items: center; gap: 10px; }}
.rb-topbar-brand .brand-name {{
    font-size: 0.95rem; font-weight: 800; color: {C_TEXT} !important; letter-spacing: -0.3px;
}}
.rb-topbar-brand .brand-name span {{ color: {C_RED} !important; }}
.rb-topbar-right {{ display: flex; align-items: center; gap: 10px; }}
.rb-user-badge {{
    display: flex; align-items: center; gap: 7px;
    background: {C_RED_SOFT}; border: 1px solid rgba(255,68,27,0.15);
    border-radius: 8px; padding: 0.35rem 0.75rem;
}}
.rb-user-badge .user-name {{ font-size: 0.83rem; font-weight: 600; color: {C_TEXT}; }}
.rb-user-badge .user-role {{ font-size: 0.67rem; color: {C_MUTED}; }}
.rb-status-dot {{
    width: 7px; height: 7px; background: {C_GREEN}; border-radius: 50%;
    animation: pulse 2.5s ease-in-out infinite;
}}
.rb-meta-chip {{
    font-size: 0.69rem; color: {C_MUTED}; background: {BG_PAGE};
    border: 1px solid {C_BORDER}; border-radius: 5px; padding: 2px 7px;
}}

/* ── Page header ─────────────────────────────────────────────────────────────── */
.rb-page-header {{
    background: {BG_CARD};
    border: 1px solid {C_BORDER};
    border-left: 4px solid {C_RED};
    border-radius: 10px;
    padding: 0.9rem 1.3rem;
    margin-bottom: 1rem;
    animation: fadeIn 0.22s ease both;
    box-shadow: 0 1px 2px {C_SHADOW};
}}
.rb-page-header h1 {{
    margin: 0; font-size: 1.25rem; font-weight: 700;
    color: {C_TEXT}; letter-spacing: -0.3px;
}}
.rb-page-header p {{
    margin: 0.15rem 0 0; font-size: 0.8rem; color: {C_MUTED}; line-height: 1.5;
}}

/* ── Cards ───────────────────────────────────────────────────────────────────── */
.rb-card {{
    background: {BG_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 1.1rem 1.3rem;
    box-shadow: 0 1px 3px {C_SHADOW};
    margin-bottom: 0.75rem;
    animation: fadeIn 0.28s ease both;
}}

/* KPI metric card */
.rb-metric {{
    background: {BG_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 0.9rem 1.1rem;
    box-shadow: 0 1px 2px {C_SHADOW};
    text-align: center;
    animation: fadeIn 0.28s ease both;
}}
.rb-metric .rb-metric-label {{
    font-size: 0.65rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.5px; color: {C_MUTED}; margin-bottom: 4px;
}}
.rb-metric .rb-metric-value {{
    font-size: 1.8rem; font-weight: 800; color: {C_TEXT};
    line-height: 1.1; font-variant-numeric: tabular-nums;
}}
.rb-metric .rb-metric-sub {{
    font-size: 0.71rem; color: {C_MUTED}; margin-top: 3px;
}}

/* Executive stat block */
.rb-stat {{
    background: {BG_CARD}; border: 1px solid {C_BORDER};
    border-radius: 10px; padding: 1rem 1.2rem;
    box-shadow: 0 1px 2px {C_SHADOW};
}}
.rb-stat-label {{ font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px; color: {C_MUTED}; margin-bottom: 3px; }}
.rb-stat-value {{ font-size: 2rem; font-weight: 800; color: {C_TEXT}; line-height: 1; font-variant-numeric: tabular-nums; }}
.rb-stat-delta {{ font-size: 0.75rem; margin-top: 4px; font-weight: 500; }}

/* Upload status row */
.rb-upload-row {{
    display: grid;
    grid-template-columns: 2fr 1fr 1fr 1fr 1fr;
    gap: 0;
    align-items: center;
    padding: 0.65rem 1rem;
    border-bottom: 1px solid {C_BORDER};
    font-size: 0.82rem;
}}
.rb-upload-row:last-child {{ border-bottom: none; }}
.rb-upload-row:hover {{ background: #F8F9FB; }}
.rb-upload-header {{
    background: {BG_PAGE}; font-size: 0.68rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.5px; color: {C_MUTED};
}}

/* Filter bar */
.rb-filter-bar {{
    background: {BG_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 0.8rem 1.2rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 2px {C_SHADOW};
}}
.rb-filter-title {{
    font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.6px; color: {C_MUTED}; margin-bottom: 0.5rem;
}}

/* Section title */
.rb-section-title {{
    font-size: 0.9rem; font-weight: 700; color: {C_TEXT};
    margin: 1rem 0 0.5rem; letter-spacing: -0.2px;
}}
.rb-caption {{ font-size: 0.73rem; color: {C_MUTED}; }}

/* Upload section */
.rb-upload-section {{
    background: {BG_CARD}; border: 1px solid {C_BORDER};
    border-radius: 10px; padding: 1rem 1.3rem;
    box-shadow: 0 1px 2px {C_SHADOW}; margin-bottom: 0.75rem;
}}

/* ── Semáforo table ───────────────────────────────────────────────────────────── */
.semaforo-table tr:hover td {{ background: {C_RED_SOFT} !important; transition: background 0.12s; }}
.semaforo-table {{ border-radius: 10px; overflow: hidden; }}

/* ── Last update banner ───────────────────────────────────────────────────────── */
.last-update-banner {{
    background: {BG_CARD}; border-left: 3px solid {C_RED};
    border-radius: 0 8px 8px 0; padding: 0.45rem 0.9rem;
    margin-bottom: 0.85rem; font-size: 0.8rem; color: {C_TEXT};
    box-shadow: 0 1px 2px {C_SHADOW};
}}

/* ── Native Streamlit metrics ─────────────────────────────────────────────────── */
[data-testid="metric-container"] {{
    background: {BG_CARD} !important;
    border: 1px solid {C_BORDER} !important;
    border-radius: 10px !important;
    padding: 0.85rem 1.1rem !important;
    box-shadow: 0 1px 3px {C_SHADOW} !important;
    animation: fadeIn 0.28s ease both !important;
}}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{
    font-weight: 800 !important; color: {C_TEXT} !important;
    font-variant-numeric: tabular-nums !important;
}}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {{
    font-size: 0.7rem !important; font-weight: 600 !important;
    color: {C_MUTED} !important; text-transform: uppercase; letter-spacing: 0.5px;
}}
[data-testid="metric-container"] [data-testid="stMetricDelta"] svg {{ display: none; }}

/* ── Buttons ─────────────────────────────────────────────────────────────────── */
.stButton > button {{
    border-radius: 8px !important; font-weight: 600 !important;
    font-size: 0.84rem !important;
    transition: all 0.18s ease !important;
    background: {C_RED} !important;
    border-color: {C_RED} !important;
    color: white !important;
}}
.stButton > button:hover {{
    background: {C_RED_DARK} !important;
    border-color: {C_RED_DARK} !important;
    box-shadow: 0 3px 10px rgba(255,68,27,0.28) !important;
    transform: translateY(-1px) !important;
}}
.stButton > button:active {{
    transform: translateY(0) !important;
    box-shadow: none !important;
}}

/* ── File uploader ────────────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {{
    background: {C_RED_SOFT} !important;
    border: 2px dashed rgba(255,68,27,0.35) !important;
    border-radius: 10px !important;
    transition: border-color 0.15s, background 0.15s;
}}
[data-testid="stFileUploader"]:hover {{
    background: rgba(255,68,27,0.07) !important;
    border-color: {C_RED} !important;
}}
[data-testid="stFileUploaderDropzone"] button span:first-child {{ display: none !important; }}
[data-testid="stFileUploaderDropzone"] button {{ min-width: 90px !important; }}
[data-testid="stFileUploaderDropzoneInstructions"] > div > span:last-child {{ display: none !important; }}

/* ── Tabs ─────────────────────────────────────────────────────────────────────── */
[data-testid="stTab"] {{ font-weight: 600 !important; font-size: 0.84rem !important; color: {C_MUTED} !important; }}
[data-testid="stTab"]:hover {{ color: {C_RED} !important; }}
[data-testid="stTab"][aria-selected="true"] {{
    border-bottom: 2px solid {C_RED} !important; color: {C_RED} !important;
}}

/* ── Dataframe ───────────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] thead tr,
[data-testid="stDataEditor"] thead tr {{ background: {BG_PAGE} !important; }}
[data-testid="stDataFrame"] tbody tr,
[data-testid="stDataEditor"] tbody tr {{ border-bottom: 1px solid {C_BORDER} !important; }}
[data-testid="stDataFrame"] tbody tr:hover,
[data-testid="stDataEditor"] tbody tr:hover {{ background: {C_RED_SOFT} !important; }}

/* ── Inputs ──────────────────────────────────────────────────────────────────── */
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] > div > div {{
    border-radius: 7px !important; border-color: {C_BORDER} !important;
    transition: border-color 0.15s, box-shadow 0.15s;
}}
[data-testid="stNumberInput"] input:focus-visible,
[data-testid="stTextInput"] input:focus-visible {{
    border-color: {C_RED} !important;
    box-shadow: 0 0 0 3px rgba(255,68,27,0.12) !important;
    outline: none;
}}

/* ── Expander ────────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    background: {BG_CARD} !important; border: 1px solid {C_BORDER} !important;
    border-radius: 10px !important; box-shadow: 0 1px 2px {C_SHADOW} !important;
}}
[data-testid="stExpander"] details > summary {{
    list-style: none; cursor: pointer; display: flex;
    align-items: center; padding: 0.48rem 0.75rem;
    border-radius: 8px; user-select: none; gap: 6px;
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
.js-plotly-plot {{ background: {BG_CARD} !important; border-radius: 10px !important; }}

/* ── Alerts ──────────────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {{
    border-radius: 8px !important; font-size: 0.84rem !important;
    border-left-width: 3px !important;
}}

/* ── Scrollbar ───────────────────────────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 4px; height: 4px; }}
::-webkit-scrollbar-track {{ background: {BG_PAGE}; }}
::-webkit-scrollbar-thumb {{ background: #CBD5E1; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: #94A3B8; }}

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
