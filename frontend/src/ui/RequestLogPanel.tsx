// Panel de logs (RNF-14): cada request emitido por el cliente HTTP aparece
// acá. RF-4.7: las rutas se registran SIN query string → nunca hay
// coordenadas en el log. El status y el `code` se muestran tal cual llegan.
import { useSyncExternalStore } from 'react'
import { getSnapshotLogs, limpiarLogs, suscribirLogs } from '@/logs/requestLog'
import { claseBadge, VistaProblema } from './VistaProblema'

function horaLocal(momento: string): string {
  return new Date(momento).toLocaleTimeString('es-AR', { hour12: false })
}

export function RequestLogPanel() {
  const entradas = useSyncExternalStore(suscribirLogs, getSnapshotLogs, getSnapshotLogs)

  return (
    <section className="panel">
      <div className="panel-cabecera">
        <h2>Panel de logs ({entradas.length})</h2>
        <button onClick={limpiarLogs} disabled={entradas.length === 0}>
          Limpiar
        </button>
      </div>
      <p className="nota">
        RF-4.7: se registra solo la ruta, sin query string — nunca aparecen coordenadas en el
        log. Máximo 200 entradas en memoria.
      </p>

      {entradas.length === 0 ? (
        <p className="meta">Todavía no se registraron requests.</p>
      ) : (
        <div className="log-tabla-envoltorio">
          <table className="log-tabla">
            <thead>
              <tr>
                <th>Hora</th>
                <th>Método</th>
                <th>Ruta</th>
                <th>Status</th>
                <th>X-Request-Id</th>
                <th>Duración</th>
                <th>code</th>
                <th>Retry-After</th>
                <th>Detalle</th>
              </tr>
            </thead>
            <tbody>
              {entradas.map((e) => (
                <tr key={e.id}>
                  <td>{horaLocal(e.momento)}</td>
                  <td>{e.metodo}</td>
                  <td className="ruta">
                    <code>{e.ruta}</code>
                  </td>
                  <td>
                    {e.status === null ? (
                      <span className="badge badge-error">sin respuesta</span>
                    ) : (
                      <span className={`badge ${claseBadge(e.status)}`}>{e.status}</span>
                    )}
                  </td>
                  <td>
                    <code>{e.requestId ?? '—'}</code>
                  </td>
                  <td>{e.duracionMs} ms</td>
                  <td>{e.problem?.code !== undefined ? <code>{e.problem.code}</code> : '—'}</td>
                  <td>{e.retryAfter !== null ? `${e.retryAfter} s` : '—'}</td>
                  <td>
                    {e.problem !== null ? (
                      <details>
                        <summary>ver</summary>
                        <VistaProblema problem={e.problem} />
                      </details>
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
