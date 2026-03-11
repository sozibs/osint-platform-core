import React from 'react';
import { ResponsiveGrid } from '../components/responsive/ResponsiveGrid';
import { useDeviceType } from '../hooks/useDeviceType';

const StatCard: React.FC<{ label: string; value: string; icon: string }> = ({ label, value, icon }) => (
  <div className="card">
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
      <span style={{ fontSize: 24 }}>{icon}</span>
      <span style={{ color: '#8892b0', fontSize: 13 }}>{label}</span>
    </div>
    <div style={{ fontSize: 28, fontWeight: 700, color: '#64ffda' }}>{value}</div>
  </div>
);

const Dashboard: React.FC = () => {
  const deviceType = useDeviceType();
  return (
    <div>
      <h1 style={{ marginBottom: 24, fontSize: deviceType === 'mobile' ? 20 : 24 }}>Dashboard</h1>
      <ResponsiveGrid mobileColumns={2} tabletColumns={2} desktopColumns={4} gap="md">
        <StatCard label="Entities" value="1,284" icon="👤" />
        <StatCard label="Cases" value="47" icon="📁" />
        <StatCard label="Searches" value="326" icon="🔍" />
        <StatCard label="Alerts" value="12" icon="⚠️" />
      </ResponsiveGrid>
      <div style={{ marginTop: 32 }}>
        <h2 style={{ marginBottom: 16, fontSize: 18, color: '#ccd6f6' }}>Recent Activity</h2>
        <div className="card">
          <p style={{ color: '#8892b0', fontSize: 14 }}>No recent activity to display.</p>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
