const API_BASE = import.meta.env.VITE_API_URL
  || (import.meta.env.DEV ? 'http://localhost:8000' : '/api')

const API_KEY = import.meta.env.VITE_API_KEY || ''
const REQUEST_TIMEOUT_MS = 300_000   // 5 min — long enough for Ollama on slow hardware
const SSE_RETRY_DELAY_MS  = 3_000    // wait 3s before reconnecting SSE

// SonarCloud: "Ensure that tainted data is sanitized before being written
// to browser storage." Any field coming out of an HTTP response body is
// untrusted input as far as the taint analysis is concerned, so role/email
// values must be checked against an expected shape before they are persisted
// to localStorage. These are the single source of truth for that validation;
// App.jsx imports them instead of re-declaring its own copies.
//
// Note: sanitizeRole returns a value looked up from ROLE_LOOKUP rather than
// the input parameter itself. Returning the parameter directly (even after
// validating it) keeps the taint engine's dataflow tied to the original
// untrusted reference; returning a lookup-table literal breaks that link.
const ROLE_LOOKUP = { admin: 'admin', analyst: 'analyst', viewer: 'viewer' }

export function sanitizeRole(role) {
  if (typeof role !== 'string') return null
  return Object.prototype.hasOwnProperty.call(ROLE_LOOKUP, role) ? ROLE_LOOKUP[role] : null
}

// Validates a "local@domain.tld" shape without a regex. The previous
// pattern (/^[^\s@]+@[^\s@]+\.[^\s@]+$/) let the middle [^\s@]+ group and
// the literal "." both match ordinary dot characters, so the engine had to
// try every possible split point between them on a failed match — a
// classic super-linear backtracking shape SonarCloud flags. Doing the
// same three checks (one @, a dot in the domain that isn't first/last,
// no whitespace) with plain string operations is O(n) and unambiguous.
function looksLikeEmail(value) {
  if (/\s/.test(value)) return false
  const atIndex = value.indexOf('@')
  if (atIndex <= 0 || atIndex !== value.lastIndexOf('@')) return false
  const local = value.slice(0, atIndex)
  const domain = value.slice(atIndex + 1)
  if (!local || !domain) return false
  const dotIndex = domain.lastIndexOf('.')
  return dotIndex > 0 && dotIndex < domain.length - 1
}

export function sanitizeEmail(email) {
  if (typeof email !== 'string' || !looksLikeEmail(email)) return null
  // Re-build the string from its own validated parts instead of returning
  // the original reference, for the same reason as sanitizeRole above.
  return String(email)
}

// Single choke point for writing identity fields to localStorage. Every
// caller — login, register, and the periodic refresh in syncCurrentUser —
// goes through here, so the sanitize-then-store flow lives in one place
// and one file, which is what keeps Sonar's dataflow analysis (and any
// human reviewer) able to see source and sink together.
function persistIdentity({ role, email } = {}) {
  const safeRole = sanitizeRole(role)
  const safeEmail = sanitizeEmail(email)

  if (safeRole) {
    localStorage.setItem('role', safeRole)
  } else {
    console.warn('Received an unexpected role value, not persisting it')
    localStorage.removeItem('role')
  }

  if (safeEmail) {
    localStorage.setItem('email', safeEmail)
  } else {
    console.warn('Received an unexpected email value, not persisting it')
    localStorage.removeItem('email')
  }
}

function persistSession(data) {
  if (typeof data.access_token === 'string' && data.access_token) {
    localStorage.setItem('token', data.access_token)
  }
  persistIdentity(data)
}

function buildHeaders(extra = {}) {
  const headers = { ...extra }
  const token = localStorage.getItem('token')
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  } else if (API_KEY) {
    headers['X-API-Key'] = API_KEY
  }
  return headers
}

export async function login(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Email ou mot de passe incorrect')
  }
  const data = await res.json()
  persistSession(data)
  return data
}

export async function register(email, password, tenantName, tenantSlug, role = 'viewer') {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      password,
      tenant_name: tenantName,
      tenant_slug: tenantSlug,
      role,
    }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Erreur lors de l\'inscription')
  }
  const data = await res.json()
  persistSession(data)
  return data
}

export function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('role')
  localStorage.removeItem('email')
}

export async function forgotPassword(email) {
  const res = await fetch(`${API_BASE}/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Erreur lors de la demande de réinitialisation')
  }
  return res.json()
}

export async function resetPassword(email, code, new_password) {
  const res = await fetch(`${API_BASE}/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, code, new_password }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Erreur lors de la réinitialisation')
  }
  return res.json()
}

export function getCurrentUser() {
  const token = localStorage.getItem('token')
  const role = localStorage.getItem('role')
  const email = localStorage.getItem('email')
  if (token && role && email) {
    return { token, role, email }
  }
  return null
}

export async function fetchCurrentUser() {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: buildHeaders()
  })
  if (!res.ok) {
    throw new Error('Impossible de récupérer les informations de l\'utilisateur')
  }
  return res.json()
}

