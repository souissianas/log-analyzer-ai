export default function AccountModals({
  showAccountModal,
  setShowAccountModal,
  showSettingsModal,
  setShowSettingsModal,
  user,
  darkMode,
  setDarkMode,
  t,
  language,
}) {
  if (!showAccountModal && !showSettingsModal) return null;
  return (
    <>
      {/* ── Mon Compte Modal ─────────────────────────────────────── */}
      {showAccountModal && (
        <div
          className="modal-overlay"
          role="button"
          tabIndex={0}
          onClick={() => setShowAccountModal(false)}
          onKeyDown={(e) => {
            if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setShowAccountModal(false);
            }
          }}
        >
          <div className="shortcuts-modal" onClick={e => e.stopPropagation()} style={{ minWidth: '420px' }}>
            <div className="shortcuts-modal-header">
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ width: '20px', height: '20px', color: 'var(--accent)' }}>
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
                {t('accountTitle')}
              </h3>
              <button className="modal-close-btn" onClick={() => setShowAccountModal(false)}>{t('modalClose')}</button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '8px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontSize: '0.78rem', color: 'var(--muted)', textTransform: 'uppercase', fontWeight: 600 }}>{t('accountEmail')}</span>
                <span style={{ fontSize: '0.95rem', fontWeight: 500, wordBreak: 'break-all' }}>{user.email}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontSize: '0.78rem', color: 'var(--muted)', textTransform: 'uppercase', fontWeight: 600 }}>{t('accountRole')}</span>
                <div><span className={`user-role-badge role-${user.role}`} style={{ display: 'inline-block' }}>{user.role}</span></div>
              </div>
              <div style={{ height: '1px', background: 'var(--surface-2)', margin: '4px 0' }} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span style={{ fontSize: '0.78rem', color: 'var(--muted)', textTransform: 'uppercase', fontWeight: 600 }}>{t('accountPermissions')}</span>
                <p style={{ fontSize: '0.85rem', color: 'var(--muted)', margin: 0, lineHeight: 1.45 }}>
                  {user.role === 'admin' && t('roleDescAdmin')}
                  {user.role === 'analyst' && t('roleDescAnalyst')}
                  {user.role === 'viewer' && t('roleDescViewer')}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
      {/* ── Paramètres Modal ─────────────────────────────────────── */}
      {showSettingsModal && (
        <div
          className="modal-overlay"
          role="button"
          tabIndex={0}
          onClick={() => setShowSettingsModal(false)}
          onKeyDown={(e) => {
            if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setShowSettingsModal(false);
            }
          }}
        >
          <div className="shortcuts-modal" onClick={e => e.stopPropagation()} style={{ minWidth: '420px' }}>
            <div className="shortcuts-modal-header">
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ width: '20px', height: '20px', color: 'var(--accent)' }}>
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
                {t('settingsTitle')}
              </h3>
              <button className="modal-close-btn" onClick={() => setShowSettingsModal(false)}>{t('modalClose')}</button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>{t('settingsTheme')}</span>
                  <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>{t('settingsThemeDesc')}</span>
                </div>
                <button className="btn-nav-toggle" onClick={() => setDarkMode(prev => !prev)} style={{ minWidth: '100px', justifyContent: 'center' }}>
                  {darkMode ? t('settingsThemeLightBtn') : t('settingsThemeDarkBtn')}
                </button>
              </div>
              <div style={{ height: '1px', background: 'var(--surface-2)' }} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>{t('settingsModel')}</span>
                <span style={{ fontSize: '0.78rem', color: 'var(--muted)', marginBottom: '4px' }}>{t('settingsModelDesc')}</span>
                <input type="text" value="llama3.2 (Local Ollama)" disabled style={{ padding: '8px 12px', background: 'var(--surface-2)', border: '1px solid var(--surface-2)', borderRadius: '8px', color: 'var(--muted)', fontSize: '0.85rem' }} />
              </div>
              <div style={{ height: '1px', background: 'var(--surface-2)' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--error)' }}>{t('settingsData')}</span>
                  <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>{t('settingsDataDesc')}</span>
                </div>
                <button className="btn-logout" onClick={() => {
                  if (window.confirm(t('settingsResetConfirm'))) {
                    const theme = localStorage.getItem('theme');
                    const lastLogin = localStorage.getItem('lastLogin');
                    const lang = localStorage.getItem('lang');
                    localStorage.clear();
                    if (theme !== null) localStorage.setItem('theme', theme);
                    if (lastLogin !== null) localStorage.setItem('lastLogin', lastLogin);
                    if (lang !== null) localStorage.setItem('lang', lang);
                    window.location.reload();
                  }
                }}>
                  {t('settingsResetBtn')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
