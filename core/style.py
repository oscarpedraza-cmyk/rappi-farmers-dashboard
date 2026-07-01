"""
core/style.py — Rappi Farmers Design System
White-canvas Rappi Partners aesthetic. Call inject_global_css() once per page.
"""

# ── Design tokens ─────────────────────────────────────────────────────────────
BG_PAGE    = "#F5F5F7"   # page canvas — Apple-grade off-white
BG_CARD    = "#FFFFFF"   # card / chart surface
BG_NAV     = "#FFFFFF"   # top navbar — white with border
BG_SIDEBAR = "#FFFFFF"   # sidebar — white with coral active state
C_RED      = "#FF441B"   # Rappi coral — primary accent
C_RED_DARK = "#E03A16"   # hover / pressed
C_RED_SOFT = "#FFF1EE"   # coral tint for backgrounds
C_GREEN    = "#00B341"   # success
C_AMBER    = "#F59E0B"   # warning
C_BLUE     = "#2563EB"   # info
C_TEXT     = "#111827"   # primary text
C_MUTED    = "#6B7280"   # secondary text
C_BORDER   = "#E5E7EB"   # borders
C_SHADOW   = "rgba(0,0,0,0.06)"  # base shadow colour


def inject_global_css() -> str:
    return f"""
<style>
/* ── Fonts ──────────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20,400,0,0&family=Inter:wght@400;500;600;700;800;900&display=swap');

.material-symbols-rounded {{
    font-family: 'Material Symbols Rounded' !important;
    font-weight: normal !important; font-style: normal !important;
    font-size: 1.1em !important; line-height: 1; letter-spacing: normal;
    text-transform: none; display: inline-block; white-space: nowrap;
    -webkit-font-feature-settings: 'liga'; font-feature-settings: 'liga';
    -webkit-font-smoothing: antialiased; vertical-align: middle;
}}

html, body, [class*="css"], [class*="st-"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    font-size: 15px;
    color: {C_TEXT};
    -webkit-font-smoothing: antialiased;
}}

/* ── Keyframes ───────────────────────────────────────────────────────────────── */
@keyframes fadeSlideUp {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to   {{ opacity: 1; transform: translateY(0);    }}
}}
@keyframes pulseGreen {{
    0%, 100% {{ box-shadow: 0 0 0 0   rgba(0,179,65,0.45); }}
    50%       {{ box-shadow: 0 0 0 5px rgba(0,179,65,0);    }}
}}
@keyframes shimmer {{
    0%   {{ background-position: -400px 0; }}
    100% {{ background-position:  400px 0; }}
}}

@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }}
}}

/* ── Page background ─────────────────────────────────────────────────────────── */
.stApp {{
    background: {BG_PAGE} !important;
}}
.main .block-container {{
    background: {BG_PAGE} !important;
    padding-top: 0.5rem !important;
    padding-left: 1.8rem !important;
    padding-right: 1.8rem !important;
    max-width: 1400px !important;
}}

/* ── Hide Streamlit chrome ───────────────────────────────────────────────────── */
#MainMenu {{ visibility: hidden; }}
footer    {{ visibility: hidden; }}
header    {{ visibility: hidden; }}

/* ── Hide sidebar collapse toggle ────────────────────────────────────────────── */
[data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}
[data-testid="collapsedControl"]          {{ display: none !important; }}
section[data-testid="stSidebar"][aria-expanded="false"] + div .main
    .block-container {{ padding-left: 1.8rem !important; }}

/* ── Sidebar — white with coral active ───────────────────────────────────────── */
[data-testid="stSidebar"] > div:first-child {{
    background: {BG_SIDEBAR} !important;
    border-right: 1px solid {C_BORDER};
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
    border: 1px solid rgba(255,68,27,0.22) !important;
    transition: background 0.18s, box-shadow 0.18s;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background: rgba(255,68,27,0.14) !important;
    box-shadow: 0 2px 8px rgba(255,68,27,0.18) !important;
}}

/* Nav links */
[data-testid="stSidebarNav"] a {{
    color: {C_MUTED} !important;
    border-radius: 8px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    padding: 0.42rem 0.85rem !important;
    transition: background 0.15s, color 0.15s;
}}
[data-testid="stSidebarNav"] a:hover {{
    background: {C_RED_SOFT} !important;
    color: {C_RED} !important;
}}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: {C_RED} !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
}}
[data-testid="stSidebarNav"] svg {{ display: none; }}

/* ── Top navbar (rendered via HTML) ──────────────────────────────────────────── */
.rb-topbar {{
    background: {BG_NAV};
    border: 1px solid {C_BORDER};
    border-radius: 12px;
    padding: 0.78rem 1.3rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.1rem;
    box-shadow: 0 1px 3px {C_SHADOW}, 0 4px 12px rgba(0,0,0,0.04);
    animation: fadeSlideUp 0.30s ease-out both;
}}
.rb-topbar-brand {{
    display: flex;
    align-items: center;
    gap: 10px;
}}
.rb-topbar-brand .brand-name {{
    font-size: 1rem;
    font-weight: 800;
    color: {C_TEXT};
    letter-spacing: -0.3px;
}}
.rb-topbar-brand .brand-name span {{ color: {C_RED}; }}
.rb-topbar-right {{
    display: flex;
    align-items: center;
    gap: 12px;
}}
.rb-user-badge {{
    display: flex;
    align-items: center;
    gap: 8px;
    background: {C_RED_SOFT};
    border: 1px solid rgba(255,68,27,0.18);
    border-radius: 9px;
    padding: 0.4rem 0.85rem;
}}
.rb-user-badge .user-name {{
    font-size: 0.87rem;
    font-weight: 700;
    color: {C_TEXT};
}}
.rb-user-badge .user-role {{
    font-size: 0.69rem;
    color: {C_MUTED};
    margin-top: 1px;
}}
.rb-status-dot {{
    width: 8px; height: 8px;
    background: {C_GREEN};
    border-radius: 50%;
    animation: pulseGreen 2.2s ease-in-out infinite;
}}
.rb-meta-chip {{
    font-size: 0.71rem;
    color: {C_MUTED};
    background: {BG_PAGE};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 3px 8px;
}}

/* ── Cards ───────────────────────────────────────────────────────────────────── */
.rb-card {{
    background: {BG_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 12px;
    padding: 1.25rem 1.45rem;
    box-shadow: 0 1px 3px {C_SHADOW}, 0 4px 14px rgba(0,0,0,0.04);
    margin-bottom: 0.85rem;
    transition: opacity 0.22s ease, transform 0.22s ease;
    animation: fadeSlideUp 0.32s ease-out both;
    will-change: transform;
}}
.rb-card:hover {{
    transform: translateY(-2px);
    opacity: 0.97;
}}

/* KPI metric card */
.rb-metric {{
    background: {BG_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 12px;
    padding: 1rem 1.15rem;
    box-shadow: 0 1px 3px {C_SHADOW}, 0 4px 14px rgba(0,0,0,0.04);
    text-align: center;
    transition: transform 0.22s ease;
    animation: fadeSlideUp 0.32s ease-out both;
    will-change: transform;
}}
.rb-metric:hover {{
    transform: translateY(-2px);
}}
.rb-metric .rb-metric-label {{
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: {C_MUTED};
    margin-bottom: 5px;
}}
.rb-metric .rb-metric-value {{
    font-size: 1.9rem;
    font-weight: 800;
    color: {C_TEXT};
    line-height: 1.1;
    font-variant-numeric: tabular-nums;
}}
.rb-metric .rb-metric-sub {{
    font-size: 0.75rem;
    color: {C_MUTED};
    margin-top: 4px;
}}

/* Section title */
.rb-section-title {{
    font-size: 1rem;
    font-weight: 700;
    color: {C_TEXT};
    margin: 1.1rem 0 0.55rem;
    letter-spacing: -0.2px;
}}

/* Page header */
.rb-page-header {{
    background: {BG_CARD};
    border: 1px solid {C_BORDER};
    border-top: 3px solid {C_RED};
    border-radius: 12px;
    padding: 1rem 1.45rem;
    box-shadow: 0 1px 3px {C_SHADOW}, 0 4px 14px rgba(0,0,0,0.04);
    margin-bottom: 1.1rem;
    animation: fadeSlideUp 0.28s ease-out both;
}}
.rb-page-header h1 {{
    margin: 0;
    font-size: 1.4rem;
    font-weight: 800;
    color: {C_TEXT};
    letter-spacing: -0.4px;
    text-wrap: balance;
}}
.rb-page-header p {{
    margin: 0.18rem 0 0;
    font-size: 0.83rem;
    color: {C_MUTED};
    line-height: 1.5;
}}

/* Caption */
.rb-caption {{ font-size: 0.76rem; color: {C_MUTED}; }}

/* Upload section */
.rb-upload-section {{
    background: {BG_CARD};
    border: 1px solid {C_BORDER};
    border-top: 3px solid {C_RED};
    border-radius: 12px;
    padding: 1.15rem 1.45rem;
    box-shadow: 0 1px 3px {C_SHADOW}, 0 4px 14px rgba(0,0,0,0.04);
    margin-bottom: 1.1rem;
}}

/* ── Semáforo table ───────────────────────────────────────────────────────────── */
.semaforo-table tr:hover td {{ background: {C_RED_SOFT} !important; transition: background 0.15s; }}
.semaforo-table {{ border-radius: 12px; overflow: hidden; }}

/* ── Last update banner ───────────────────────────────────────────────────────── */
.last-update-banner {{
    background: {BG_CARD};
    border-left: 3px solid {C_RED};
    border-radius: 0 10px 10px 0;
    padding: 0.55rem 1rem;
    margin-bottom: 1rem;
    font-size: 0.83rem;
    color: {C_TEXT};
    box-shadow: 0 1px 3px {C_SHADOW};
}}

/* ── Native Streamlit metrics ─────────────────────────────────────────────────── */
[data-testid="metric-container"] {{
    background: {BG_CARD} !important;
    border: 1px solid {C_BORDER} !important;
    border-radius: 12px !important;
    padding: 0.95rem 1.15rem !important;
    box-shadow: 0 1px 3px {C_SHADOW}, 0 4px 14px rgba(0,0,0,0.04) !important;
    transition: transform 0.22s ease !important;
    animation: fadeSlideUp 0.30s ease-out both !important;
    will-change: transform;
}}
[data-testid="metric-container"]:hover {{
    transform: translateY(-2px);
}}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{
    font-weight: 800 !important;
    color: {C_TEXT} !important;
    font-variant-numeric: tabular-nums !important;
}}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {{
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    color: {C_MUTED} !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
[data-testid="metric-container"] [data-testid="stMetricDelta"] svg {{ display: none; }}

/* ── Buttons ─────────────────────────────────────────────────────────────────── */
.stButton > button {{
    border-radius: 9px !important;
    font-weight: 600 !important;
    font-size: 0.87rem !important;
    transition: background 0.20s ease, border-color 0.20s ease, box-shadow 0.20s ease, transform 0.20s ease !important;
    background: {C_RED} !important;
    border-color: {C_RED} !important;
    color: white !important;
}}
.stButton > button:hover {{
    background: {C_RED_DARK} !important;
    border-color: {C_RED_DARK} !important;
    box-shadow: 0 4px 14px rgba(255,68,27,0.32) !important;
    transform: translateY(-1px) !important;
}}
.stButton > button:active {{
    transform: translateY(0) scale(0.98) !important;
    box-shadow: none !important;
}}

/* ── File uploader ────────────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {{
    background: {C_RED_SOFT} !important;
    border: 2px dashed rgba(255,68,27,0.40) !important;
    border-radius: 12px !important;
    padding: 0.5rem !important;
    transition: border-color 0.18s, background 0.18s;
}}
[data-testid="stFileUploader"]:hover {{
    background: rgba(255,68,27,0.08) !important;
    border-color: {C_RED} !important;
}}
[data-testid="stFileUploaderDropzone"] button span:first-child {{ display: none !important; }}
[data-testid="stFileUploaderDropzone"] button {{ min-width: 90px !important; }}
[data-testid="stFileUploaderDropzoneInstructions"] > div > span:last-child {{ display: none !important; }}

/* ── Tabs ─────────────────────────────────────────────────────────────────────── */
[data-testid="stTab"] {{ font-weight: 600 !important; font-size: 0.87rem !important; color: {C_MUTED} !important; transition: color 0.18s; }}
[data-testid="stTab"]:hover {{ color: {C_RED} !important; }}
[data-testid="stTab"][aria-selected="true"] {{
    border-bottom: 2.5px solid {C_RED} !important;
    color: {C_RED} !important;
}}

/* ── Dataframe / data editor ──────────────────────────────────────────────────── */
[data-testid="stDataFrame"] thead tr,
[data-testid="stDataEditor"] thead tr {{
    background: {BG_PAGE} !important;
}}
[data-testid="stDataFrame"] tbody tr,
[data-testid="stDataEditor"] tbody tr {{
    border-bottom: 1px solid {C_BORDER} !important;
    transition: background 0.12s;
}}
[data-testid="stDataFrame"] tbody tr:hover,
[data-testid="stDataEditor"] tbody tr:hover {{
    background: {C_RED_SOFT} !important;
}}

/* ── Inputs / selects ────────────────────────────────────────────────────────── */
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] > div > div {{
    border-radius: 8px !important;
    border-color: {C_BORDER} !important;
    transition: border-color 0.18s, box-shadow 0.18s;
}}
[data-testid="stNumberInput"] input:focus-visible,
[data-testid="stTextInput"] input:focus-visible {{
    border-color: {C_RED} !important;
    box-shadow: 0 0 0 3px rgba(255,68,27,0.15) !important;
    outline: none;
}}

/* ── Expander ────────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    background: {BG_CARD} !important;
    border: 1px solid {C_BORDER} !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 3px {C_SHADOW} !important;
    transition: box-shadow 0.20s;
}}
[data-testid="stExpander"]:hover {{
    box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
}}
[data-testid="stExpander"] details > summary {{
    list-style: none; cursor: pointer; display: flex;
    align-items: center; padding: 0.52rem 0.8rem;
    border-radius: 10px; user-select: none; gap: 6px;
}}
[data-testid="stExpander"] details > summary::-webkit-details-marker {{ display: none; }}

/* ── KEY FIX: suppress arrow text nodes when icon font isn't loaded ── */
[data-testid="stExpander"] details > summary > :first-child {{
    font-size: 0 !important; line-height: 0 !important;
    width: 14px !important; min-width: 14px !important;
    height: 14px !important; flex-shrink: 0; overflow: hidden;
}}
[data-testid="stExpander"] details > summary > :first-child svg {{
    width: 14px !important; height: 14px !important; display: block;
}}
[data-testid="stExpander"] details > summary::before {{
    content: '';
    display: inline-block;
    width: 5px; height: 5px;
    border-right: 1.8px solid {C_MUTED};
    border-bottom: 1.8px solid {C_MUTED};
    transform: rotate(-45deg);
    flex-shrink: 0;
    transition: transform 0.15s ease;
}}
[data-testid="stExpander"] details[open] > summary::before {{
    transform: rotate(45deg);
}}

/* ── Plotly chart container ───────────────────────────────────────────────────── */
.js-plotly-plot {{
    background: {BG_CARD} !important;
    border-radius: 12px !important;
}}

/* ── Alerts ──────────────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {{
    border-radius: 10px !important;
    font-size: 0.87rem !important;
    border-left-width: 3px !important;
}}

/* ── Scrollbar ───────────────────────────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: {BG_PAGE}; }}
::-webkit-scrollbar-thumb {{ background: #D1D5DB; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: #9CA3AF; }}

/* ── Stagger entry animation for column grids ────────────────────────────────── */
[data-testid="column"]:nth-child(1) [data-testid="metric-container"] {{ animation-delay: 0.05s; }}
[data-testid="column"]:nth-child(2) [data-testid="metric-container"] {{ animation-delay: 0.10s; }}
[data-testid="column"]:nth-child(3) [data-testid="metric-container"] {{ animation-delay: 0.15s; }}
[data-testid="column"]:nth-child(4) [data-testid="metric-container"] {{ animation-delay: 0.20s; }}
[data-testid="column"]:nth-child(5) [data-testid="metric-container"] {{ animation-delay: 0.25s; }}
</style>

<script>
(function() {{
    // Clear raw "_arrow_right" / "_arrow_drop_down" text nodes injected by Streamlit
    // when the icon font isn't loaded. CSS ::before chevron handles visual indicator.
    function fixArrows() {{
        document.querySelectorAll(
            '[data-testid="stExpander"] details > summary'
        ).forEach(function(summary) {{
            var walker = document.createTreeWalker(
                summary, NodeFilter.SHOW_TEXT, null, false
            );
            var node;
            while ((node = walker.nextNode())) {{
                if (/_?arrow_/.test(node.textContent)) {{
                    node.textContent = '';
                }}
            }}
        }});
    }}

    fixArrows();
    window.addEventListener('load', fixArrows);
    [300, 800, 1500, 3000].forEach(function(ms) {{
        setTimeout(fixArrows, ms);
    }});
    var mo = new MutationObserver(function() {{ fixArrows(); }});
    document.addEventListener('DOMContentLoaded', function() {{
        mo.observe(document.body, {{ childList: true, subtree: true }});
    }});
}})();
</script>
"""
