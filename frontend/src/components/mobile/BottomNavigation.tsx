import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import './BottomNavigation.css';

interface NavItem {
  label: string;
  path: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', path: '/dashboard', icon: '⊞' },
  { label: 'Footprint', path: '/modules/digital-footprint', icon: '👤' },
  { label: 'Investigate', path: '/modules/investigation', icon: '🔍' },
  { label: 'Cyber', path: '/modules/cyber-osint', icon: '🔒' },
  { label: 'More', path: '/settings', icon: '☰' },
];

export const BottomNavigation: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <nav className="bottom-nav" aria-label="Main navigation">
      {NAV_ITEMS.map((item) => (
        <button
          key={item.path}
          className={`bottom-nav__item ${location.pathname === item.path ? 'bottom-nav__item--active' : ''}`}
          onClick={() => navigate(item.path)}
          aria-current={location.pathname === item.path ? 'page' : undefined}
        >
          <span className="bottom-nav__icon" aria-hidden="true">{item.icon}</span>
          <span className="bottom-nav__label">{item.label}</span>
        </button>
      ))}
    </nav>
  );
};
