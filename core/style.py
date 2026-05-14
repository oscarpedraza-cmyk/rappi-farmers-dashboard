"""
core/style.py — Shared Rappi Business design system CSS.
Call inject_global_css() once per page, right after set_page_config().
"""

def inject_global_css() -> str:
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Base ── */
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

/* ── Page background ── */
.main .block-container {
    background: #F4F5F7 !important;
    padding-top: 1.5rem !important;
}

/* ── Hide Streamlit default menu & footer ── */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }

/* ── Sidebar — Rappi red ── */
[data-testid="stSidebar"] > div:first-child {
    background: #E8281F !important;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span { color: white !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: white !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.2) !important; }

/* Sidebar section labels */
[data-testid="stSidebar"] .sidebar-section-label {
    color: rgba(255,255,255,0.6) !important;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Sidebar inputs — slightly darker red */
[data-testid="stSidebar"] .stNumberInput input,
[data-testid="stSidebar"] .stTextInput input,
[data-testid="stSidebar"] .stSelectbox select {
    background: #C62419 !important;
    color: white !important;
    border-color: rgba(255,255,255,0.3) !important;
}
[data-testid="stSidebar"] .stMetric {
    background: rgba(0,0,0,0.12);
    border-radius: 8px;
    padding: 8px;
}
[data-testid="stSidebar"] .stMetric label { color: rgba(255,255,255,0.7) !important; }
[data-testid="stSidebar"] .stMetric [data-testid="metric-container"] > div { color: white !important; }

/* ── Native Streamlit metrics — white card ── */
[data-testid="metric-container"] {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 12px !important;
    padding: 1rem 1.2rem !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
}

/* ── Buttons ── */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
}
.stButton > button[kind="primary"],
.stButton > button {
    background: #E8281F !important;
    border-color: #E8281F !important;
    color: white !important;
}
.stButton > button:hover {
    background: #C62419 !important;
    border-color: #C62419 !important;
    box-shadow: 0 4px 12px rgba(232,40,31,0.35) !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: #FFFFFF !important;
    border: 2px dashed #E8281F !important;
    border-radius: 12px !important;
    padding: 0.5rem !important;
}

/* ── Tabs ── */
[data-testid="stTab"] { font-weight: 600 !important; }
[data-testid="stTab"][aria-selected="true"] {
    border-bottom: 2px solid #E8281F !important;
    color: #E8281F !important;
}

/* ── Dataframe / table ── */
[data-testid="stDataFrame"] thead tr {
    background: #F9FAFB !important;
}
[data-testid="stDataFrame"] tbody tr {
    border-bottom: 1px solid #F3F4F6 !important;
}

/* ── Card classes ── */

/* Generic white card */
.rb-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    margin-bottom: 0.8rem;
}

/* KPI metric card */
.rb-metric {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    text-align: center;
}
.rb-metric .rb-metric-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #6B7280;
    margin-bottom: 4px;
}
.rb-metric .rb-metric-value {
    font-size: 2rem;
    font-weight: 800;
    color: #1A1A1A;
    line-height: 1.1;
}
.rb-metric .rb-metric-sub {
    font-size: 0.78rem;
    color: #9CA3AF;
    margin-top: 4px;
}

/* Section title */
.rb-section-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #374151;
    margin: 1rem 0 0.5rem;
}

/* Page header card */
.rb-page-header {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-left: 4px solid #E8281F;
    border-radius: 12px;
    padding: 1.2rem 1.6rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    margin-bottom: 1.2rem;
}
.rb-page-header h1 {
    margin: 0;
    font-size: 1.6rem;
    font-weight: 700;
    color: #1A1A1A;
}
.rb-page-header p {
    margin: 0.2rem 0 0;
    font-size: 0.85rem;
    color: #6B7280;
}

/* Caption */
.rb-caption {
    font-size: 0.78rem;
    color: #9CA3AF;
}

/* Semaphore hover table row */
.semaforo-table tr:hover td { background: #F9FAFB !important; }
.semaforo-table { border-radius: 10px; overflow: hidden; }

/* Info/update banner */
.last-update-banner {
    background: #FFFFFF;
    border-left: 4px solid #E8281F;
    border-radius: 0 8px 8px 0;
    padding: 0.6rem 1rem;
    margin-bottom: 1rem;
    font-size: 0.85rem;
    color: #374151;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
</style>
"""
