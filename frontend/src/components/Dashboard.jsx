import { useState, useEffect } from 'react'
import { fetchDashboardStats } from '../api'
import { useTranslation } from '../i18n'

const LEVEL_COLORS = {
  ERROR:    { bg: 'var(--level-error-bg)',  border: 'var(--level-error-border)', text: 'var(--level-error-text)' },
  CRITICAL: { bg: 'var(--level-crit-bg)',   border: 'var(--level-crit-border)',  text: 'var(--level-crit-text)' },
  WARNING:  { bg: 'var(--level-warn-bg)',   border: 'var(--level-warn-border)',  text: 'var(--level-warn-text)' },
  UNKNOWN:  { bg: 'var(--level-unk-bg)',    border: 'var(--level-unk-border)',   text: 'var(--level-unk-text)' },
}

function StatCard({ icon, label, value, sub, color = 'accent' }) {
  return (
    <div className={`dash-stat-card dash-stat-${color}`}>
      <div className="dash-stat-icon">{icon}</div>
      <div className="dash-stat-body">
        <div className="dash-stat-value">{value}</div>
        <div className="dash-stat-label">{label}</div>
        {sub && <div className="dash-stat-sub">{sub}</div>}
      </div>
    </div>
  )
}

function DonutChart({ data, title }) {
  const { t } = useTranslation()
  if (!data || data.length === 0) return (
    <div className="dash-chart-card">
      <h3 className="dash-chart-title">{title}</h3>
      <div className="dash-empty">{t('dashEmptyChart')}</div>
    </div>
  )

  const palette = ['#3b82f6', '#ef4444', '#f59e0b', '#22c55e', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']
  const total = data.reduce((s, d) => s + d.count, 0)
  let cumulative = 0
  const segments = data.map((d, i) => {
    const pct = total > 0 ? (d.count / total) * 100 : 0
    const seg = { ...d, pct, color: palette[i % palette.length], offset: cumulative }
    cumulative += pct
    return seg
  })

  // SVG donut via stroke-dasharray trick
  const r = 40
  const circ = 2 * Math.PI * r

  return (
    <div className="dash-chart-card">
      <h3 className="dash-chart-title">{title}</h3>
      <div className="dash-donut-wrapper">
        <svg viewBox="0 0 100 100" className="dash-donut-svg">
          <circle cx="50" cy="50" r={r} fill="none" stroke="var(--surface-2)" strokeWidth="14" />
          {segments.map((s, i) => (
            <circle
              key={i}
              cx="50" cy="50" r={r}
              fill="none"
              stroke={s.color}
              strokeWidth="14"
              strokeDasharray={`${(s.pct / 100) * circ} ${circ}`}
              strokeDashoffset={-((s.offset / 100) * circ)}
              transform="rotate(-90 50 50)"
              style={{ transition: 'stroke-dasharray 0.6s ease' }}
            />
          ))}
          <text x="50" y="46" textAnchor="middle" className="donut-center-num" fill="var(--text)" fontSize="13" fontWeight="700">{total}</text>
          <text x="50" y="58" textAnchor="middle" fill="var(--muted)" fontSize="6">total</text>
        </svg>
        <div className="dash-donut-legend">
          {segments.map((s, i) => (
            <div key={i} className="dash-legend-row">
              <span className="dash-legend-dot" style={{ background: s.color }} />
              <span className="dash-legend-label">{s.category || s.level || s.name}</span>
              <span className="dash-legend-count">{s.count}</span>
              <span className="dash-legend-pct">{s.pct.toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function BarChart({ data, title, barKey = 'count', labelKey = 'day', colorKey }) {
  const { t } = useTranslation()
  if (!data || data.length === 0) return (
    <div className="dash-chart-card">
      <h3 className="dash-chart-title">{title}</h3>
      <div className="dash-empty">{t('dashEmptyChartDays')}</div>
    </div>
  )

  const maxVal = Math.max(...data.map(d => d[barKey] || 0), 1)

  return (
    <div className="dash-chart-card">
      <h3 className="dash-chart-title">{title}</h3>
      <div className="dash-bar-chart">
        {data.map((d, i) => {
          const pct = ((d[barKey] || 0) / maxVal) * 100
          const label = String(d[labelKey] || '').slice(-5) // last 5 chars for date (MM-DD)
          return (
            <div key={i} className="dash-bar-col">
              <div className="dash-bar-val">{d[barKey] || 0}</div>
              <div className="dash-bar-track">
                <div
                  className="dash-bar-fill"
                  style={{
                    height: `${pct}%`,
                    background: colorKey === 'errors'
                      ? 'linear-gradient(180deg, #ef4444, #dc2626)'
                      : 'linear-gradient(180deg, #3b82f6, #6366f1)',
                    animationDelay: `${i * 0.05}s`,
                  }}
                />
              </div>
              <div className="dash-bar-label">{label}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function TopFilesTable({ data }) {
  const { t } = useTranslation()
  if (!data || data.length === 0) return (
    <div className="dash-chart-card">
      <h3 className="dash-chart-title">{t('dashChartTopFiles')}</h3>
      <div className="dash-empty">{t('dashEmptyChart')}</div>
    </div>
  )

  const maxErrors = Math.max(...data.map(d => d.total_errors), 1)

  return (
    <div className="dash-chart-card">
      <h3 className="dash-chart-title">{t('dashChartTopFiles')}</h3>
      <div className="dash-table-wrapper">
        <table className="dash-table">
          <thead>
            <tr>
              <th>{t('dashTableRank')}</th>
              <th>{t('dashTableFile')}</th>
              <th>{t('dashTableRuns')}</th>
              <th>{t('dashTableErrors')}</th>
              <th>{t('dashTableSplit')}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((f, i) => (
              <tr key={i}>
                <td className="dash-table-rank">{i + 1}</td>
                <td className="dash-table-filename" title={f.filename}>
                  📄 {f.filename.length > 28 ? '…' + f.filename.slice(-25) : f.filename}
                </td>
                <td className="dash-table-runs">{f.runs}</td>
                <td className="dash-table-errors">{f.total_errors}</td>
                <td className="dash-table-bar-cell">
                  <div className="dash-table-bar-track">
                    <div
                      className="dash-table-bar-fill"
                      style={{ width: `${(f.total_errors / maxErrors) * 100}%` }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function LevelBadges({ data }) {
  const { t } = useTranslation()
  if (!data || Object.keys(data).length === 0) return null
  return (
    <div className="dash-chart-card">
      <h3 className="dash-chart-title">{t('dashChartErrorsLevel')}</h3>
      <div className="dash-level-grid">
        {Object.entries(data).map(([level, count]) => {
          const c = LEVEL_COLORS[level] || LEVEL_COLORS.UNKNOWN
          return (
            <div key={level} className="dash-level-card" style={{ background: c.bg, borderColor: c.border }}>
              <span className="dash-level-count" style={{ color: c.text }}>{count}</span>
              <span className="dash-level-name" style={{ color: c.text }}>{level}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function Dashboard({ onClose }) {
  const { t } = useTranslation()
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchDashboardStats()
      .then(setStats)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="dashboard-page">
      {/* Header */}
      <div className="dash-header">
        <div className="dash-header-left">
          <div className="dash-header-icon">📊</div>
          <div>
            <h1 className="dash-title">{t('dashTitle')}</h1>
            <p className="dash-subtitle">{t('dashSubtitle')}</p>
          </div>
        </div>
        <button className="dash-close-btn" onClick={onClose}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
          {t('dashBackBtn')}
        </button>
      </div>

      {loading && (
        <div className="dash-loading">
          <div className="dash-spinner" />
          <span>{t('dashLoading')}</span>
        </div>
      )}

      {error && (
        <div className="dash-error">
          ⚠️ {error}
        </div>
      )}

      {stats && !loading && (
        <>
          {/* KPI Cards */}
          <div className="dash-kpi-grid">
            <StatCard
              icon="🔬"
              label={t('dashTotalAnalyses')}
              value={stats.total_analyses}
              sub={t('dashTotalAnalysesSub')}
              color="blue"
            />
            <StatCard
              icon="🔴"
              label={t('dashErrorsDetected')}
              value={stats.total_errors}
              sub={t('dashErrorsDetectedSub', { n: stats.total_analyzed })}
              color="red"
            />
            <StatCard
              icon="🤖"
              label={t('dashAiRate')}
              value={stats.total_errors > 0
                ? `${Math.round((stats.total_analyzed / stats.total_errors) * 100)}%`
                : '—'}
              sub={t('dashAiRateSub')}
              color="purple"
            />
            <StatCard
              icon="📁"
              label={t('dashUniqueFiles')}
              value={stats.top_files?.length ?? 0}
              sub={t('dashUniqueFilesSub')}
              color="green"
            />
          </div>

          {/* Charts row 1 */}
          <div className="dash-charts-grid-2">
            <BarChart
              data={stats.analyses_per_day}
              title={t('dashChartAnalysesDay')}
              barKey="count"
              labelKey="day"
            />
            <BarChart
              data={stats.analyses_per_day}
              title={t('dashChartErrorsDay')}
              barKey="errors"
              labelKey="day"
              colorKey="errors"
            />
          </div>

          {/* Charts row 2 */}
          <div className="dash-charts-grid-3">
            <LevelBadges data={stats.errors_by_level} />
            <DonutChart
              data={(stats.errors_by_category || []).filter(d => d.category !== 'unknown' && d.category !== 'Autre').map(d => ({ ...d, name: d.category }))}
              title={t('dashChartErrorsCategory')}
            />
            <TopFilesTable data={stats.top_files} />
          </div>
        </>
      )}
    </div>
  )
}
