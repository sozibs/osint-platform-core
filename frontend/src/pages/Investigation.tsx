import React from 'react';

const Investigation: React.FC = () => (
  <div>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
      <h1 style={{ fontSize: 22 }}>Investigation</h1>
      <button
        style={{
          background: '#0f3460', color: '#64ffda', border: 'none',
          borderRadius: 8, padding: '10px 20px', cursor: 'pointer',
          fontWeight: 600, minHeight: 44,
        }}
      >
        + New Case
      </button>
    </div>
    <div className="card">
      <p style={{ color: '#8892b0', fontSize: 14 }}>No active investigations. Start a new case to begin.</p>
    </div>
  </div>
);

export default Investigation;
