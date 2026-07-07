import { useEffect, useState } from 'react'
import { checkHealth, checkReadiness } from '../api'

export default function HealthStatus() {
  const [backend, setBackend] = useState(null)
  const [readiness, setReadiness] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const h = await checkHealth()
        if (!cancelled) setBackend({ ok: true, ...h })
      } catch {
        if (!cancelled) setBackend({ ok: false })
      }

      try {
        const r = await checkReadiness()
        if (!cancelled) setReadiness(r)
      } catch (err) {
        if (!cancelled) setReadiness({ ok: false, error: String(err) })
      }
    }

    poll()
    const id = setInterval(poll, 30000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  const dbOk = readiness?.database?.ok
  const ollamaOk = readiness?.ok && readiness?.ollama?.ollama_running && readiness?.ollama?.model_available

  return (
    <div className="health-bar">
      <span className={`health-pill ${backend?.ok ? 'ok' : 'ko'}`}>
        Backend {backend?.ok ? 'OK' : '...'}
      </span>
      <span className={`health-pill ${dbOk ? 'ok' : 'ko'}`}>
        DB {dbOk ? 'OK' : '...'}
      </span>
      <span className={`health-pill ${ollamaOk ? 'ok' : 'ko'}`}>
        Ollama {ollamaOk ? 'OK' : '...'}
      </span>
      {readiness?.ollama?.model_available && (
        <span className="health-model">{readiness.ollama.required_model || 'llama3.2'}</span>
      )}
    </div>
  )
}
