import React, { type ReactNode } from 'react';
import './ResponsiveGrid.css';

interface ResponsiveGridProps {
  children: ReactNode;
  mobileColumns?: 1 | 2;
  tabletColumns?: 1 | 2 | 3;
  desktopColumns?: 1 | 2 | 3 | 4;
  gap?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const ResponsiveGrid: React.FC<ResponsiveGridProps> = ({
  children,
  mobileColumns = 1,
  tabletColumns = 2,
  desktopColumns = 3,
  gap = 'md',
  className,
}) => {
  return (
    <div
      className={`responsive-grid responsive-grid--mobile-${mobileColumns} responsive-grid--tablet-${tabletColumns} responsive-grid--desktop-${desktopColumns} responsive-grid--gap-${gap} ${className ?? ''}`}
    >
      {children}
    </div>
  );
};
