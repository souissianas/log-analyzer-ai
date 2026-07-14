import { useState, useRef, useEffect, useCallback } from 'react'
import LogUploader from './components/LogUploader'
import ErrorAnalysis from './components/ErrorAnalysis'
import HistoryPage from './components/HistoryPage'
import LoadingSpinner from './components/LoadingSpinner'
import LoginPage from './components/LoginPage'
import Dashboard from './components/Dashboard'
import UserManagementPage from './components/UserManagementPage'
import Navbar from './components/Navbar'
import AccountModals from './components/AccountModals'
import { useTranslation } from './i18n'
import {
  submitAnalysisJob,
  streamJobProgress,
  getJobResult,
  fetchAnalysis,
  downloadAnalysisPdf,
  getCurrentUser,
  syncCurrentUser,
  logout,
} from './api'

const VIEWS = {
  ANALYZE: 'analyze',
  HISTORY: 'history',
  DASHBOARD: 'dashboard',
  USERS: 'users',
}

export default function App() {
  const { language, setLanguage, t } = useTranslation()
  const [user, setUser] = useState(() => getCurrentUser())
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [historyKey, setHistoryKey] = useState(0)
  const [activeView, setActiveView] = useState(VIEWS.ANALYZE)
  const [progress, setProgress] = useState({ current: 0, total: 0 })
  const streamRef = useRef(null)

  // ── Navbar extra state (shared) ─────────────────────────────────
  const [darkMode, setDarkMode] = useState(() => {
    return localStorage.getItem('theme') !== 'light'
  })
  const [showAccountModal, setShowAccountModal] = useState(false)
  const [showSettingsModal, setShowSettingsModal] = useState(false)
  const [showProfileMenu, setShowProfileMenu] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [lastLogin] = useState(() => {
    const stored = localStorage.getItem('lastLogin')
    if (stored) return new Date(stored)
    return null
  })

  // Apply theme to <body>
  useEffect(() => {
    document.body.classList.toggle('theme-light', !darkMode)
    localStorage.setItem('theme', darkMode ? 'dark' : 'light')
  }, [darkMode])

  // Keyboard shortcuts
  const handleKeyDown = useCallback((e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
    if (e.key === 'Escape') {
      setShowAccountModal(false)
      setShowSettingsModal(false)
    }
    if ((e.ctrlKey || e.metaKey) && e.key === '1') { e.preventDefault(); setActiveView(VIEWS.ANALYZE) }
    if ((e.ctrlKey || e.metaKey) && e.key === '2') { e.preventDefault(); setActiveView(VIEWS.HISTORY) }
    if ((e.ctrlKey || e.metaKey) && e.key === '3') { e.preventDefault(); setActiveView(VIEWS.DASHBOARD) }
    if ((e.ctrlKey || e.metaKey) && e.key === '4' && user?.role === 'admin') { e.preventDefault(); setActiveView(VIEWS.USERS) }
  }, [user])

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  function handleLogout() {
    logout()
    setUser(null)
    resetState()
    setShowProfileMenu(false)
  }

  // Fetch current user on mount / login to get fresh role and status.
  // syncCurrentUser (api.js) validates the response and persists role/email
  // to localStorage itself — App.jsx only consumes the already-safe result.
  useEffect(() => {
    if (user && user.token) {
      syncCurrentUser()
        .then(freshUser => {
          setUser(prev => ({ ...prev, ...freshUser }))
        })
        .catch(err => {
          console.error('Error updating user info:', err)
          if (err.message && err.message.includes('401')) {
            handleLogout()
          }
        })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.token])

  // ── Core handlers ───────────────────────────────────────────────
  function resetState() {
    setError(null)
    setResults(null)
    setProgress({ current: 0, total: 0 })
    streamRef.current?.close()
    streamRef.current = null
  }

  function handleLoginSuccess(userData) {
    setUser(userData)
    setHistoryKey((k) => k + 1)
    localStorage.setItem('lastLogin', new Date().toISOString())
  }

  async function handleAnalyze(file) {
    resetState()
    setLoading(true)
    setActiveView(VIEWS.ANALYZE)

    try {
      const maxErrors = 999999
      const job = await submitAnalysisJob(file, maxErrors)
      setProgress({ current: 0, total: 0 })

      await new Promise((resolve, reject) => {
        const stream = streamJobProgress(job.job_id, {
          onProgress: ({ current, total }) => {
            setProgress({ current: current ?? 0, total: total ?? 0 })
          },
          onDone: async ({ log_id }) => {
            try {
              const { result } = await getJobResult(job.job_id)
              setResults({ ...result, log_id })
              setHistoryKey((k) => k + 1)
              const msg = language === 'fr'
                ? `Analyse terminée — ${file.name}`
                : `Analysis completed — ${file.name}`
              setNotifications(prev => [{
                id: Date.now(),
                text: msg,
                time: new Date().toLocaleTimeString(language === 'fr' ? 'fr-FR' : 'en-US', { hour: '2-digit', minute: '2-digit' }),
                read: false,
              }, ...prev.slice(0, 9)])
              resolve()
            } catch (fetchErr) {
              reject(fetchErr)
            }
          },
          onError: (msg) => reject(new Error(msg)),
        })
        streamRef.current = stream
      })
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
      streamRef.current = null
    }
  }

  async function handleSelectHistory(logId) {
    resetState()
    setLoading(true)
    setActiveView(VIEWS.ANALYZE)
    try {
      const item = await fetchAnalysis(logId)
      setResults({ ...item.data, log_id: item.id })
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  async function handleExportPdf(logId) {
    try {
      await downloadAnalysisPdf(logId)
    } catch (err) {
      setError(String(err))
    }
  }

  if (!user) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />
  }

  function getLoadingMessage() {
    if (!loading) return null
    if (progress.total > 0) {
      return language === 'fr'
        ? `Analyse IA — erreur ${progress.current + 1} / ${progress.total}…`
        : `AI Analysis — error ${progress.current + 1} / ${progress.total}…`
    }
    return language === 'fr' ? 'Soumission de l\'analyse…' : 'Submitting analysis…'
  }
  const loadingMessage = getLoadingMessage()

  const unreadCount = notifications.filter(n => !n.read).length

  function formatLastLogin(date) {
    if (!date) return null
    const now = new Date()
    const diff = Math.floor((now - date) / 1000 / 60)
    if (diff < 1) return t('dateJustNow')
    if (diff < 60) return t('dateMinsAgo', { n: diff })
    const h = Math.floor(diff / 60)
    if (h < 24) return t('dateHoursAgo', { n: h })
    return date.toLocaleDateString(language === 'fr' ? 'fr-FR' : 'en-US')
  }

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
    <div className="dashboard-layout">
      <AccountModals
        showAccountModal={showAccountModal}
        setShowAccountModal={setShowAccountModal}
        showSettingsModal={showSettingsModal}
        setShowSettingsModal={setShowSettingsModal}
        user={user}
        darkMode={darkMode}
        setDarkMode={setDarkMode}
        t={t}
        language={language}
      />

      <Navbar
        user={user}
        activeView={activeView}
        setActiveView={setActiveView}
        loading={loading}
        loadingMessage={loadingMessage}
        language={language}
        setLanguage={setLanguage}
        darkMode={darkMode}
        setDarkMode={setDarkMode}
        notifications={notifications}
        setNotifications={setNotifications}
        lastLogin={lastLogin}
        formatLastLogin={formatLastLogin}
        setShowAccountModal={setShowAccountModal}
        setShowSettingsModal={setShowSettingsModal}
        handleLogout={handleLogout}
        VIEWS={VIEWS}
        t={t}
      />

      {/* ── App Content ─────────────────────────────────────────── */}
      <div className="app-container">
        {activeView === VIEWS.DASHBOARD && (
          <Dashboard onClose={() => setActiveView(VIEWS.ANALYZE)} />
        )}

        {activeView === VIEWS.HISTORY && (
          <HistoryPage onSelect={handleSelectHistory} refreshKey={historyKey} />
        )}

        {activeView === VIEWS.USERS && user?.role === 'admin' && (
          <UserManagementPage />
        )}

        {activeView === VIEWS.ANALYZE && (
          <div className="app-grid full-width">
            <main className="main-content">
              <LogUploader onAnalyze={handleAnalyze} disabled={loading} role={user.role} />

              {loading && (
                <LoadingSpinner
                  message={loadingMessage}
                  current={progress.current}
                  total={progress.total}
                />
              )}

              {error && (
                <div className="alert-error" role="alert">
                  <div className="alert-icon-container">
                    <svg className="alert-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="8" x2="12" y2="12" />
                      <line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                  </div>
                  <div className="alert-message">{error}</div>
                </div>
              )}

              <ErrorAnalysis data={results} onExportPdf={handleExportPdf} role={user.role} />
            </main>
          </div>
        )}
      </div>
    </div>
  )
}
