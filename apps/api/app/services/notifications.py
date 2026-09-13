"""Multi-channel notification dispatch (email/WhatsApp/push), honoring each
user's `notification_prefs`. Each channel sender is isolated so a provider
swap (e.g. SES -> SendGrid) touches one function."""
from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.alert import Alert
from app.models.user import User

logger = get_logger(__name__)


async def send_email(*, to_email: str, subject: str, body: str) -> bool:
    import boto3

    settings = get_settings()
    try:
        client = boto3.client("ses", region_name=settings.aws_region)
        client.send_email(
            Source=settings.ses_from_email,
            Destination={"ToAddresses": [to_email]},
            Message={"Subject": {"Data": subject}, "Body": {"Text": {"Data": body}}},
        )
        return True
    except Exception:
        logger.exception("email_send_failed", to_email=to_email)
        return False


async def send_whatsapp(*, to_phone: str, message: str) -> bool:
    settings = get_settings()
    token = settings.whatsapp_business_api_token
    if not token:
        logger.warning("whatsapp_not_configured")
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://graph.facebook.com/v19.0/me/messages",
                headers={"Authorization": f"Bearer {token}"},
                json={"to": to_phone, "type": "text", "text": {"body": message}},
            )
            response.raise_for_status()
        return True
    except Exception:
        logger.exception("whatsapp_send_failed", to_phone=to_phone)
        return False


async def send_push(*, device_token: str, title: str, body: str) -> bool:
    settings = get_settings()
    server_key = settings.fcm_server_key
    if not server_key:
        logger.warning("push_not_configured")
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://fcm.googleapis.com/fcm/send",
                headers={"Authorization": f"key={server_key}"},
                json={"to": device_token, "notification": {"title": title, "body": body}},
            )
            response.raise_for_status()
        return True
    except Exception:
        logger.exception("push_send_failed")
        return False


async def dispatch_alert(*, alert: Alert, user: User) -> dict:
    """Sends `alert` through every channel the user has opted into, based
    on `user.notification_prefs` (`{email, whatsapp, push}` booleans).
    Returns a `{channel: bool_sent}` dict for `alert.channels_sent`."""
    prefs = user.notification_prefs or {}
    sent: dict[str, bool] = {}

    if prefs.get("email", True):
        sent["email"] = await send_email(to_email=user.email, subject=alert.title, body=alert.body)
    if prefs.get("whatsapp", False):
        phone = prefs.get("phone_number")
        sent["whatsapp"] = await send_whatsapp(to_phone=phone, message=alert.body) if phone else False
    if prefs.get("push", True):
        device_token = prefs.get("device_token")
        sent["push"] = (
            await send_push(device_token=device_token, title=alert.title, body=alert.body)
            if device_token
            else False
        )
    return sent
