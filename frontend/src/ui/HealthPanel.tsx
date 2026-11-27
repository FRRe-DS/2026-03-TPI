// Panel de salud (Etapa 1b): consulta GET /health/live y GET /health/ready.
// Ambos endpoints no requieren token. Se muestra siempre el status HTTP y,
// si hay error, el problem+json completo (con el `code` tal cual llega).
import { useState } from 'react'
import { consultarLiveness, consultarReadiness } from '@/api/endpoints'
import { ApiError, esApiError } from '@/api/problem'
import { claseBadge, VistaProblema } from './VistaProblema'

interface Exito {
  status: number
  cuerpo: unknown
  requestId: string | null
  duracionMs: number
}

interface Estado {
  cargando: boolean
  exito: Exito | null
  error: ApiError | null
}

const ESTADO_INICIAL: Estado = { cargando: false, exito: null, error: null }

function useConsulta(
  consulta: () => Promise<{ status: number; cuerpo: unknown; requestId: string | null }>,
) {
  const [estado, setEstado] = useState<Estado>(ESTADO_INICIAL)

  async function ejecutar(): Promise<void> {
    setEstado({ cargando: true, exito: null, error: null })
    const inicio = performance.now()
    try {
      const respuesta = await consulta()
      setEstado({
        cargando: false,
        exito: { ...respuesta, duracionMs: Math.round(performance.now() - inicio) },
        error: null,
      })
    } catch (e) {
      setEstado({
        cargando: false,
        exito: null,
        error: esApiError(e)
          ? e
          : new ApiError({ status: 0, message: e instanceof Error ? e.message : String(e) }),
      })
    }
  }

  return { estado, ejecutar }
}

function ResultadoSalud({ estado }: { estado: Estado }) {
  if (estado.cargando) return <p className="meta">Consultando…</p>

  if (estado.error !== null) {
    const { error } = estado
    return (
      <div className="resultado">
        <p>
          <span className={`badge ${error.status === 0 ? 'badge-error' : claseBadge(error.status)}`}>
            {error.status === 0 ? 'sin respuesta' : error.status}
          </span>{' '}
          {error.message}
        </p>
        {error.problem !== null && <VistaProblema problem={error.problem} />}
        {error.retryAfter !== null && <p className="meta">Retry-After: {error.retryAfter} s</p>}
        {error.requestId !== null && (
          <p className="meta">
            X-Request-Id: <code>{error.requestId}</code>
          </p>
        )}
      </div>
    )
  }

  if (estado.exito !== null) {
    const { status, cuerpo, requestId, duracionMs } = estado.exito
    return (
      <div className="resultado">
        <p>
          <span className={`badge ${claseBadge(status)}`}>{status}</span>{' '}
          {cuerpo === null ? '(sin cuerpo)' : JSON.stringify(cuerpo)}
        </p>
        <p className="meta">
          X-Request-Id: <code>{requestId ?? '—'}</code> · {duracionMs} ms
        </p>
      </div>
    )
  }

  return null
}

export function HealthPanel() {
  const live = useConsulta(consultarLiveness)
  const ready = useConsulta(consultarReadiness)

  return (
    <section className="panel">
      <h2>Panel de salud</h2>
      <p className="nota">
        <code>GET /health/live</code> y <code>GET /health/ready</code> no requieren token.
      </p>
      <div className="salud-fila">
        <div className="salud-item">
          <h3>
            Liveness <code>GET /health/live</code>
          </h3>
          <button onClick={live.ejecutar} disabled={live.estado.cargando}>
            {live.estado.cargando ? 'Consultando…' : 'Consultar'}
          </button>
          <ResultadoSalud estado={live.estado} />
        </div>
        <div className="salud-item">
          <h3>
            Readiness <code>GET /health/ready</code>
          </h3>
          <button onClick={ready.ejecutar} disabled={ready.estado.cargando}>
            {ready.estado.cargando ? 'Consultando…' : 'Consultar'}
          </button>
          <ResultadoSalud estado={ready.estado} />
        </div>
      </div>
    </section>
  )
}
