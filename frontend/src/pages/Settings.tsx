import React from 'react';
import { usePWA } from '../hooks/usePWA';
import { useNetworkStatus } from '../hooks/useNetworkStatus';
import { useDeviceType } from '../hooks/useDeviceType';

const Settings: React.FC = () => {
  const { isStandalone, isOnline } = usePWA();
  const { effectiveType } = useNetworkStatus();
  const deviceType = useDeviceType();

  return (
    <div>
      <h1 style={{ marginBottom: 24, fontSize: 22 }}>Settings</h1>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: 16, marginBottom: 16, color: '#64ffda' }}>App Info</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#8892b0' }}>Mode</span>
            <span>{isStandalone ? '📱 Standalone (Installed)' : '🌐 Browser'}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#8892b0' }}>Network</span>
            <span>{isOnline ? `🟢 Online (${effectiveType})` : '🔴 Offline'}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#8892b0' }}>Device</span>
            <span style={{ textTransform: 'capitalize' }}>{deviceType}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#8892b0' }}>Version</span>
            <span>1.0.0</span>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 style={{ fontSize: 16, marginBottom: 16, color: '#64ffda' }}>Preferences</h2>
        <p style={{ color: '#8892b0', fontSize: 14 }}>Settings configuration coming soon.</p>
      </div>
    </div>
  );
};

export default Settings;
