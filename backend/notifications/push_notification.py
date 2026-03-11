"""Push notification delivery for the OSINT Platform."""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def send_push_notification(
    subscription_info: dict[str, Any],
    message: dict[str, Any],
    vapid_private_key: str,
    vapid_claims: dict[str, str],
) -> bool:
    """
    Send a Web Push notification to a single subscriber.

    Args:
        subscription_info: The push subscription object (endpoint + keys).
        message: Notification payload dict (title, body, icon, data …).
        vapid_private_key: Base64url-encoded VAPID private key.
        vapid_claims: VAPID claims dict, e.g. ``{"sub": "mailto:admin@example.com"}``.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    try:
        from pywebpush import webpush, WebPushException  # type: ignore[import-untyped]
    except ImportError:
        logger.warning(
            "pywebpush is not installed. Push notifications are unavailable. "
            "Install it with: pip install pywebpush"
        )
        return False

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(message),
            vapid_private_key=vapid_private_key,
            vapid_claims=vapid_claims,
        )
        logger.info("Push notification sent to %s", subscription_info.get("endpoint", "unknown"))
        return True
    except Exception as exc:  # WebPushException or any network error
        logger.error("Push notification failed: %s", exc)
        return False


async def broadcast_notification(
    subscriptions: list[dict[str, Any]],
    message: dict[str, Any],
    vapid_private_key: str,
    vapid_subject: str = "mailto:admin@osint-platform.com",
) -> dict[str, int]:
    """
    Send a push notification to multiple subscribers.

    Returns a dict with ``sent`` and ``failed`` counts.
    """
    vapid_claims = {"sub": vapid_subject}
    sent = 0
    failed = 0

    for subscription in subscriptions:
        success = send_push_notification(
            subscription_info=subscription,
            message=message,
            vapid_private_key=vapid_private_key,
            vapid_claims=vapid_claims,
        )
        if success:
            sent += 1
        else:
            failed += 1

    return {"sent": sent, "failed": failed}
