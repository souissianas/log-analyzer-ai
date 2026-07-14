import { useState, useRef, useEffect } from 'react'

export default function Navbar({
  user,
  activeView,
  setActiveView,
  loading,
  loadingMessage,
  language,
  setLanguage,
  darkMode,
  setDarkMode,
  notifications,
  setNotifications,
  lastLogin,
  formatLastLogin,
  setShowAccountModal,
  setShowSettingsModal,
  handleLogout,
  VIEWS,
  t,
}) {
  const [showProfileMenu, setShowProfileMenu] = useState(false)
  const [showNotifications, setShowNotifications] = useState(false)
  const profileMenuRef = useRef(null)
  const notifRef = useRef(null)

  const unreadCount = notifications.filter(n => !n.read).length

  // Close dropdowns on Escape
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        setShowProfileMenu(false)
        setShowNotifications(false)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Close dropdowns when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target)) {
        setShowProfileMenu(false)
      }
      if (notifRef.current && !notifRef.current.contains(e.target)) {
        setShowNotifications(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const navItems = [
    {
      id: VIEWS.ANALYZE,
      label: t('navAnalyze'),
      shortcut: '⌘1',
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        </svg>
      ),
    },
    {
      id: VIEWS.HISTORY,
      label: t('navHistory'),
      shortcut: '⌘2',
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12 6 12 12 16 14"/>
        </svg>
      ),
    },
    {
      id: VIEWS.DASHBOARD,
      label: t('navDashboard'),
      shortcut: '⌘3',
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="3" width="20" height="14" rx="2"/>
          <line x1="8" y1="21" x2="16" y2="21"/>
          <line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
      ),
    },
  ]

  if (user?.role === 'admin') {
    navItems.push({
      id: VIEWS.USERS,
      label: t('navUsers') || 'Utilisateurs',
      shortcut: '⌘4',
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
      ),
    })
  }

  return (
    <nav className="navbar">
      <div className="nav-container">

        {/* Brand */}
        <div className="nav-brand">
          <div className="nav-logo-wrap">
            <svg className="nav-logo" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
              <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
              <line x1="12" y1="22.08" x2="12" y2="12" />
            </svg>
          </div>
          <div className="brand-text-container">
            <span className="brand-text">Log Analyzer <span className="brand-highlight">AI</span></span>
          </div>
        </div>

        {/* Center nav tabs */}
        <div className="nav-tabs">
          {navItems.map(item => (
            <button
              key={item.id}
              className={`nav-tab ${activeView === item.id ? 'active' : ''}`}
              onClick={() => setActiveView(item.id)}
              title={item.shortcut}
            >
              <span className="nav-tab-icon">{item.icon}</span>
              <span className="nav-tab-label">{item.label}</span>
              {activeView === item.id && <span className="nav-tab-indicator" />}
            </button>
          ))}
        </div>

        {/* Right section */}
        <div className="nav-profile">

          {/* Job indicator */}
          {loading && (
            <div className="nav-job-indicator" title={loadingMessage}>
              <span className="nav-job-spinner" />
              <span className="nav-job-label">{t('navAnalyzing')}</span>
            </div>
          )}

          <div className="profile-separator" />

          {/* Language switcher */}
          <button
            className="btn-icon-action btn-lang-toggle"
            onClick={() => setLanguage(prev => prev === 'fr' ? 'en' : 'fr')}
            title={language === 'fr' ? 'Switch to English' : 'Passer en Français'}
            style={{ fontSize: '0.78rem', fontWeight: 700, fontFamily: 'monospace' }}
          >
            {language.toUpperCase()}
          </button>

          {/* Theme toggle */}
          <button
            className="btn-icon-action"
            onClick={() => setDarkMode(prev => !prev)}
            title={t(darkMode ? 'navLightMode' : 'navDarkMode')}
          >
            {darkMode ? '☀️' : '🌙'}
          </button>

          {/* Notification Bell */}
          <div className="nav-notif-wrapper" ref={notifRef}>
            <button
              className="btn-icon-action"
              onClick={() => {
                setShowNotifications(prev => !prev)
                setShowProfileMenu(false)
              }}
              title={t('navNotifications')}
            >
              <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
              {unreadCount > 0 && (
                <span className="notif-badge">{unreadCount}</span>
              )}
            </button>

            {showNotifications && (
              <div className="notif-dropdown">
                <div className="notif-header">
                  <span>{t('navNotifications')}</span>
                  {unreadCount > 0 && (
                    <button className="notif-mark-read" onClick={() => setNotifications(prev => prev.map(n => ({ ...n, read: true })))}>
                      {t('navMarkAllRead')}
                    </button>
                  )}
                </div>
                {notifications.length === 0 ? (
                  <div className="notif-empty">{t('navNoNotifications')}</div>
                ) : (
                  <ul className="notif-list">
                    {notifications.map(n => (
                      <li
                        key={n.id}
                        className={`notif-item ${n.read ? '' : 'unread'}`}
                        role="button"
                        tabIndex={0}
                        onClick={() => setNotifications(prev => prev.map(x => x.id === n.id ? { ...x, read: true } : x))}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            setNotifications(prev => prev.map(x => x.id === n.id ? { ...x, read: true } : x))
                          }
                        }}
                      >
                        <div className="notif-icon">✅</div>
                        <div className="notif-content">
                          <span className="notif-text">{n.text}</span>
                          <span className="notif-time">{n.time}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>

          <div className="profile-separator" />

          {/* Profile dropdown */}
          <div className="nav-profile-wrapper" ref={profileMenuRef}>
            <button
              className="user-profile-card"
              onClick={() => {
                setShowProfileMenu(prev => !prev)
                setShowNotifications(false)
              }}
            >
              <div className="user-avatar">
                {user.email ? user.email[0].toUpperCase() : 'U'}
              </div>
              <div className="user-info">
                <span className="user-email" title={user.email}>{user.email}</span>
                <span className={`user-role-badge role-${user.role}`}>{user.role}</span>
              </div>
              <svg className={`dropdown-chevron ${showProfileMenu ? 'open' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>

            {showProfileMenu && (
              <div className="profile-dropdown">
                <div className="profile-dropdown-header">
                  <div className="profile-dropdown-avatar">
                    {user.email ? user.email[0].toUpperCase() : 'U'}
                  </div>
                  <div>
                    <div className="profile-dropdown-email">{user.email}</div>
                    <span className={`user-role-badge role-${user.role}`}>{user.role}</span>
                    {lastLogin && (
                      <div className="profile-last-login">
                        {t('navLastLogin')} {formatLastLogin(lastLogin)}
                      </div>
                    )}
                  </div>
                </div>

                <div className="profile-dropdown-divider" />

                <button className="profile-dropdown-item" onClick={() => { setShowAccountModal(true); setShowProfileMenu(false); }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
                  {t('navMyAccount')}
                </button>
                <button className="profile-dropdown-item" onClick={() => { setShowSettingsModal(true); setShowProfileMenu(false); }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>
                  {t('navSettings')}
                </button>

                <div className="profile-dropdown-divider" />

                <button className="profile-dropdown-item danger" onClick={handleLogout}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
                  {t('navLogout')}
                </button>
              </div>
            )}
          </div>

        </div>
      </div>
    </nav>
  )
}
