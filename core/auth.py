"""
Authentication & authorization for Rappi Farmers Dashboard.

Flow:
  1. User enters @rappi.com email → validated against allowed list
  2. If supervisor email → additional PIN required (from st.secrets or default)
  3. Session state stores auth info → persists during the session
  4. Every page calls require_auth() at top → redirects to login if needed

Roles:
  - supervisor (oscar.pedraza@rappi.com) → can upload Sheet Maestro, sees admin panel
  - farmer (everyone in FARMERS_EMAILS) → read-only view of latest saved state
"""
import streamlit as st
from core.loader import FARMERS_EMAILS, EXCLUDED_EMAILS, FARMER_NAMES

SUPERVISOR_EMAIL = "oscar.pedraza@rappi.com"
SUPERVISOR_NAME  = "Oscar Pedraza"

def _logo_html(width: int = 120) -> str:
    """Returns an <img> tag with the Rappi logo embedded as base64, or a text fallback."""
    import base64
    from pathlib import Path
    logo_path = Path(__file__).parent.parent / "assets" / "rappi_logo.png"
    if logo_path.exists():
        b64 = base64.b64encode(logo_path.read_bytes()).decode()
        return f'<img src="data:image/png;base64,{b64}" width="{width}" style="display:block;margin:0 auto 0.8rem">'
    return '<div style="font-size:1.8rem;font-weight:900;color:#E8281F;text-align:center;margin-bottom:0.8rem">rappi</div>'


def _allowed_emails() -> set:
    return (set(FARMERS_EMAILS) - EXCLUDED_EMAILS) | {SUPERVISOR_EMAIL}


def _supervisor_pin() -> str:
    try:
        return st.secrets["SUPERVISOR_PIN"]
    except Exception:
        return "Rappi2026"   # Oscar debe cambiar esto en Streamlit Cloud → Settings → Secrets


