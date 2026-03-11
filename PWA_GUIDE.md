# PWA Guide – OSINT Platform

This guide explains how to install and use the OSINT Platform as a Progressive Web App (PWA) on any device.

## What is the PWA?

The OSINT Platform PWA provides a native app-like experience directly from your browser—no app store required. Once installed it:

- Launches from your home screen or taskbar
- Works **offline** with cached data
- Receives **push notifications** for investigation updates
- Uses **background sync** to queue actions when offline

---

## Installation

### Android

1. Open the OSINT Platform URL in **Chrome**.
2. Tap the **"Install OSINT Platform"** banner that appears at the bottom of the screen.  
   _Alternatively: tap the ⋮ menu → "Add to Home Screen"._
3. Tap **Install** in the confirmation dialog.
4. The app icon appears on your home screen. Tap it to launch.

### iOS (Safari)

1. Open the OSINT Platform URL in **Safari**.
2. Tap the **Share** button (⬆️ at the bottom of the screen).
3. Scroll down and tap **"Add to Home Screen"**.
4. Tap **Add** (top-right).
5. The app icon appears on your home screen.

> **Note:** iOS requires Safari. Chrome and Firefox on iOS do not support PWA installation.

### Desktop (Chrome / Edge)

1. Open the OSINT Platform URL in **Chrome** or **Edge**.
2. Click the **Install** icon (⊕) in the address bar, **or** click the **"Install OSINT Platform"** banner.
3. Click **Install** in the confirmation dialog.
4. The app opens as a standalone window and a shortcut is added to your taskbar/dock.

### Desktop (Firefox)

Firefox supports PWA installation through extensions. Alternatively, bookmark the URL and open it normally; full PWA install is not natively supported in desktop Firefox.

---

## Updating the App

The PWA auto-updates in the background. When a new version is available you will see a prompt asking to reload—tap **Reload** to apply the update immediately, or it will be applied the next time you launch the app.

---

## Offline Usage

When you are offline, the app:

- Serves previously cached pages and static assets instantly.
- Displays cached entities and cases.
- Queues new searches/actions in the local **sync queue** (IndexedDB).
- Automatically syncs queued actions when connectivity is restored via Background Sync.

See [OFFLINE_MODE.md](./OFFLINE_MODE.md) for details.

---

## Push Notifications

Push notifications are sent for:

| Event | Description |
|---|---|
| Investigation update | New entity or relationship found |
| Data ingestion | Source processing completed |
| Export ready | Report download available |
| Correlation discovered | New entity link identified |
| Threat intel alert | Cyber OSINT alert triggered |
| Background sync | Offline queue processed |

To enable notifications, click **Allow** when prompted, or visit **Settings** and enable notifications there.

---

## Shortcuts

When installed, the following app shortcuts are available (long-press the icon on Android/iOS):

| Shortcut | Destination |
|---|---|
| Dashboard | `/dashboard` |
| New Investigation | `/modules/investigation/new` |
| Digital Footprint Scan | `/modules/digital-footprint` |
| Cyber OSINT | `/modules/cyber-osint` |

---

## Share Target

The OSINT Platform registers as a share target on Android and desktop. You can share a URL or text from any app directly into the platform for analysis:

1. In any app, tap **Share**.
2. Select **OSINT Platform** from the share sheet.
3. The shared content is pre-filled in the relevant module.

---

## Lighthouse PWA Score

The platform targets a Lighthouse PWA score of **90+**. To audit:

```bash
# Install Lighthouse CLI
npm install -g lighthouse

# Run audit
lighthouse https://your-osint-platform.com --only-categories=pwa
```
