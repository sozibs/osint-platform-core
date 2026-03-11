import React, { useState } from 'react';

const Misinformation: React.FC = () => {
  const [claim, setClaim] = useState('');

  return (
    <div>
      <h1 style={{ marginBottom: 24, fontSize: 22 }}>Misinformation Analysis</h1>
      <div className="card" style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', marginBottom: 8, color: '#8892b0', fontSize: 13 }}>
          Claim or URL to verify
        </label>
        <textarea
          value={claim}
          onChange={(e) => setClaim(e.target.value)}
          placeholder="Paste a claim, article URL, or social media post to fact-check..."
          rows={4}
          style={{
            width: '100%', background: '#1a1a2e', border: '1px solid #0f3460',
            borderRadius: 8, padding: '10px 14px', color: '#ccd6f6',
            fontSize: 14, resize: 'vertical', fontFamily: 'inherit',
          }}
        />
        <button
          style={{
            marginTop: 12, background: '#0f3460', color: '#64ffda', border: 'none',
            borderRadius: 8, padding: '10px 20px', cursor: 'pointer',
            fontWeight: 600, minHeight: 44,
          }}
        >
          Analyze
        </button>
      </div>
      <div className="card">
        <p style={{ color: '#8892b0', fontSize: 14 }}>Fact-check results will appear here.</p>
      </div>
    </div>
  );
};

export default Misinformation;
