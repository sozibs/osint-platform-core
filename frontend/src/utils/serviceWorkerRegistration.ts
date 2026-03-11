/// <reference types="vite-plugin-pwa/client" />
import { registerSW } from 'virtual:pwa-register';

export function registerServiceWorker(): () => void {
  const updateSW = registerSW({
    onNeedRefresh() {
      if (confirm('A new version of the app is available. Reload to update?')) {
        updateSW(true);
      }
    },
    onOfflineReady() {
      console.log('App is ready to work offline');
    },
    onRegistered(registration: ServiceWorkerRegistration | undefined) {
      console.log('Service worker registered:', registration);
    },
    onRegisterError(error: unknown) {
      console.error('Service worker registration failed:', error);
    },
  });
  return updateSW;
}