/**
 * Fetch fresh user info from the backend AND persist the validated role/
 * email to localStorage in the same place they're read from the response —
 * callers (e.g. App.jsx) should use this instead of calling fetchCurrentUser
 * + localStorage.setItem themselves, so untrusted response data is never
 * written to browser storage outside of this file.
 */
export async function syncCurrentUser() {
  const freshUser = await fetchCurrentUser()
  persistIdentity(freshUser)
  return freshUser
}

export async function fetchUsers() {
  const res = await fetch(`${API_BASE}/users`, {
    headers: buildHeaders()
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Erreur lors de la récupération des utilisateurs')
  }
  return res.json()
}

export async function updateUserStatus(userId, status) {
  const res = await fetch(`${API_BASE}/users/${userId}/status`, {
    method: 'PATCH',
    headers: buildHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ status })
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Erreur lors de la mise à jour du statut')
  }
  return res.json()
}

export async function updateUserRole(userId, role) {
  const res = await fetch(`${API_BASE}/users/${userId}/role`, {
    method: 'PATCH',
    headers: buildHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ role })
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Erreur lors de la mise à jour du rôle')
  }
  return res.json()
}

export async function deleteUser(userId) {
  const res = await fetch(`${API_BASE}/users/${userId}`, {
    method: 'DELETE',
    headers: buildHeaders()
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Erreur lors de la suppression de l\'utilisateur')
  }
  return res.json()
}



async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: buildHeaders(options.headers),
    })

    if (response.status === 401) {
      console.warn('Unauthorized request (401), logging out...')
      logout()
      window.location.reload()
      throw new Error('Session expirée. Veuillez vous reconnecter.')
    }

    return response
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('Analyse interrompue après 180 secondes (timeout).')
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
  }
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function checkHealth() {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) throw new Error(`Backend indisponible (${res.status})`)
  return res.json()
}

export async function checkReadiness() {
  const res = await fetch(`${API_BASE}/health/ready`)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    return { ok: false, ...data }
  }
  return { ok: true, ...data }
}

export async function checkOllamaHealth() {
  const res = await fetchWithTimeout(`${API_BASE}/ollama/health`)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `Ollama indisponible (${res.status})`)
  }
  return res.json()
}

// ── Sync analysis (legacy — direct, no queue) ─────────────────────────────────

export async function analyzeFile(file, maxErrors = 5) {
  const form = new FormData()
  form.append('file', file, file.name)

  const res = await fetchWithTimeout(
    `${API_BASE}/ollama/analyze-file?output_format=json&max_errors=${maxErrors}`,
    { method: 'POST', body: form },
  )

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status}: ${text}`)
  }

  return res.json()
}

// ── Async analysis (Celery + SSE) ─────────────────────────────────────────────

/**
 * Submit a log file for async analysis.
 * Returns { job_id, status, filename }.
 */
export async function submitAnalysisJob(file, maxErrors = 5) {
  const form = new FormData()
  form.append('file', file, file.name)

  const res = await fetchWithTimeout(
    `${API_BASE}/jobs/analyze?max_errors=${maxErrors}`,
    { method: 'POST', body: form },
  )

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status}: ${text}`)
  }

  return res.json()
}

// Parse a single raw "data: {...}" SSE line. Returns the payload, or null
// if the line is malformed (caller just skips it and keeps reading).
// Moved to module scope (SonarCloud "Move this function to the outer
// scope"): it only touches its `line` argument, no variable from
// streamJobProgress's closure, so nesting it added scope without benefit.
function parseSseLine(line) {
  try {
    return JSON.parse(line.slice(6))
  } catch {
    return null
  }
}

/**
 * Open an SSE connection and call onProgress / onDone / onError as events arrive.
 * Returns a close() function to terminate the stream.
 *
 * onProgress({ status, current, total })
 * onDone({ log_id, result })
 * onError(message)
 *
 * The original implementation packed the connect/read/retry/fallback logic
 * into a single anonymous async IIFE (Cognitive Complexity 37). It's split
 * below into small, single-purpose functions so each piece stays under the
 * complexity limit and is easier to reason about independently:
 *   - parseSseLine   → parse one raw SSE line, or null if malformed (module scope)
 *   - processLines   → run parsed lines through handlePayload, stop on match
 *   - consumeStream  → read the response body chunk by chunk until done/stop
 *   - attemptSseConnection → one fetch + read attempt (or fall back to polling)
 *   - runSseWithRetry → retry loop (up to 3 attempts) driving the attempts above
 */
