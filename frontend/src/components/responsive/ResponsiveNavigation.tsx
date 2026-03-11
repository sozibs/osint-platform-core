import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useDeviceType } from '../../hooks/useDeviceType';
import { BottomNavigation } from '../mobile/BottomNavigation';
import { MobileMenu } from '../mobile/MobileMenu';
import './ResponsiveNavigation.css';

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/dashboard', icon: '⊞' },
  { label: 'Digital Footprint', path: '/modules/digital-footprint', icon: '👤' },
  { label: 'Investigation', path: '/modules/investigation', icon: '🔍' },
  { label: 'Cyber OSINT', path: '/modules/cyber-osint', icon: '🔒' },
  { label: 'Misinformation', path: '/modules/misinformation', icon: '📰' },
  { label: 'Settings', path: '/settings', icon: '⚙️' },
];

export const ResponsiveNavigation: React.FC = () => {
  const deviceType = useDeviceType();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  if (deviceType === 'mobile') {
    return (
      <>
        <header className="mobile-header">
          <button
            className="mobile-header__menu-btn"
            onClick={() => setMenuOpen(true)}
            aria-label="Open menu"
          >
            ☰
          </button>
          <span className="mobile-header__title">🛡️ OSINT Platform</span>
          <div className="mobile-header__actions">
            <button className="mobile-header__icon-btn" aria-label="Search">🔍</button>
          </div>
        </header>
        <MobileMenu isOpen={menuOpen} onClose={() => setMenuOpen(false)} />
        <BottomNavigation />
      </>
    );
  }

  if (deviceType === 'tablet') {
    return (
      <>
        <header className="tablet-header">
          <button
            className="tablet-header__menu-btn"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
          >
            ☰
          </button>
          <span className="tablet-header__title">🛡️ OSINT Platform</span>
        </header>
        <MobileMenu isOpen={menuOpen} onClose={() => setMenuOpen(false)} />
      </>
    );
  }

  // Desktop sidebar
  return (
    <aside className="desktop-sidebar" aria-label="Main navigation">
      <div className="desktop-sidebar__logo">
        <span>🛡️</span>
        <span>OSINT Platform</span>
      </div>
      <nav className="desktop-sidebar__nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.path}
            className={`desktop-sidebar__item ${location.pathname === item.path ? 'desktop-sidebar__item--active' : ''}`}
            onClick={() => navigate(item.path)}
            aria-current={location.pathname === item.path ? 'page' : undefined}
          >
            <span className="desktop-sidebar__item-icon" aria-hidden="true">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
};
