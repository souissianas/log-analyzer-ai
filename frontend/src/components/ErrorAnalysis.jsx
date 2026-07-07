import { useTranslation } from '../i18n'

function levelClass(level) {
  const value = (level || '').toUpperCase()
  if (value === 'CRITICAL' || value === 'FATAL') return 'level-critical'
  if (value === 'ERROR' || value === 'FAIL') return 'level-error'
  if (value === 'WARNING' || value === 'WARN') return 'level-warning'
  return 'level-default'
}

function ResultStat({ label, value }) {
  return (
    <div className="result-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function AnalysisList({ title, items }) {
  if (!items?.length) return null

  return (
    <section className="analysis-block">
      <h4>{title}</h4>
      <ul>
        {items.map((item, index) => (
          <li key={`${title}-${index}`}>{item}</li>
        ))}
      </ul>
    </section>
  )
}

function ErrorCard({ error }) {
  const { t } = useTranslation()
  const { analysis } = error

  return (
    <article className={`error-card ${levelClass(error.level)}`}>
      <header className="error-card-header">
        <span className="error-badge">{error.level}</span>
        <h3>{t('analysisCardTitle', { n: error.index })}</h3>
        {error.category && error.category !== 'unknown' && (
          <span className="error-category">{error.category}</span>
        )}
        {error.processing_time_seconds != null && (
          <span className="error-timing">{error.processing_time_seconds}s</span>
        )}
      </header>

      <p className="error-message">{error.message}</p>

      <div className="error-meta">
        {error.line_number && <span>{t('analysisLineLabel', { n: error.line_number })}</span>}
        {error.timestamp && <span>{error.timestamp}</span>}
      </div>

      {!error.success && (
        <p className="error-fail">{t('analysisFailed', { err: error.error || 'Erreur inconnue' })}</p>
      )}

      {error.success && analysis && (
        <div className="analysis-sections">
          {analysis.explanation && (
            <section className="analysis-block explanation">
              <h4>{t('analysisExplanationHeader')}</h4>
              <p>{analysis.explanation}</p>
            </section>
          )}

          <AnalysisList title={t('analysisCausesHeader')} items={analysis.causes} />
          <AnalysisList title={t('analysisSolutionsHeader')} items={analysis.solutions} />
        </div>
      )}
    </article>
  )
}

export default function ErrorAnalysis({ data, onExportPdf, role }) {
  const { t } = useTranslation()

  if (!data) return null

  if (data.message && !data.analyzed?.length) {
    return (
      <section className="results-card">
        <h2>{t('analysisResultTitle', { name: data.filename })}</h2>
        <p className="no-errors">{data.message}</p>
      </section>
    )
  }

  return (
    <section className="results-card">
      <div className="results-header">
        <div>
          <h2>{t('analysisResultTitle', { name: data.filename })}</h2>
          <p className="results-summary">{t('analysisResultDesc')}</p>
        </div>
        {data.log_id && onExportPdf && role !== 'viewer' && (
          <button type="button" className="btn-secondary" onClick={() => onExportPdf(data.log_id)}>
            {t('analysisBtnExport')}
          </button>
        )}
      </div>

      <div className="result-stats">
        <ResultStat label={t('analysisStatDetected')} value={data.total_errors_found ?? 0} />
        <ResultStat label={t('analysisStatAnalyzed')} value={data.total_analyzed ?? data.analyzed?.length ?? 0} />
        <ResultStat label={t('analysisStatSkipped')} value={data.skipped ?? 0} />
      </div>

      <div className="analyzed-list">
        {data.analyzed?.map((error) => (
          <ErrorCard key={`${error.index}-${error.line_number}`} error={error} />
        ))}
      </div>
    </section>
  )
}
