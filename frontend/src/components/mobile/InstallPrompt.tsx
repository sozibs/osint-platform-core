import React, { useState } from 'react';
import { useInstallPrompt } from '../../hooks/useInstallPrompt';
import './InstallPrompt.css';

export const InstallPrompt: React.FC = () => {
  const { canInstall, isIOS, install } = useInstallPrompt();
  const [dismissed, setDismissed] = useState(false);
  const [showIOSInstructions, setShowIOSInstructions] = useState(false);

  if (dismissed || !canInstall) return null;

  const handleInstall = async () => {
    if (isIOS) {
      setShowIOSInstructions(true);
      return;
    }
    const outcome = await install();
    if (outcome === 'accepted' || outcome === 'dismissed') {
      setDismissed(true);
    }
  };

  return (
    <>
      <div className="install-prompt" role="banner">
        <div className="install-prompt__content">
          <div className="install-prompt__icon" aria-hidden="true">📱</div>
          <div className="install-prompt__text">
            <strong>Install OSINT Platform</strong>
            <p>Add to your home screen for the best experience</p>
          </div>
        </div>
        <div className="install-prompt__actions">
          <button className="install-prompt__btn install-prompt__btn--primary" onClick={handleInstall}>
            Install
          </button>
          <button
            className="install-prompt__btn install-prompt__btn--dismiss"
            onClick={() => setDismissed(true)}
            aria-label="Dismiss install prompt"
          >
            ✕
          </button>
        </div>
      </div>

      {showIOSInstructions && (
        <div className="ios-modal" role="dialog" aria-modal="true" aria-label="iOS installation instructions">
          <div className="ios-modal__overlay" onClick={() => setShowIOSInstructions(false)} />
          <div className="ios-modal__content">
            <h3>Install on iOS</h3>
            <ol>
              <li>Tap the <strong>Share</strong> button in Safari <span aria-hidden="true">⬆️</span></li>
              <li>Scroll down and tap <strong>&quot;Add to Home Screen&quot;</strong></li>
              <li>Tap <strong>&quot;Add&quot;</strong></li>
            </ol>
            <button className="install-prompt__btn install-prompt__btn--primary" onClick={() => { setShowIOSInstructions(false); setDismissed(true); }}>
              Got it
            </button>
          </div>
        </div>
      )}
    </>
  );
};
