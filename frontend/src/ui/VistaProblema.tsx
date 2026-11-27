// Muestra un problem+json tal cual llega: siempre el status HTTP y el `code`
// recibido, sin ramificar sobre valores exactos de `code` (la guía es el status).
import type { ApiProblem } from '@/api/types'

export function claseBadge(status: number): string {
  if (status >= 200 && status < 300) return 'badge-ok'
  if (status >= 400) return 'badge-error'
  return 'badge-info'
}

export function VistaProblema({ problem }: { problem: ApiProblem }) {
  const extra = problem as Record<string, unknown>
  return (
    <div className="problema">
      <p>
        <span className={`badge ${claseBadge(problem.status)}`}>{problem.status}</span>{' '}
        <strong>{problem.title}</strong>
        {problem.code !== undefined && (
          <>
            {' · '}
            <code className="codigo">{problem.code}</code>
          </>
        )}
      </p>
      <p>{problem.detail}</p>
      <p className="meta">
        instance: <code>{problem.instance}</code>
        {problem.trace_id !== undefined && (
          <>
            {' · '}trace_id: <code>{problem.trace_id}</code>
          </>
        )}
        {typeof extra.retry_after === 'number' && <> · retry_after: {extra.retry_after} s</>}
      </p>
      {problem.invalid_params !== undefined && problem.invalid_params.length > 0 && (
        <ul className="invalid-params">
          {problem.invalid_params.map((p) => (
            <li key={p.name}>
              <code>{p.name}</code>: {p.reason}
            </li>
          ))}
        </ul>
      )}
      <details>
        <summary>JSON completo</summary>
        <pre>{JSON.stringify(problem, null, 2)}</pre>
      </details>
    </div>
  )
}
