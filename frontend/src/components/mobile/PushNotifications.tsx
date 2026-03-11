import React, { useState, useEffect } from 'react';
import './PushNotifications.css';

type PermissionState = 'default' | 'granted' | 'denied';

function getInitialPermission(): PermissionState {
  if (!('Notification' in window)) return 'denied';
  return Notification.permission as PermissionState;
}

export const PushNotifications: React.FC = () => {
  const [permission, setPermission] = useState<PermissionState>(getInitialPermission);
  const [showBanner, setShowBanner] = useState(false);

  useEffect(() => {
    if (permission !== 'default') return;
    const timer = setTimeout(() => setShowBanner(true), 5000);
    return () => clearTimeout(timer);
  }, [permission]);

  const requestPermission = async () => {
    try {
      const result = await Notification.requestPermission();
      setPermission(result);
      setShowBanner(false);
      if (result === 'granted') {
        await subscribeToNotifications();
      }
    } catch (err) {
      console.error('Failed to request notification permission:', err);
    }
  };

  const subscribeToNotifications = async () => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
    try {
      const registration = await navigator.serviceWorker.ready;
      const vapidPublicKey = import.meta.env.VITE_VAPID_PUBLIC_KEY;
      if (!vapidPublicKey) {
        console.warn('Push notifications: VITE_VAPID_PUBLIC_KEY is not configured');
        return;
      }

      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        // Pass as string — PushManager accepts a base64url-encoded VAPID public key string
        applicationServerKey: vapidPublicKey,
      });

      await fetch('/api/v1/notifications/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(subscription),
      });
    } catch (err) {
      console.error('Failed to subscribe to push notifications:', err);
    }
  };

  if (!showBanner || permission !== 'default') return null;

  return (
    <div className="push-banner" role="alert">
      <span className="push-banner__icon" aria-hidden="true">🔔</span>
      <div className="push-banner__text">
        <strong>Stay informed</strong>
        <p>Enable notifications for investigation updates</p>
      </div>
      <div className="push-banner__actions">
        <button className="push-banner__btn push-banner__btn--accept" onClick={requestPermission}>
          Allow
        </button>
        <button
          className="push-banner__btn push-banner__btn--deny"
          onClick={() => setShowBanner(false)}
        >
          Not now
        </button>
      </div>
    </div>
  );
};
