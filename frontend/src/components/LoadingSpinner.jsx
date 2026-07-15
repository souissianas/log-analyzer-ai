// Smell "Use <progress> instead of the 'progressbar' role" : le fond +
// remplissage (deux <div>) reste tel quel pour le rendu visuel existant
// (largeur en %, dépend du CSS .progress-fill), mais il devient purement
// décoratif (aria-hidden) et un vrai <progress> natif porte désormais la
// sémantique d'accessibilité. Le <progress> est visuellement masqué avec
// la technique standard "visually hidden" (pas de display:none, pour
// rester perçu par les lecteurs d'écran) plutôt que rendu à l'écran, pour
// ne pas dupliquer visuellement la barre déjà dessinée par .progress-fill.
const visuallyHiddenStyle = {
  position: 'absolute',
  width: '1px',
  height: '1px',
  padding: 0,
  margin: '-1px',
  overflow: 'hidden',
  clip: 'rect(0, 0, 0, 0)',
  whiteSpace: 'nowrap',
  border: 0,
}

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
              aria-hidden="true"
            />
            <progress value={current} max={total} style={visuallyHiddenStyle}>
              {pct}%
            </progress>
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
