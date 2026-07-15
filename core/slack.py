from __future__ import annotations
import os
import requests


def _token() -> str | None:
    try:
        import streamlit as st
        return st.secrets.get("SLACK_BOT_TOKEN") or os.environ.get("SLACK_BOT_TOKEN")
    except Exception:
        return os.environ.get("SLACK_BOT_TOKEN")


def send_farmer_report(
    slack_user_id: str,
    farmer_name: str,
    metrics: dict,        # {label: (value_str, color)}  color = "green"|"yellow"|"red"|"gray"
    plan_items: list[str],
    brands_riesgo: list[str],
    semana: str = "",
) -> tuple[bool, str]:
    """
    Sends a formatted DM to a farmer via Slack Bot API.
    Returns (success: bool, message: str).
    """
    token = _token()
    if not token:
        return False, "No hay SLACK_BOT_TOKEN configurado en los secrets."

    _EMOJI = {"green": "🟢", "yellow": "🟡", "red": "🔴", "gray": "⚪"}

    # ── Metrics block ──────────────────────────────────────────────────────────
    metrics_lines = "\n".join(
        f"{_EMOJI.get(color, '⚪')} *{label}:* {value}"
        for label, (value, color) in metrics.items()
    )

    # ── Plan block ─────────────────────────────────────────────────────────────
    plan_text = "\n".join(f"• {item}" for item in plan_items) if plan_items else "Sin acciones pendientes."

    # ── ADS risk block ─────────────────────────────────────────────────────────
    ads_block = ""
    if brands_riesgo:
        ads_names = ", ".join(brands_riesgo[:5])
        extra = f" y {len(brands_riesgo)-5} más" if len(brands_riesgo) > 5 else ""
        ads_block = f"\n\n🚨 *ADS en riesgo (penetración > 70%):* {ads_names}{extra}"

    sem_label = f" — Sem. {semana}" if semana else ""

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📊 Tu Review Semanal{sem_label}", "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"Hola *{farmer_name}* 👋 Acá va tu resumen de métricas:"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📈 Métricas clave*\n{metrics_lines}"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*🎯 Tu plan de esta semana*\n{plan_text}{ads_block}"},
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "Rappi Farmers Dashboard · AR/UY Supervisión Comercial"}],
        },
    ]

    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"channel": slack_user_id, "blocks": blocks, "text": f"Review Semanal — {farmer_name}"},
        timeout=10,
    )

    if not resp.ok:
        return False, f"Error HTTP {resp.status_code}"

    data = resp.json()
    if data.get("ok"):
        return True, "Mensaje enviado correctamente."
    return False, data.get("error", "Error desconocido de Slack API.")
