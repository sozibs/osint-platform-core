import { useState, useEffect } from 'react';

interface NetworkStatus {
  isOnline: boolean;
  effectiveType: string;
  downlink: number;
  rtt: number;
}

export function useNetworkStatus(): NetworkStatus {
  const getConnectionInfo = () => {
    const connection = (navigator as Navigator & {
      connection?: { effectiveType?: string; downlink?: number; rtt?: number };
    }).connection;
    return {
      isOnline: navigator.onLine,
      effectiveType: connection?.effectiveType ?? 'unknown',
      downlink: connection?.downlink ?? 0,
      rtt: connection?.rtt ?? 0,
    };
  };

  const [status, setStatus] = useState<NetworkStatus>(getConnectionInfo);

  useEffect(() => {
    const update = () => setStatus(getConnectionInfo());
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    return () => {
      window.removeEventListener('online', update);
      window.removeEventListener('offline', update);
    };
  }, []);

  return status;
}
