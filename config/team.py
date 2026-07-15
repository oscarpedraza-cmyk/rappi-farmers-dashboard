"""Team roster and identity configuration.

Single source of truth for who is on the team, their display names and Slack
IDs, and the supervisor identity. These are internal, non-secret identifiers
(actual secrets — Google credentials, the supervisor PIN — live in environment
variables / Streamlit secrets, never here).
"""
from __future__ import annotations

# ── Supervisor identity ───────────────────────────────────────────────────────
SUPERVISOR_EMAIL: str = "oscar.pedraza@rappi.com"
SUPERVISOR_NAME: str = "Oscar Pedraza"

# ── Active farmer roster ──────────────────────────────────────────────────────
FARMERS_EMAILS: list[str] = [
    "maira.franco@rappi.com",
    "micheel.espitia@rappi.com",
    "arnold.camino@rappi.com",
    "lady.bobativa@rappi.com",
    "fanny.landazabal@rappi.com",
    "claudia.pineda@rappi.com",
    "esteban.castano@rappi.com",
    "luisfernando.hernandez@rappi.com",
    "alejandro.salamanca@rappi.com",
    "angie.contreras@rappi.com",
    "diana.saavedra@rappi.com",
    "maria.pedraza@rappi.com",
    "sabas.ramirez@rappi.com",
]

# Farmers excluidos (renuncia, licencia, etc.) — no aparecen en el dashboard.
EXCLUDED_EMAILS: set[str] = {
    "vanesa.fernandez@rappi.com",   # renuncia voluntaria mayo 2026
    "luis.ibarra@rappi.com",        # salida julio 2026
}

FARMER_NAMES: dict[str, str] = {
    "maira.franco@rappi.com": "Maira Franco",
    "micheel.espitia@rappi.com": "Micheel Espitia",
    "arnold.camino@rappi.com": "Arnold Camino",
    "lady.bobativa@rappi.com": "Lady Bobativa",
    "fanny.landazabal@rappi.com": "Fanny Landazabal",
    "claudia.pineda@rappi.com": "Claudia Pineda",
    "esteban.castano@rappi.com": "Esteban Castaño",
    "luisfernando.hernandez@rappi.com": "Luis Fernando Hernández",
    "alejandro.salamanca@rappi.com": "Alejandro Salamanca",
    "angie.contreras@rappi.com": "Angie Contreras",
    "diana.saavedra@rappi.com": "Diana Saavedra",
    "maria.pedraza@rappi.com": "Maria Pedraza",
    "sabas.ramirez@rappi.com": "Sabas Ramirez",
}

SLACK_IDS: dict[str, str] = {
    "oscar.pedraza@rappi.com": "U09BXG9V64V",
    "maira.franco@rappi.com": "U0A2GM2TXTQ",
    "micheel.espitia@rappi.com": "U04KTCXR4SC",
    "arnold.camino@rappi.com": "U099GE8J2F9",
    "lady.bobativa@rappi.com": "U06JFH95KPD",
    "fanny.landazabal@rappi.com": "U09KHT8737C",
    "claudia.pineda@rappi.com": "U0A1PTFBB0B",
    "esteban.castano@rappi.com": "U09488QUV19",
    "luisfernando.hernandez@rappi.com": "UMEALSBS7",
    "alejandro.salamanca@rappi.com": "U095P47BZ5X",
    "angie.contreras@rappi.com": "U08H6NS5J2C",
    "diana.saavedra@rappi.com": "U0AAUHTG9DH",
    "maria.pedraza@rappi.com": "U09TT5M0CR2",
    "vanesa.fernandez@rappi.com": "U0AR2626PAA",
}
