"""API routes for PWA push notification management."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from notifications.push_notification import broadcast_notification
from notifications.vapid_keys import get_vapid_keys

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"])

# In-memory subscription store.
# ⚠️  LIMITATION: This is a single-process, in-memory store suitable only for
# development and single-worker deployments. In production with multiple workers
# (e.g. Gunicorn/Uvicorn workers), each process maintains its own independent
# subscription list, so subscriptions registered by one worker are invisible to
# others. Replace with a database-backed store (e.g. PostgreSQL table) before
# deploying to production with more than one worker.
_subscriptions: list[dict[str, Any]] = []


# ── Schemas ───────────────────────────────────────────────────────────────────

class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscription(BaseModel):
    endpoint: str
    expiration_time: int | None = Field(None, alias="expirationTime")
    keys: PushSubscriptionKeys

    model_config = {"populate_by_name": True}


class NotificationPayload(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field("", max_length=500)
    icon: str = "/icons/icon-192x192.png"
    badge: str = "/icons/icon-96x96.png"
    data: dict[str, Any] = Field(default_factory=dict)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/vapid-public-key", summary="Get VAPID public key for push subscription")
async def get_vapid_public_key() -> dict[str, str]:
    """Return the VAPID public key needed by the frontend to subscribe."""
    keys = get_vapid_keys()
    public_key = keys.get("public_key", "")
    if not public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Push notifications are not configured on this server.",
        )
    return {"publicKey": public_key}


@router.post("/subscribe", status_code=status.HTTP_201_CREATED, summary="Subscribe to push notifications")
async def subscribe(subscription: PushSubscription) -> dict[str, str]:
    """Register a push subscription endpoint."""
    sub_dict = subscription.model_dump(by_alias=True)
    # Deduplicate by endpoint
    endpoints = {s.get("endpoint") for s in _subscriptions}
    if subscription.endpoint not in endpoints:
        _subscriptions.append(sub_dict)
        logger.info("New push subscription registered: %s", subscription.endpoint[:60])
    return {"status": "subscribed"}


@router.delete("/unsubscribe", summary="Unsubscribe from push notifications")
async def unsubscribe(subscription: PushSubscription) -> dict[str, str]:
    """Remove a push subscription."""
    global _subscriptions  # noqa: PLW0603
    _subscriptions = [s for s in _subscriptions if s.get("endpoint") != subscription.endpoint]
    logger.info("Push subscription removed: %s", subscription.endpoint[:60])
    return {"status": "unsubscribed"}


@router.post("/send", summary="Broadcast a notification to all subscribers (admin)")
async def send_notification(payload: NotificationPayload) -> dict[str, int]:
    """Send a push notification to all registered subscribers."""
    if not _subscriptions:
        return {"sent": 0, "failed": 0}

    keys = get_vapid_keys()
    private_key = keys.get("private_key", "")
    if not private_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Push notifications are not configured on this server.",
        )

    message = payload.model_dump()
    result = await broadcast_notification(
        subscriptions=_subscriptions,
        message=message,
        vapid_private_key=private_key,
    )
    return result
