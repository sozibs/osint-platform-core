const CACHE_NAME = 'osint-platform-v1';
const STATIC_ASSETS = ['/', '/manifest.json'];

export async function precacheAssets(): Promise<void> {
  if ('caches' in window) {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(STATIC_ASSETS);
  }
}

export async function clearOldCaches(): Promise<void> {
  if ('caches' in window) {
    const cacheNames = await caches.keys();
    await Promise.all(
      cacheNames
        .filter((name) => name !== CACHE_NAME)
        .map((name) => caches.delete(name)),
    );
  }
}

export async function getCachedResponse(url: string): Promise<Response | undefined> {
  if ('caches' in window) {
    const cache = await caches.open(CACHE_NAME);
    return cache.match(url);
  }
  return undefined;
}
