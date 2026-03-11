import React, { useState } from 'react';

const DigitalFootprint: React.FC = () => {
  const [query, setQuery] = useState('');

  return (
    <div>
      <h1 style={{ marginBottom: 24, fontSize: 22 }}>Digital Footprint</h1>
      <div className="card" style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', marginBottom: 8, color: '#8892b0', fontSize: 13 }}>
          Search target (email, phone, username)
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter email, phone, or username..."
            style={{
              flex: 1, background: '#1a1a2e', border: '1px solid #0f3460',
              borderRadius: 8, padding: '10px 14px', color: '#ccd6f6',
              fontSize: 14, minHeight: 44,
            }}
          />
          <button
            style={{
              background: '#0f3460', color: '#64ffda', border: 'none',
              borderRadius: 8, padding: '10px 20px', cursor: 'pointer',
              fontWeight: 600, minHeight: 44,
            }}
          >
            Scan
          </button>
        </div>
      </div>
      <div className="card">
        <p style={{ color: '#8892b0', fontSize: 14 }}>Results will appear here after scanning.</p>
      </div>
    </div>
  );
};

export default DigitalFootprint;