# ── Login page ────────────────────────────────────────────────────────────────
def render_login():
    """Renders the Rappi-branded login page. Call before st.stop()."""

    # Hide sidebar and toolbar on login screen
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    header[data-testid="stHeader"] { background: transparent; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .block-container { padding-top: 2rem !important; }
    </style>
    """, unsafe_allow_html=True)

    # Center login card
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown(_logo_html(130), unsafe_allow_html=True)
        st.markdown("""
        <div style="
            background: #FFFFFF;
            border-radius: 16px;
            padding: 2rem 2.2rem;
            box-shadow: 0 4px 24px rgba(0,0,0,0.10);
            border: 1px solid #F0F0F0;
            margin-top: 0.5rem;
        ">
            <h2 style="margin:0 0 0.3rem;font-size:1.4rem;color:#1A1A1A;font-weight:700">
                Dashboard de Farmers 🚀
            </h2>
            <p style="margin:0 0 1.5rem;color:#666;font-size:0.88rem">
                Supervisión comercial · Equipo AR/UY
            </p>
        """, unsafe_allow_html=True)

        # ── Pending supervisor PIN flow ────────────────────────────────────────
        if st.session_state.get("_auth_step") == "pin":
            pending = st.session_state.get("_auth_pending_email", "")
            st.markdown(f'<p style="color:#555;font-size:0.85rem">Supervisor detectado: <b>{pending}</b></p>',
                        unsafe_allow_html=True)
            pin = st.text_input("🔒 PIN de supervisor", type="password",
                                placeholder="Ingresa tu PIN",
                                key="pin_input")
            c1, c2 = st.columns(2)
            if c1.button("✅ Confirmar", use_container_width=True, type="primary"):
                if pin == _supervisor_pin():
                    _set_auth(pending, is_supervisor=True)
                    st.session_state.pop("_auth_step", None)
                    st.session_state.pop("_auth_pending_email", None)
                    st.rerun()
                else:
                    st.error("PIN incorrecto. Intenta nuevamente.")
            if c2.button("← Volver", use_container_width=True):
                st.session_state.pop("_auth_step", None)
                st.session_state.pop("_auth_pending_email", None)
                st.rerun()

        # ── Email login flow ───────────────────────────────────────────────────
        else:
            email_raw = st.text_input(
                "📧 Tu correo @rappi.com",
                placeholder="nombre.apellido@rappi.com",
                key="login_email"
            )
            if st.button("Ingresar →", use_container_width=True, type="primary"):
                _handle_login(email_raw)

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("""
        <p style="text-align:center;color:#AAA;font-size:0.75rem;margin-top:1rem">
            Solo accesible con correos autorizados del equipo Rappi AR/UY
        </p>
        """, unsafe_allow_html=True)


def _handle_login(email_raw: str):
    email = email_raw.strip().lower()

    if not email:
        st.warning("Ingresa tu correo.")
        return

    if not email.endswith("@rappi.com"):
        st.error("❌ Solo se permiten correos @rappi.com.")
        return

    allowed = _allowed_emails()
    if email not in allowed:
        st.error("❌ Tu correo no está habilitado para acceder al dashboard. Contacta a tu supervisor.")
        return

    if email == SUPERVISOR_EMAIL:
        st.session_state["_auth_step"] = "pin"
        st.session_state["_auth_pending_email"] = email
        st.rerun()
    else:
        _set_auth(email, is_supervisor=False)
        st.rerun()


def _set_auth(email: str, is_supervisor: bool):
    name = FARMER_NAMES.get(email, email.split("@")[0].replace(".", " ").title())
    if email == SUPERVISOR_EMAIL:
        name = SUPERVISOR_NAME
    st.session_state["auth_email"]         = email
    st.session_state["auth_is_supervisor"] = is_supervisor
    st.session_state["auth_name"]          = name


# ── Auth gate (call at top of every page) ─────────────────────────────────────
def require_auth() -> tuple[str, bool]:
    """
    Returns (email, is_supervisor). Shows login page and stops if not authenticated.
    Place this at the very top of every Streamlit page/app.
    """
    if "auth_email" not in st.session_state:
        render_login()
        st.stop()

    email        = st.session_state["auth_email"]
    is_supervisor = st.session_state.get("auth_is_supervisor", False)

    # Re-validate (in case allowed list changed)
    if email not in _allowed_emails():
        _clear_auth()
        render_login()
        st.stop()

    return email, is_supervisor


def get_auth_name() -> str:
    return st.session_state.get("auth_name", "Usuario")


def _clear_auth():
    for k in ["auth_email", "auth_is_supervisor", "auth_name",
              "_auth_step", "_auth_pending_email"]:
        st.session_state.pop(k, None)


def render_sidebar_user_badge():
    """Renders the logged-in user chip at the top of the sidebar (legacy — kept for compat)."""
    email  = st.session_state.get("auth_email", "")
    name   = get_auth_name()
    is_sup = st.session_state.get("auth_is_supervisor", False)
    role   = "🔑 Supervisor" if is_sup else "👤 Farmer"

    st.sidebar.markdown(f"""
    <div style="background:rgba(255,255,255,0.08);border-radius:10px;
                padding:0.7rem 0.9rem;margin-bottom:0.5rem;
                border-left:3px solid rgba(255,255,255,0.4)">
        <div style="font-size:0.68rem;color:rgba(255,255,255,0.55);margin-bottom:2px">{role}</div>
        <div style="font-weight:700;color:white;font-size:0.9rem">{name}</div>
        <div style="font-size:0.68rem;color:rgba(255,255,255,0.5)">{email}</div>
    </div>
    """, unsafe_allow_html=True)

    if st.sidebar.button("Cerrar sesión", use_container_width=True, key="logout_btn"):
        _clear_auth()
        st.rerun()


def render_topbar(updated_at: str = "", dia_corte: int = None, progreso_pct: float = None):
    """
    Renders the top navigation bar in the main content area.
    Shows: logo + brand | user info | meta chips (date, progress).
    Logout button rendered via Streamlit columns so it actually works.
    """
    import base64
    from pathlib import Path
    from datetime import date

    name   = get_auth_name()
    email  = st.session_state.get("auth_email", "")
    is_sup = st.session_state.get("auth_is_supervisor", False)
    role   = "Supervisor" if is_sup else "Farmer"
    role_icon = "🔑" if is_sup else "👤"
    today_str = date.today().strftime("%d %b %Y")

    # Logo
    logo_path = Path(__file__).parent.parent / "assets" / "rappi_logo.png"
    if logo_path.exists():
        b64 = base64.b64encode(logo_path.read_bytes()).decode()
        logo_html = f'<img src="data:image/png;base64,{b64}" height="28" style="display:block">'
    else:
        logo_html = '<span style="font-size:1.2rem;font-weight:900;color:#E8281F">rappi</span>'

    # Meta chips
    chips_html = f'<span class="rb-meta-chip">📅 {today_str}</span>'
    if updated_at:
        chips_html += f'<span class="rb-meta-chip" style="margin-left:6px">🔄 {updated_at}</span>'
    if progreso_pct is not None:
        chips_html += (f'<span class="rb-meta-chip" style="margin-left:6px">'
                       f'📊 Corte día {dia_corte} · {progreso_pct:.0f}% del mes</span>')

    col_bar, col_btn = st.columns([12, 1])
    with col_bar:
        st.markdown(f"""
        <div class="rb-topbar">
            <div class="rb-topbar-brand">
                {logo_html}
                <div>
                    <div class="brand-name">Rappi <span>Farmers</span></div>
                    <div style="font-size:0.65rem;color:rgba(255,255,255,0.4);
                                margin-top:1px;letter-spacing:0.3px">Dashboard AR / UY</div>
                </div>
            </div>
            <div style="display:flex;align-items:center;gap:10px">
                {chips_html}
                <div class="rb-user-badge">
                    <div class="rb-status-dot"></div>
                    <div>
                        <div class="user-name">{role_icon} {name}</div>
                        <div class="user-role">{role} · {email.split('@')[0]}</div>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col_btn:
        st.markdown("<div style='margin-top:0.3rem'>", unsafe_allow_html=True)
        if st.button("⏏", help="Cerrar sesión", key="topbar_logout"):
            _clear_auth()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
