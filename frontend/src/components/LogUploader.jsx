import { useState } from 'react'
import { useTranslation } from '../i18n'

function formatSize(bytes) {
  if (!bytes) return '0 Ko'
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}

export default function LogUploader({ onAnalyze, disabled, role }) {
  const { t } = useTranslation()
  const [file, setFile] = useState(null)
  const [validationError, setValidationError] = useState(null)
  const isViewer = role === 'viewer'

  function selectFile(nextFile) {
    setValidationError(null)

    if (!nextFile) {
      setFile(null)
      return
    }

    if (isViewer) {
      setValidationError(t('uploaderRoleError'))
      return
    }

    if (!nextFile.name.match(/\.(log|txt)$/i)) {
      setFile(null)
      setValidationError(t('uploaderFormatError'))
      return
    }

    setFile(nextFile)
  }

  function handleDrop(e) {
    e.preventDefault()
    if (disabled || isViewer) return
    selectFile(e.dataTransfer.files[0] || null)
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (isViewer || !file || disabled) return
    onAnalyze(file)
  }

  // Smell "Extract this nested ternary operation into an independent
  // statement" : chaque libellé conditionnel (titre de la zone de dépôt,
  // description, libellé du bouton) est calculé à part plutôt qu'en JSX.
  let dropZoneTitle
  if (isViewer) {
    dropZoneTitle = t('uploaderViewerTitle')
  } else if (file) {
    dropZoneTitle = file.name
  } else {
    dropZoneTitle = t('uploaderDropText')
  }

  let dropZoneMeta
  if (isViewer) {
    dropZoneMeta = t('uploaderViewerDesc')
  } else if (file) {
    dropZoneMeta = t('uploaderReadyText', { name: formatSize(file.size) })
  } else {
    dropZoneMeta = t('uploaderClickText')
  }

  let submitLabel
  if (isViewer) {
    submitLabel = t('uploaderRoleViewerLabel')
  } else if (disabled) {
    submitLabel = t('uploaderBtnLoading')
  } else {
    submitLabel = t('uploaderBtnAnalyze')
  }

  return (
    <section className="upload-card">
      <h2>{t('uploaderTitle')}</h2>

      <form onSubmit={handleSubmit}>
        <label
          className={`drop-zone ${file ? 'has-file' : ''} ${isViewer ? 'disabled-zone' : ''}`}
          htmlFor="log-file"
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
        >
          <span className="drop-zone-title">{dropZoneTitle}</span>
          <span className="drop-zone-meta">{dropZoneMeta}</span>
        </label>

        <input
          id="log-file"
          type="file"
          accept=".log,.txt"
          disabled={disabled || isViewer}
          onChange={(e) => selectFile(e.target.files[0] || null)}
        />

        {file && !disabled && (
          <div style={{ display: 'flex', gap: '10px', margin: '12px 0 4px 0' }}>
            <button
              type="button"
              onClick={() => selectFile(null)}
              style={{
                flex: 1,
                padding: '8px 12px',
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.2)',
                borderRadius: '8px',
                color: '#fca5a5',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px'
              }}
              onMouseOver={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)'; }}
              onMouseOut={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)'; }}
              onFocus={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)'; }}
              onBlur={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)'; }}
            >
              {t('uploaderBtnRemove')}
            </button>
            <button
              type="button"
              onClick={() => {
                const el = document.getElementById('log-file');
                if (el) {
                  el.value = '';
                  el.click();
                }
              }}
              style={{
                flex: 1,
                padding: '8px 12px',
                background: 'rgba(59, 130, 246, 0.1)',
                border: '1px solid rgba(59, 130, 246, 0.2)',
                borderRadius: '8px',
                color: '#93c5fd',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px'
              }}
              onMouseOver={(e) => { e.currentTarget.style.background = 'rgba(59, 130, 246, 0.2)'; }}
              onMouseOut={(e) => { e.currentTarget.style.background = 'rgba(59, 130, 246, 0.1)'; }}
              onFocus={(e) => { e.currentTarget.style.background = 'rgba(59, 130, 246, 0.2)'; }}
              onBlur={(e) => { e.currentTarget.style.background = 'rgba(59, 130, 246, 0.1)'; }}
            >
              {t('uploaderBtnChange')}
            </button>
          </div>
        )}

        {validationError && <p className="form-error">{validationError}</p>}

        <button type="submit" disabled={!file || disabled || isViewer}>
          {submitLabel}
        </button>
      </form>

      {file && <p className="file-hint">{t('uploaderHint')}</p>}
    </section>
  )
}
