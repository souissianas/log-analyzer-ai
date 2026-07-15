import { useState } from 'react'
import { login, register, forgotPassword, resetPassword } from '../api'
import { useTranslation } from '../i18n'

// view: 'login' | 'register' | 'forgot' | 'reset'
export default function LoginPage({ onLoginSuccess }) {
  const { t } = useTranslation()
  const [view, setView] = useState('login')

  // Login / Register fields
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [tenantName, setTenantName] = useState('')
  const [tenantSlug, setTenantSlug] = useState('')
  const [role, setRole] = useState('viewer')

  // Forgot / Reset fields
  const [forgotEmail, setForgotEmail] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [error, setError] = useState('')
  const [infoMessage, setInfoMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const handleTenantNameChange = (val) => {
    setTenantName(val)
    const slug = val
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/(^-|-$)/g, '')
    setTenantSlug(slug)
  }

  const switchView = (next) => {
    setView(next)
    setError('')
    setInfoMessage('')
  }

  // ─── Login / Register submit ───────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setInfoMessage('')
    setLoading(true)
    try {
      if (view === 'register') {
        if (!tenantName.trim() || !tenantSlug.trim()) {
          throw new Error(t('loginOrgError'))
        }
        const user = await register(email, password, tenantName, tenantSlug, role)
        if (user && user.access_token) {
          onLoginSuccess(user)
        } else {
          setInfoMessage(
            t('pendingRegistrationMessage') ||
            'Votre compte a été créé. Un administrateur doit le valider.'
          )
          switchView('login')
        }
      } else {
        const user = await login(email, password)
        onLoginSuccess(user)
      }
    } catch (err) {
      if (err.message && (err.message.includes('valider') || err.message.includes('attente'))) {
        setInfoMessage(err.message)
      } else {
        setError(err.message || 'Une erreur est survenue.')
      }
    } finally {
      setLoading(false)
    }
  }

  // ─── Forgot password: step 1 ──────────────────────────────────────────
  const handleForgotSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setInfoMessage('')
    setLoading(true)
    try {
      await forgotPassword(forgotEmail)
      setInfoMessage(
        'Un code à 6 chiffres a été envoyé par email (ou est visible dans les logs du serveur si le SMTP n\'est pas configuré). Entrez-le ci-dessous.'
      )
      switchView('reset')
    } catch (err) {
      setError(err.message || 'Erreur lors de la demande.')
    } finally {
      setLoading(false)
    }
  }

  // ─── Reset password: step 2 ───────────────────────────────────────────
  const handleResetSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    if (newPassword !== confirmPassword) {
      setError('Les mots de passe ne correspondent pas.')
      setLoading(false)
      return
    }
    try {
      await resetPassword(forgotEmail, otpCode, newPassword)
      setInfoMessage('Mot de passe mis à jour ! Vous pouvez maintenant vous connecter.')
      switchView('login')
    } catch (err) {
      setError(err.message || 'Erreur lors de la réinitialisation.')
    } finally {
      setLoading(false)
    }
  }

  // ─── Render helpers ───────────────────────────────────────────────────
  const renderForgotForm = () => (
    <form onSubmit={handleForgotSubmit} className="login-form">
      <p className="forgot-desc">
        Entrez votre adresse email. Vous recevrez un code à 6 chiffres par email.
      </p>
      <div className="form-group">
        <label htmlFor="forgot-email">Adresse email</label>
        <input
          type="email"
          id="forgot-email"
          placeholder="nom@entreprise.com"
          value={forgotEmail}
          onChange={(e) => setForgotEmail(e.target.value)}
          required
        />
      </div>
      <button type="submit" className="btn-primary login-btn" disabled={loading}>
        {loading ? 'Envoi en cours…' : 'Envoyer le code'}
      </button>
      <div className="login-footer">
        <button type="button" className="btn-link" onClick={() => switchView('login')}>
          ← Retour à la connexion
        </button>
      </div>
    </form>
  )

  const renderResetForm = () => (
    <form onSubmit={handleResetSubmit} className="login-form">
      <p className="forgot-desc">
        Entrez le code reçu et choisissez un nouveau mot de passe.
      </p>
      <div className="form-group">
        <label htmlFor="reset-email">Adresse email</label>
        <input
          type="email"
          id="reset-email"
          placeholder="nom@entreprise.com"
          value={forgotEmail}
          onChange={(e) => setForgotEmail(e.target.value)}
          required
        />
      </div>
      <div className="form-group">
        <label htmlFor="otp-code">Code de vérification (6 chiffres)</label>
        <input
          type="text"
          id="otp-code"
          placeholder="123456"
          maxLength={6}
          value={otpCode}
          onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
          required
          style={{ letterSpacing: '0.35em', fontSize: '1.2rem', textAlign: 'center' }}
        />
      </div>
      <div className="form-group">
        <label htmlFor="new-password">Nouveau mot de passe</label>
        <input
          type="password"
          id="new-password"
          placeholder="••••••••"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
          minLength={6}
        />
      </div>
      <div className="form-group">
        <label htmlFor="confirm-password">Confirmer le mot de passe</label>
        <input
          type="password"
          id="confirm-password"
          placeholder="••••••••"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
          minLength={6}
        />
      </div>
      <button type="submit" className="btn-primary login-btn" disabled={loading}>
        {loading ? 'Mise à jour…' : 'Mettre à jour le mot de passe'}
      </button>
      <div className="login-footer">
        <button type="button" className="btn-link" onClick={() => switchView('forgot')}>
          ← Renvoyer le code
        </button>
      </div>
    </form>
  )

  const renderLoginRegisterForm = () => {
    // Smell "Extract this nested ternary operation into an independent
    // statement" : le libellé du bouton dépendait de deux conditions
    // imbriquées (loading, puis view === 'register'). On les résout l'une
    // après l'autre avant le JSX plutôt qu'en une seule expression.
    let submitLabel
    if (loading) {
      submitLabel = t('loginLoading')
    } else if (view === 'register') {
      submitLabel = t('loginBtnSubmitRegister')
    } else {
      submitLabel = t('loginBtnSubmitLogin')
    }

    return (
      <form onSubmit={handleSubmit} className="login-form">
        <div className="form-group">
          <label htmlFor="email">{t('loginEmailLabel')}</label>
          <input
            type="email"
            id="email"
            placeholder="nom@entreprise.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="password">{t('loginPasswordLabel')}</label>
          <input
            type="password"
            id="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {view === 'login' && (
            <button
              type="button"
              className="btn-link forgot-link"
              onClick={() => { setForgotEmail(email); switchView('forgot') }}
            >
              Mot de passe oublié ?
            </button>
          )}
        </div>

        {view === 'register' && (
          <>
            <div className="form-group">
              <label htmlFor="tenantName">{t('loginOrgNameLabel')}</label>
              <input
                type="text"
                id="tenantName"
                placeholder="Acme Corp"
                value={tenantName}
                onChange={(e) => handleTenantNameChange(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="tenantSlug">{t('loginOrgSlugLabel')}</label>
              <input
                type="text"
                id="tenantSlug"
                placeholder="acme-corp"
                value={tenantSlug}
                onChange={(e) => setTenantSlug(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="role">{t('loginDesiredRole')}</label>
              <select
                id="role"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="viewer">{t('loginRoleViewer')}</option>
                <option value="analyst">{t('loginRoleAnalyst')}</option>
                <option value="admin">{t('loginRoleAdmin')}</option>
              </select>
            </div>
          </>
        )}

        <button type="submit" className="btn-primary login-btn" disabled={loading}>
          {submitLabel}
        </button>

        <div className="login-footer">
          <button
            type="button"
            className="btn-link"
            onClick={() => switchView(view === 'register' ? 'login' : 'register')}
          >
            {view === 'register' ? t('loginToggleHaveAccount') : t('loginToggleNewAccount')}
          </button>
        </div>
      </form>
    )
  }

  // ─── Titles per view ──────────────────────────────────────────────────
  const subtitles = {
    login: t('loginWelcomeConnect'),
    register: t('loginWelcomeJoin'),
    forgot: 'Réinitialisation du mot de passe',
    reset: 'Nouveau mot de passe',
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <div className="brand-logo">
            <span className="logo-icon">⚡</span>
            <h2>Log Analyzer AI</h2>
          </div>
          <p className="login-subtitle">{subtitles[view]}</p>
        </div>

        {error && <div className="login-error">{error}</div>}
        {infoMessage && (
          <div
            className="login-info"
            style={{
              backgroundColor: 'rgba(16, 185, 129, 0.15)',
              color: '#10b981',
              padding: '0.75rem',
              borderRadius: '6px',
              marginBottom: '1rem',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              fontSize: '0.9rem',
              lineHeight: '1.4',
            }}
          >
            {infoMessage}
          </div>
        )}

        {view === 'forgot' && renderForgotForm()}
        {view === 'reset' && renderResetForm()}
        {(view === 'login' || view === 'register') && renderLoginRegisterForm()}
      </div>
    </div>
  )
}
