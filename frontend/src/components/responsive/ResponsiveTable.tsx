import React from 'react';
import { useDeviceType } from '../../hooks/useDeviceType';
import './ResponsiveTable.css';

export interface Column<T> {
  key: keyof T;
  label: string;
  mobileVisible?: boolean;
  render?: (value: T[keyof T], row: T) => React.ReactNode;
}

interface ResponsiveTableProps<T extends Record<string, unknown>> {
  columns: Column<T>[];
  data: T[];
  keyField: keyof T;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
}

export function ResponsiveTable<T extends Record<string, unknown>>({
  columns,
  data,
  keyField,
  onRowClick,
  emptyMessage = 'No data available',
}: ResponsiveTableProps<T>) {
  const deviceType = useDeviceType();

  if (data.length === 0) {
    return (
      <div className="responsive-table__empty" role="status">
        {emptyMessage}
      </div>
    );
  }

  // Mobile: card view
  if (deviceType === 'mobile') {
    return (
      <div className="responsive-table__cards">
        {data.map((row) => (
          <div
            key={String(row[keyField])}
            className={`responsive-table__card ${onRowClick ? 'responsive-table__card--clickable' : ''}`}
            onClick={() => onRowClick?.(row)}
          >
            {columns
              .filter((col) => col.mobileVisible !== false)
              .map((col) => (
                <div key={String(col.key)} className="responsive-table__card-row">
                  <span className="responsive-table__card-label">{col.label}</span>
                  <span className="responsive-table__card-value">
                    {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? '')}
                  </span>
                </div>
              ))}
          </div>
        ))}
      </div>
    );
  }

  // Tablet / Desktop: table view
  const visibleColumns =
    deviceType === 'tablet' ? columns.filter((c) => c.mobileVisible !== false) : columns;

  return (
    <div className="responsive-table__wrapper">
      <table className="responsive-table__table">
        <thead>
          <tr>
            {visibleColumns.map((col) => (
              <th key={String(col.key)} className="responsive-table__th">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr
              key={String(row[keyField])}
              className={`responsive-table__tr ${onRowClick ? 'responsive-table__tr--clickable' : ''}`}
              onClick={() => onRowClick?.(row)}
            >
              {visibleColumns.map((col) => (
                <td key={String(col.key)} className="responsive-table__td">
                  {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
