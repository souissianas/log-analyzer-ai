import { useEffect, useState, useMemo } from 'react'
import { fetchAnalysisHistory } from '../api'
import { useTranslation } from '../i18n'

export default function HistoryPage({ onSelect, refreshKey }) {
  const { t, language } = useTranslation()
  const [items, setItems] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState('date_desc')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [viewMode, setViewMode] = useState('grouped') // 'grouped' | 'flat'

  const SORT_OPTIONS = useMemo(() => [
    { value: 'date_desc', label: t('historySortRecent') },
    { value: 'date_asc',  label: t('historySortOldest') },
    { value: 'errors_desc', label: t('historySortErrorsDesc') },
    { value: 'errors_asc',  label: t('historySortErrorsAsc') },
  ], [t])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchAnalysisHistory()
      .then((data) => { if (!cancelled) setItems(data.items || []) })
      .catch((err) => { if (!cancelled) setError(String(err)) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [refreshKey])

  function formatDate(dateStr) {
    if (!dateStr) return ''
    try {
      return new Date(dateStr).toLocaleString(language === 'fr' ? 'fr-FR' : 'en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    } catch { return dateStr }
  }

  function formatDateRelative(dateStr) {
    if (!dateStr) return ''
    try {
      const now = new Date()
      const date = new Date(dateStr)
      const diff = Math.floor((now - date) / 1000)
      if (diff < 60) return t('dateJustNow')
      if (diff < 3600) return t('dateMinsAgo', { n: Math.floor(diff / 60) })
      if (diff < 86400) return t('dateHoursAgo', { n: Math.floor(diff / 3600) })
      if (diff < 604800) return t('dateDaysAgo', { n: Math.floor(diff / 86400) })
      return date.toLocaleDateString(language === 'fr' ? 'fr-FR' : 'en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    } catch { return dateStr }
  }

  const filteredAndSorted = useMemo(() => {
    const q = searchQuery.toLowerCase()
    let result = items.filter(item => {
      const filename = (item.filename || '').toLowerCase()
      return filename.includes(q) || String(item.id).includes(q) || formatDate(item.created_at).toLowerCase().includes(q)
    })
    result = [...result].sort((a, b) => {
      if (sortBy === 'date_desc') return new Date(b.created_at) - new Date(a.created_at)
      if (sortBy === 'date_asc')  return new Date(a.created_at) - new Date(b.created_at)
      if (sortBy === 'errors_desc') return (b.total_errors_found || 0) - (a.total_errors_found || 0)
      if (sortBy === 'errors_asc')  return (a.total_errors_found || 0) - (b.total_errors_found || 0)
      return 0
    })
    return result
  }, [items, searchQuery, sortBy, language])

  const groupedByFile = useMemo(() => {
    const groups = {}
    filteredAndSorted.forEach(item => {
      const key = item.filename || (language === 'fr' ? 'Sans nom' : 'Unnamed')
      if (!groups[key]) groups[key] = []
      groups[key].push(item)
    })
    return groups
  }, [filteredAndSorted, language])

  const [expandedFiles, setExpandedFiles] = useState({})
  useEffect(() => {
    if (filteredAndSorted.length > 0) {
      const firstFile = filteredAndSorted[0].filename || (language === 'fr' ? 'Sans nom' : 'Unnamed')
      setExpandedFiles(prev => ({ [firstFile]: true, ...prev }))
    }
  }, [items, searchQuery])

  const totalErrors = items.reduce((s, i) => s + (i.total_errors_found || 0), 0)
  const uniqueFiles = new Set(items.map(i => i.filename)).size

  function handleSelect(id) {
    setSelectedId(id)
    onSelect(id)
  }

  const getErrorColor = (count) => {
    if (count === 0) return 'var(--success)'
    if (count < 10) return 'var(--warning)'
    return 'var(--error)'
  }

  return (
    <div className="history-page">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="history-page-header">
        <div className="history-page-title-group">
          <div className="history-page-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12 6 12 12 16 14"/>
            </svg>
          </div>
          <div>
            <h1 className="history-page-title">{t('historyPageTitle')}</h1>
            <p className="history-page-subtitle">{t('historyPageSubtitle')}</p>
          </div>
        </div>

        {/* Stats pills */}
        <div className="history-stats-row">
          <div className="history-stat-pill">
            <span className="history-stat-value">{items.length}</span>
            <span className="history-stat-label">{t('historyStatAnalyses')}</span>
          </div>
          <div className="history-stat-pill">
            <span className="history-stat-value">{uniqueFiles}</span>
            <span className="history-stat-label">{t('historyStatFiles')}</span>
          </div>
          <div className="history-stat-pill history-stat-pill--error">
            <span className="history-stat-value">{totalErrors.toLocaleString()}</span>
            <span className="history-stat-label">{t('historyStatErrors')}</span>
          </div>
        </div>
      </div>

      {/* ── Toolbar ─────────────────────────────────────────────── */}
      <div className="history-toolbar">
        <div className="history-search-wrap">
          <svg className="history-search-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            type="text"
            placeholder={t('historySearchPlaceholder')}
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="history-page-search"
          />
          {searchQuery && (
            <button className="history-search-clear" onClick={() => setSearchQuery('')}>✕</button>
          )}
        </div>

        <div className="history-toolbar-right">
          <select
            className="history-sort-select"
            value={sortBy}
            onChange={e => setSortBy(e.target.value)}
          >
            {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          <div className="history-view-toggle">
            <button
              className={`history-view-btn ${viewMode === 'grouped' ? 'active' : ''}`}
              onClick={() => setViewMode('grouped')}
              title={t('historyViewTooltipGrouped')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15">
                <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
                <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
              </svg>
            </button>
            <button
              className={`history-view-btn ${viewMode === 'flat' ? 'active' : ''}`}
              onClick={() => setViewMode('flat')}
              title={t('historyViewTooltipFlat')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15">
                <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* ── Content ─────────────────────────────────────────────── */}
      <div className="history-page-body">
        {loading && (
          <div className="history-page-loading">
            <div className="history-page-spinner"/>
            <span>{t('historyLoading')}</span>
          </div>
        )}
        {error && <div className="history-page-error">{error}</div>}

        {!loading && !error && filteredAndSorted.length === 0 && (
          <div className="history-page-empty">
            <div className="history-empty-icon">🗂️</div>
            <p>{searchQuery ? t('historyNoResults') : t('historyEmptyState')}</p>
            {searchQuery && <button className="history-clear-search-btn" onClick={() => setSearchQuery('')}>{t('historyClearSearch')}</button>}
          </div>
        )}

        {!loading && !error && filteredAndSorted.length > 0 && viewMode === 'flat' && (
          <div className="history-flat-list">
            {filteredAndSorted.map(item => (
              <button
                key={item.id}
                className={`history-flat-item ${selectedId === item.id ? 'selected' : ''}`}
                onClick={() => handleSelect(item.id)}
              >
                <div className="history-flat-left">
                  <span className="history-flat-file-icon">📄</span>
                  <div className="history-flat-info">
                    <span className="history-flat-filename">{item.filename || (language === 'fr' ? 'Sans nom' : 'Unnamed')}</span>
                    <span className="history-flat-date">{formatDateRelative(item.created_at)} · #{item.id}</span>
                  </div>
                </div>
                <div className="history-flat-right">
                  <span className="history-flat-errors" style={{ color: getErrorColor(item.total_errors_found || 0) }}>
                    {item.total_errors_found || 0}
                  </span>
                  <span className="history-flat-errors-label">{t('historyErrorLabel', { s: (item.total_errors_found || 0) !== 1 ? 's' : '' })}</span>
                  <svg className="history-flat-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                    <polyline points="9 18 15 12 9 6"/>
                  </svg>
                </div>
              </button>
            ))}
          </div>
        )}

        {!loading && !error && filteredAndSorted.length > 0 && viewMode === 'grouped' && (
          <div className="history-grouped-grid">
            {Object.entries(groupedByFile).map(([filename, fileItems]) => {
              const isExpanded = expandedFiles[filename]
              const totalFileErrors = fileItems.reduce((s, i) => s + (i.total_errors_found || 0), 0)
              const latestDate = fileItems[0]?.created_at
              return (
                <div key={filename} className={`history-group-card ${isExpanded ? 'expanded' : ''}`}>
                  <button
                    className="history-group-header"
                    onClick={() => setExpandedFiles(prev => ({ ...prev, [filename]: !prev[filename] }))}
                  >
                    <div className="history-group-file-icon">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
                        <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
                        <polyline points="13 2 13 9 20 9"/>
                      </svg>
                    </div>
                    <div className="history-group-meta">
                      <span className="history-group-filename" title={filename}>{filename}</span>
                      <span className="history-group-detail">
                        {t('historyLatestAnalysis', { date: formatDateRelative(latestDate), errors: totalFileErrors.toLocaleString() })}
                      </span>
                    </div>
                    <div className="history-group-badges">
                      <span className="history-group-count-badge">
                        {t('historyRunsCount', { n: fileItems.length, s: fileItems.length > 1 ? 's' : '' })}
                      </span>
                    </div>
                    <svg className={`history-group-chevron ${isExpanded ? 'open' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                      <polyline points="6 9 12 15 18 9"/>
                    </svg>
                  </button>

                  {isExpanded && (
                    <div className="history-group-runs">
                      {fileItems.map(item => (
                        <button
                          key={item.id}
                          className={`history-run-card ${selectedId === item.id ? 'selected' : ''}`}
                          onClick={() => handleSelect(item.id)}
                        >
                          <div className="history-run-card-left">
                            <span className="history-run-badge">#{item.id}</span>
                            <span className="history-run-date">{formatDate(item.created_at)}</span>
                          </div>
                          <div className="history-run-card-right">
                            <div
                              className="history-run-errors-badge"
                              style={{
                                background: `${getErrorColor(item.total_errors_found || 0)}22`,
                                color: getErrorColor(item.total_errors_found || 0),
                                borderColor: `${getErrorColor(item.total_errors_found || 0)}44`,
                              }}
                            >
                              {item.total_errors_found || 0} {t('historyErrorLabel', { s: (item.total_errors_found || 0) !== 1 ? 's' : '' })}
                            </div>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="12" height="12" style={{ color: 'var(--muted)', flexShrink: 0 }}>
                              <polyline points="9 18 15 12 9 6"/>
                            </svg>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
