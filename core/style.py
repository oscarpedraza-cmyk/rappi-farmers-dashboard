"""
core/style.py — Rappi Farmers Design System
Sidebar → top bar layout. Call inject_global_css() once per page.
"""

# ── Design tokens ─────────────────────────────────────────────────────────────
BG_PAGE    = "#EBF0F8"   # page background — contrasts white cards
BG_CARD    = "#FFFFFF"   # card / chart surface
BG_NAV     = "#1C2340"   # top navbar (dark navy)
BG_SIDEBAR = "#1C2340"   # sidebar nav (same dark navy)
C_RED      = "#E8281F"   # Rappi red — primary accent
C_GREEN    = "#059669"   # success
C_AMBER    = "#D97706"   # warning
C_BLUE     = "#2563EB"   # info
C_TEXT     = "#0F172A"   # primary text
C_MUTED    = "#64748B"   # secondary text
C_BORDER   = "#E2E8F0"   # card borders


def inject_global_css() -> str:
    return f"""
<style>
/* ── Fonts ──────────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20,400,0,0&family=Inter:wght@400;500;600;700;800;900&display=swap');

/* Activate Material Symbols so Streamlit's expander arrows render as icons */
.material-symbols-rounded {{
    font-family: 'Material Symbols Rounded' !important;
    font-weight: normal !important;
    font-style: normal !important;
    font-size: 1.1em !important;
    line-height: 1;
    letter-spacing: normal;
    text-transform: none;
    display: inline-block;
    white-space: nowrap;
    -webkit-font-feature-settings: 'liga';
    font-feature-settings: 'liga';
    -webkit-font-smoothing: antialiased;
    vertical-align: middle;
}}
html, body, [class*="css"], [class*="st-"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    font-size: 15px;
    color: {C_TEXT};
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

/* ── Hide Streamlit chrome ────────────────────────────────────────────────── */
#MainMenu {{ visibility: hidden; }}
footer    {{ visibility: hidden; }}
header    {{ visibility: hidden; }}

/* ── Hide sidebar collapse/expand toggle button ──────────────────────────── */
[data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}
[data-testid="collapsedControl"]          {{ display: none !important; }}
section[data-testid="stSidebar"][aria-expanded="false"] + div .main
    .block-container {{ padding-left: 1.8rem !important; }}

/* ── Sidebar — dark navy ─────────────────────────────────────────────────── */
[data-testid="stSidebar"] > div:first-child {{
    background: {BG_SIDEBAR} !important;
    border-right: 1px solid rgba(255,255,255,0.06);
}}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span {{ color: rgba(255,255,255,0.85) !important; }}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{ color: #FFFFFF !important; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,0.12) !important; }}
[data-testid="stSidebar"] .stButton > button {{
    background: rgba(255,255,255,0.10) !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.20) !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background: rgba(255,255,255,0.18) !important;
}}

/* Nav links in sidebar */
[data-testid="stSidebarNav"] a {{
    color: rgba(255,255,255,0.75) !important;
    border-radius: 8px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    padding: 0.45rem 0.9rem !important;
    transition: background 0.15s;
}}
[data-testid="stSidebarNav"] a:hover {{
    background: rgba(255,255,255,0.10) !important;
    color: #FFFFFF !important;
}}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: {C_RED} !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
}}
[data-testid="stSidebarNav"] svg {{ display: none; }}

/* ── Top navbar (rendered via HTML) ─────────────────────────────────────── */
.rb-topbar {{
    background: {BG_NAV};
    border-radius: 14px;
    padding: 0.85rem 1.4rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.2rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}}
.rb-topbar-brand {{
    display: flex;
    align-items: center;
    gap: 10px;
}}
.rb-topbar-brand .brand-name {{
    font-size: 1.05rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: -0.3px;
}}
.rb-topbar-brand .brand-name span {{ color: {C_RED}; }}
.rb-topbar-right {{
    display: flex;
    align-items: center;
    gap: 14px;
}}
.rb-user-badge {{
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 10px;
    padding: 0.45rem 0.9rem;
}}
.rb-user-badge .user-name {{
    font-size: 0.88rem;
    font-weight: 700;
    color: #FFFFFF;
}}
.rb-user-badge .user-role {{
    font-size: 0.7rem;
    color: rgba(255,255,255,0.55);
    margin-top: 1px;
}}
.rb-status-dot {{
    width: 8px; height: 8px;
    background: {C_GREEN};
    border-radius: 50%;
    box-shadow: 0 0 0 2px rgba(5,150,105,0.3);
}}
.rb-meta-chip {{
    font-size: 0.72rem;
    color: rgba(255,255,255,0.5);
    background: rgba(255,255,255,0.06);
    border-radius: 6px;
    padding: 3px 8px;
}}

/* ── Cards ─────────────────────────────────────────────────────────────── */
.rb-card {{
    background: {BG_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 14px;
    padding: 1.3rem 1.5rem;
    box-shadow: 0 4px 16px rgba(15,23,42,0.07);
    margin-bottom: 0.9rem;
}}

/* KPI metric card */
.rb-metric {{
    background: {BG_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 14px;
    padding: 1.1rem 1.2rem;
    box-shadow: 0 4px 16px rgba(15,23,42,0.07);
    text-align: center;
}}
.rb-metric .rb-metric-label {{
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    color: {C_MUTED};
    margin-bottom: 5px;
}}
.rb-metric .rb-metric-value {{
    font-size: 2rem;
    font-weight: 800;
    color: {C_TEXT};
    line-height: 1.1;
}}
.rb-metric .rb-metric-sub {{
    font-size: 0.77rem;
    color: {C_MUTED};
    margin-top: 4px;
}}

/* Section title */
.rb-section-title {{
    font-size: 1.05rem;
    font-weight: 700;
    color: {C_TEXT};
    margin: 1.2rem 0 0.6rem;
    letter-spacing: -0.2px;
}}

/* Page header */
.rb-page-header {{
    background: {BG_CARD};
    border: 1px solid {C_BORDER};
    border-left: 5px solid {C_RED};
    border-radius: 14px;
    padding: 1.1rem 1.5rem;
    box-shadow: 0 4px 16px rgba(15,23,42,0.07);
    margin-bottom: 1.2rem;
}}
.rb-page-header h1 {{
    margin: 0;
    font-size: 1.45rem;
    font-weight: 800;
    color: {C_TEXT};
    letter-spacing: -0.4px;
}}
.rb-page-header p {{
    margin: 0.2rem 0 0;
    font-size: 0.84rem;
    color: {C_MUTED};
}}

/* Caption */
.rb-caption {{ font-size: 0.77rem; color: {C_MUTED}; }}

/* Upload expander section */
.rb-upload-section {{
    background: {BG_CARD};
    border: 1px solid {C_BORDER};
    border-top: 4px solid {C_RED};
    border-radius: 14px;
    padding: 1.2rem 1.5rem;
    box-shadow: 0 4px 16px rgba(15,23,42,0.07);
    margin-bottom: 1.2rem;
}}

/* ── Semáforo table ─────────────────────────────────────────────────────── */
.semaforo-table tr:hover td {{ background: #F8FAFC !important; }}
.semaforo-table {{ border-radius: 12px; overflow: hidden; }}

/* ── Last update banner ─────────────────────────────────────────────────── */
.last-update-banner {{
    background: {BG_CARD};
    border-left: 4px solid {C_RED};
    border-radius: 0 10px 10px 0;
    padding: 0.6rem 1rem;
    margin-bottom: 1rem;
    font-size: 0.84rem;
    color: {C_TEXT};
    box-shadow: 0 2px 8px rgba(15,23,42,0.05);
}}

/* ── Native Streamlit metrics — white card ──────────────────────────────── */
[data-testid="metric-container"] {{
    background: {BG_CARD} !important;
    border: 1px solid {C_BORDER} !important;
    border-radius: 14px !important;
    padding: 1rem 1.2rem !important;
    box-shadow: 0 4px 16px rgba(15,23,42,0.07) !important;
}}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
.stButton > button {{
    border-radius: 9px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    transition: all 0.18s !important;
}}
.stButton > button[kind="primary"],
.stButton > button {{
    background: {C_RED} !important;
    border-color: {C_RED} !important;
    color: white !important;
}}
.stButton > button:hover {{
    background: #C62419 !important;
    border-color: #C62419 !important;
    box-shadow: 0 4px 14px rgba(232,40,31,0.35) !important;
    transform: translateY(-1px);
}}

/* ── File uploader ────────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {{
    background: #FFF8F8 !important;
    border: 2px dashed {C_RED} !important;
    border-radius: 12px !important;
    padding: 0.5rem !important;
}}
/* Fix overlapping "uploadUpload" duplicate text on the button */
[data-testid="stFileUploaderDropzone"] button span:first-child {{
    display: none !important;
}}
[data-testid="stFileUploaderDropzone"] button {{
    min-width: 90px !important;
}}
/* Hide the redundant small-print label that duplicates the button text */
[data-testid="stFileUploaderDropzoneInstructions"] > div > span:last-child {{
    display: none !important;
}}

/* ── Tabs ────────────────────────────────────────────────────────────────── */
[data-testid="stTab"] {{ font-weight: 600 !important; font-size: 0.88rem !important; }}
[data-testid="stTab"][aria-selected="true"] {{
    border-bottom: 3px solid {C_RED} !important;
    color: {C_RED} !important;
}}

/* ── Dataframe ──────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] thead tr {{ background: #F8FAFC !important; }}
[data-testid="stDataFrame"] tbody tr {{ border-bottom: 1px solid {C_BORDER} !important; }}

/* ── Inputs / selects ────────────────────────────────────────────────────── */
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] > div > div {{
    border-radius: 8px !important;
    border-color: {C_BORDER} !important;
}}
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextInput"] input:focus {{
    border-color: {C_RED} !important;
    box-shadow: 0 0 0 3px rgba(232,40,31,0.12) !important;
}}

/* ── Expander ────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    background: {BG_CARD} !important;
    border: 1px solid {C_BORDER} !important;
    border-radius: 12px !important;
    box-shadow: 0 2px 8px rgba(15,23,42,0.05) !important;
}}
/* Summary layout */
[data-testid="stExpander"] details > summary {{
    list-style: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    padding: 0.55rem 0.8rem;
    border-radius: 10px;
    user-select: none;
    gap: 6px;
}}
[data-testid="stExpander"] details > summary::-webkit-details-marker {{ display: none; }}

/* ── KEY FIX: _arrow_ text appears when Streamlit's icon font isn't loaded.
   Set font-size:0 on the Streamlit icon element (first child of summary) so
   the text disappears regardless of whether the font loads.
   SVG children inside it (if any) are explicitly sized back to visible. ── */
[data-testid="stExpander"] details > summary > :first-child {{
    font-size: 0 !important;
    line-height: 0 !important;
    width: 14px !important;
    min-width: 14px !important;
    height: 14px !important;
    flex-shrink: 0;
    overflow: hidden;
}}
[data-testid="stExpander"] details > summary > :first-child svg {{
    width: 14px !important;
    height: 14px !important;
    display: block;
}}

/* CSS-only chevron so the expander still has a visual indicator */
[data-testid="stExpander"] details > summary::before {{
    content: '';
    display: inline-block;
    width: 5px;
    height: 5px;
    border-right: 1.8px solid {C_MUTED};
    border-bottom: 1.8px solid {C_MUTED};
    transform: rotate(-45deg);
    flex-shrink: 0;
    transition: transform 0.15s ease;
}}
[data-testid="stExpander"] details[open] > summary::before {{
    transform: rotate(45deg);
}}

/* ── Plotly chart container ──────────────────────────────────────────────── */
.js-plotly-plot {{
    background: {BG_CARD} !important;
    border-radius: 12px !important;
}}

/* ── Alerts ─────────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {{
    border-radius: 10px !important;
    font-size: 0.88rem !important;
}}

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {BG_PAGE}; }}
::-webkit-scrollbar-thumb {{ background: #CBD5E1; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: #94A3B8; }}
</style>

<script>
(function() {{
    // Streamlit injects _arrow_right / _arrow_drop_down as raw text nodes inside
    // expander <summary> elements when the icon font is not loaded.
    // This script walks those text nodes and clears them, leaving only the
    // CSS ::before chevron as the visual expand/collapse indicator.
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

    // Run immediately, after load, and watch for dynamic Streamlit re-renders
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
