import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ResponsiveNavigation } from './components/responsive/ResponsiveNavigation';
import { InstallPrompt } from './components/mobile/InstallPrompt';
import { PushNotifications } from './components/mobile/PushNotifications';
import { useNetworkStatus } from './hooks/useNetworkStatus';
import './index.css';

// Lazy-loaded modules for code splitting
const Dashboard = lazy(() => import('./pages/Dashboard'));
const DigitalFootprint = lazy(() => import('./pages/DigitalFootprint'));
const Investigation = lazy(() => import('./pages/Investigation'));
const CyberOSINT = lazy(() => import('./pages/CyberOSINT'));
const Misinformation = lazy(() => import('./pages/Misinformation'));
const Settings = lazy(() => import('./pages/Settings'));

const PageLoader: React.FC = () => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '200px', color: '#64ffda' }}>
    Loading...
  </div>
);

const AppContent: React.FC = () => {
  const { isOnline } = useNetworkStatus();

  return (
    <div className="app-layout">
      <ResponsiveNavigation />
      <main className="main-content">
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/modules/digital-footprint" element={<DigitalFootprint />} />
            <Route path="/modules/investigation" element={<Investigation />} />
            <Route path="/modules/investigation/new" element={<Investigation />} />
            <Route path="/modules/cyber-osint" element={<CyberOSINT />} />
            <Route path="/modules/misinformation" element={<Misinformation />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/share" element={<Dashboard />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Suspense>
      </main>

      {!isOnline && (
        <div className="offline-banner" role="alert">
          📡 You are offline — showing cached data
        </div>
      )}

      <InstallPrompt />
      <PushNotifications />
    </div>
  );
};

const App: React.FC = () => (
  <BrowserRouter>
    <AppContent />
  </BrowserRouter>
);

export default App;
