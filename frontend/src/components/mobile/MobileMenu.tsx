import React from 'react';
import { useNavigate } from 'react-router-dom';
import './MobileMenu.css';

interface MenuProps {
  isOpen: boolean;
  onClose: () => void;
}

const MENU_ITEMS = [
  { label: 'Dashboard', path: '/dashboard', icon: '⊞' },
  { label: 'Digital Footprint', path: '/modules/digital-footprint', icon: '👤' },
  { label: 'Investigation', path: '/modules/investigation', icon: '🔍' },
  { label: 'Cyber OSINT', path: '/modules/cyber-osint', icon: '🔒' },
  { label: 'Misinformation', path: '/modules/misinformation', icon: '📰' },
  { label: 'Settings', path: '/settings', icon: '⚙️' },
];

export const MobileMenu: React.FC<MenuProps> = ({ isOpen, onClose }) => {
  const navigate = useNavigate();

  const handleNav = (path: string) => {
    navigate(path);
    onClose();
  };

  return (
    <>
      {isOpen && (
        <div className="mobile-menu__overlay" onClick={onClose} aria-hidden="true" />
      )}
      <aside
        className={`mobile-menu ${isOpen ? 'mobile-menu--open' : ''}`}
        aria-label="Navigation menu"
        aria-hidden={!isOpen}
      >
        <div className="mobile-menu__header">
          <span className="mobile-menu__logo">🛡️ OSINT Platform</span>
          <button className="mobile-menu__close" onClick={onClose} aria-label="Close menu">
            ✕
          </button>
        </div>
        <nav>
          {MENU_ITEMS.map((item) => (
            <button key={item.path} className="mobile-menu__item" onClick={() => handleNav(item.path)}>
              <span className="mobile-menu__item-icon" aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
      </aside>
    </>
  );
};
