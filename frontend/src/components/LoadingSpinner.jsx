export default function LoadingSpinner({ message, current, total }) {
  const hasProgress = typeof current === 'number' && typeof total === 'number' && total > 0
  const pct = hasProgress ? Math.round((current / total) * 100) : null

  return (
    <div className="loading-overlay" aria-live="polite" aria-busy="true" role="status">
      <div className="spinner" aria-hidden="true" />
      <p>{message || 'Analyse en cours...'}</p>

      {hasProgress && (
        <div className="progress-container" aria-label={`Progression: ${current} sur ${total}`}>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${pct}%` }}
              aria-valuenow={pct}
              aria-valuemin={0}
              aria-valuemax={100}
              role="progressbar"
            />
          </div>
          <p className="progress-label">
            {current} / {total} erreurs analysées ({pct}%)
          </p>
        </div>
      )}

      <p className="loading-hint">
        {hasProgress
          ? `Analyse en cours (${total - current} restants) — optimisée par dédoublonnage de signatures.`
          : "L'inférence s'exécute sur le processeur local, veuillez patienter."}
      </p>
    </div>
  )
}
