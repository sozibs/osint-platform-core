# Offline Mode – OSINT Platform

## How Offline Works

The OSINT Platform uses a **service worker** powered by [Workbox](https://developer.chrome.com/docs/workbox/) to intercept network requests and serve cached responses when offline.

---

## Cache Strategies

| Resource Type | Strategy | TTL |
|---|---|---|
| HTML shell (`index.html`) | Network-first with cache fallback | — |
| Static assets (JS, CSS) | Cache-first (content-hashed, immutable) | 1 year |
| Images / icons | Cache-first | 30 days |
| API responses (`/api/v1/*`) | Network-first, cache fallback | 5 minutes |

---

## Local Storage (IndexedDB)

Offline data is stored in **IndexedDB** via the `offlineStorage` utility:

| Store | Purpose |
|---|---|
| `entities` | Cached entity records |
| `cases` | Cached investigation cases |
| `searches` | Recent search results |
| `sync-queue` | Actions queued while offline |

---

## Offline Queue & Background Sync

When you perform an action while offline (e.g., starting a search, editing an entity), the action is:

1. Stored in the `sync-queue` IndexedDB store.
2. Registered with the **Background Sync API** (`SyncManager.register('sync-queue')`).
3. Automatically retried by the service worker once connectivity is restored.

If the Background Sync API is unavailable (older browsers), queued actions are retried when the app comes back online via the `online` event.

---

## Checking Offline Status

The app displays a red banner at the bottom of the screen when offline:

```
📡 You are offline — showing cached data
```

You can also check programmatically via the `useNetworkStatus` hook:

```ts
import { useNetworkStatus } from './hooks/useNetworkStatus';

const { isOnline, effectiveType } = useNetworkStatus();
```

---

## Clearing the Cache

To clear all cached data and start fresh:

1. Open browser **DevTools** → **Application** → **Storage**.
2. Click **Clear site data**.

Or programmatically:

```ts
import { clearOldCaches } from './utils/cacheManager';
await clearOldCaches();
```

---

## Service Worker Lifecycle

| State | Description |
|---|---|
| Installing | SW being installed (first visit or update) |
| Waiting | New SW waiting to activate |
| Active | SW controlling the page |
| Redundant | Old SW replaced by new version |

When a new version is deployed, the user is prompted to reload to apply the update.

---

## Testing Offline Mode

1. Open **DevTools** → **Network** → set **Throttling** to "Offline".
2. Navigate between pages — cached pages load instantly.
3. Try submitting a form — the action is queued.
4. Re-enable network — observe automatic sync.