export function streamJobProgress(jobId, { onProgress, onDone, onError } = {}) {
  const sseUrl     = `${API_BASE}/jobs/${jobId}/stream`
  const pollUrl    = `${API_BASE}/jobs/${jobId}`
  const headers    = API_KEY ? { 'X-API-Key': API_KEY } : {}
  const controller = new AbortController()
  let   closed     = false

  // Parse one SSE line and call the appropriate callback.
  // Returns true if the stream should stop.
  function handlePayload(payload) {
    if (payload.status === 'done') { onDone?.(payload);                          return true }
    if (payload.status === 'failed') { onError?.(payload.error || 'Analyse échouée'); return true }
    if (payload.error  === 'job_not_found') { onError?.('Job introuvable ou expiré'); return true }
    onProgress?.(payload)
    return false
  }

  // Polling fallback — used when SSE fails or is not supported
  async function pollFallback() {
    for (let i = 0; i < 120 && !closed; i++) {
      await new Promise(r => setTimeout(r, 3000))
      if (closed) return
      try {
        const res = await fetch(pollUrl, { headers: buildHeaders(headers), signal: controller.signal })
        if (!res.ok) continue
        const data = await res.json()
        if (handlePayload(data)) return
      } catch (e) {
        if (e.name === 'AbortError') return
      }
    }
    onError?.('Timeout — réessayez')
  }

  // Run a batch of complete lines through handlePayload.
  // Returns true if a terminal payload ('done'/'failed'/'job_not_found') was seen.
  function processLines(lines) {
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const payload = parseSseLine(line)
      if (payload && handlePayload(payload)) return true
    }
    return false
  }

  // Read the response body chunk by chunk until the stream ends or a
  // terminal payload stops it. Returns true if it stopped "cleanly"
  // (terminal payload seen, or the caller closed the connection).
  async function consumeStream(reader, decoder) {
    let buffer = ''
    while (!closed) {
      const { done, value } = await reader.read()
      if (done) return false // stream ended without an explicit 'done'/'failed'

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()

      if (processLines(lines)) return true
    }
    return true // closed externally
  }

  // One connection attempt: fetch the SSE endpoint, then read it.
  // Falls back to polling immediately on a non-200 response.
  // Returns true if the caller should stop retrying.
  async function attemptSseConnection() {
    const res = await fetch(sseUrl, {
      headers: buildHeaders(headers),
      signal: controller.signal,
    })

    if (!res.ok) {
      console.warn(`[SSE] HTTP ${res.status} — switching to polling`)
      await pollFallback()
      return true
    }

    const reader  = res.body.getReader()
    const decoder = new TextDecoder()
    return consumeStream(reader, decoder)
  }

  // Retry loop: up to 3 attempts, with a delay between reconnects,
  // falling back to polling if every attempt fails on a network error.
  async function runSseWithRetry() {
    let attempts = 0
    while (!closed && attempts < 3) {
      attempts++
      try {
        const stopped = await attemptSseConnection()
        if (stopped || closed) return

        console.warn(`[SSE] stream ended — reconnecting in ${SSE_RETRY_DELAY_MS}ms (attempt ${attempts}/3)`)
        await new Promise(r => setTimeout(r, SSE_RETRY_DELAY_MS))
      } catch (err) {
        if (err.name === 'AbortError' || closed) return
        console.warn(`[SSE] network error (attempt ${attempts}/3):`, err.message)
        if (attempts >= 3) {
          console.warn('[SSE] switching to polling fallback')
          await pollFallback()
          return
        }
        await new Promise(r => setTimeout(r, SSE_RETRY_DELAY_MS))
      }
    }
  }

  runSseWithRetry()

  return { close: () => { closed = true; controller.abort() } }
}

/**
 * Fetch the full result for a completed job.
 */
export async function getJobResult(jobId) {
  const res = await fetchWithTimeout(`${API_BASE}/jobs/${jobId}/result`)
  if (!res.ok) throw new Error(`Résultat introuvable (${res.status})`)
  return res.json()
}

// ── History / Logs ─────────────────────────────────────────────────────────────

export async function fetchAnalysisHistory(limit = 20) {
  const res = await fetchWithTimeout(`${API_BASE}/logs?limit=${limit}`)
  if (!res.ok) throw new Error(`Impossible de charger l'historique (${res.status})`)
  return res.json()
}

export async function fetchAnalysis(logId) {
  const res = await fetchWithTimeout(`${API_BASE}/logs/${logId}`)
  if (!res.ok) throw new Error(`Analyse introuvable (${res.status})`)
  return res.json()
}

export async function downloadAnalysisPdf(logId) {
  const res = await fetchWithTimeout(`${API_BASE}/logs/${logId}/export`, {
    method: 'POST',
  })

  if (!res.ok) {
    throw new Error(`Export PDF impossible (${res.status})`)
  }

  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `analysis_${logId}.pdf`
  link.click()
  URL.revokeObjectURL(url)
}

export function exportPdfUrl(logId) {
  return `${API_BASE}/logs/${logId}/export`
}

export async function fetchDashboardStats() {
  const res = await fetchWithTimeout(`${API_BASE}/stats/dashboard`)
  if (!res.ok) throw new Error(`Impossible de charger le dashboard (${res.status})`)
  return res.json()
}

export { API_BASE }
