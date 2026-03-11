import React, { useState, useEffect } from 'react';
import './PushNotifications.css';

type PermissionState = 'default' | 'granted' | 'denied';

export const PushNotifications: React.FC = () => {
  const [permission, setPermission] = useState<PermissionState>('default');
  const [showBanner, setShowBanner] = useState(false);

  useEffect(() => {
    if (!('Notification' in window)) return;
    setPermission(Notification.permission);
    if (Notification.permission === 'default') {
      const timer = setTimeout(() => setShowBanner(true), 5000);
      return () => clearTimeout(timer);
    }
  }, []);

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
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey).buffer as ArrayBuffer,
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

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}
