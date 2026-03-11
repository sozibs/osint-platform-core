"""Tests for push notification infrastructure."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from notifications.push_notification import send_push_notification, broadcast_notification


class TestSendPushNotification:
    def test_returns_false_when_pywebpush_missing(self) -> None:
        """Should gracefully return False when pywebpush is not installed."""
        with patch.dict("sys.modules", {"pywebpush": None}):
            result = send_push_notification(
                subscription_info={"endpoint": "https://example.com/push/abc"},
                message={"title": "Test"},
                vapid_private_key="fake-key",
                vapid_claims={"sub": "mailto:test@example.com"},
            )
        # ImportError branch – function should return False
        assert result is False

    def test_returns_true_on_success(self) -> None:
        """Should return True when webpush() succeeds."""
        mock_webpush = MagicMock(return_value=None)
        mock_module = MagicMock()
        mock_module.webpush = mock_webpush
        mock_module.WebPushException = Exception

        with patch.dict("sys.modules", {"pywebpush": mock_module}):
            result = send_push_notification(
                subscription_info={"endpoint": "https://example.com/push/abc"},
                message={"title": "Alert", "body": "New entity found"},
                vapid_private_key="valid-key",
                vapid_claims={"sub": "mailto:admin@example.com"},
            )

        assert result is True
        mock_webpush.assert_called_once()
        call_kwargs = mock_webpush.call_args.kwargs
        assert call_kwargs["vapid_private_key"] == "valid-key"
        payload = json.loads(call_kwargs["data"])
        assert payload["title"] == "Alert"

    def test_returns_false_on_webpush_exception(self) -> None:
        """Should return False when webpush raises an exception."""
        mock_module = MagicMock()
        mock_module.webpush = MagicMock(side_effect=Exception("Push failed"))
        mock_module.WebPushException = Exception

        with patch.dict("sys.modules", {"pywebpush": mock_module}):
            result = send_push_notification(
                subscription_info={"endpoint": "https://example.com/push/xyz"},
                message={"title": "Test"},
                vapid_private_key="key",
                vapid_claims={"sub": "mailto:admin@example.com"},
            )

        assert result is False


class TestBroadcastNotification:
    @pytest.mark.asyncio
    async def test_empty_subscriptions(self) -> None:
        result = await broadcast_notification(
            subscriptions=[],
            message={"title": "Test"},
            vapid_private_key="key",
        )
        assert result == {"sent": 0, "failed": 0}

    @pytest.mark.asyncio
    async def test_counts_sent_and_failed(self) -> None:
        subscriptions = [
            {"endpoint": "https://example.com/push/1"},
            {"endpoint": "https://example.com/push/2"},
            {"endpoint": "https://example.com/push/3"},
        ]

        call_count = 0

        def fake_send(*args, **kwargs) -> bool:  # noqa: ANN002, ANN003
            nonlocal call_count
            call_count += 1
            # Fail the second subscription
            return call_count != 2

        with patch(
            "notifications.push_notification.send_push_notification",
            side_effect=fake_send,
        ):
            result = await broadcast_notification(
                subscriptions=subscriptions,
                message={"title": "Broadcast"},
                vapid_private_key="key",
            )

        assert result["sent"] == 2
        assert result["failed"] == 1
