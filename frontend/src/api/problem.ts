// Error tipado del cliente HTTP: siempre nace de una respuesta problem+json
// (o de un fallo de red, con status 0). La UI se guía por el status HTTP y
// muestra el `code` tal cual llega, sin ramificar sobre valores exactos.
import type { ApiProblem } from './types'

export class ApiError extends Error {
  /** Status HTTP de la respuesta; 0 si no hubo respuesta (red/CORS). */
  readonly status: number
  /** Cuerpo problem+json parseado; null si la respuesta no trajo un problema. */
  readonly problem: ApiProblem | null
  /** X-Request-Id de la respuesta (o el enviado, si el servidor no lo devolvió). */
  readonly requestId: string | null
  /** Segundos de espera sugeridos (header Retry-After o extensión retry_after). */
  readonly retryAfter: number | null

  constructor(opts: {
    status: number
    message: string
    problem?: ApiProblem | null
    requestId?: string | null
    retryAfter?: number | null
  }) {
    super(opts.message)
    this.name = 'ApiError'
    this.status = opts.status
    this.problem = opts.problem ?? null
    this.requestId = opts.requestId ?? null
    this.retryAfter = opts.retryAfter ?? null
  }

  /** `code` del problem+json tal cual llega del backend (puede ser undefined). */
  get code(): string | undefined {
    return this.problem?.code
  }
}

export function esApiError(e: unknown): e is ApiError {
  return e instanceof ApiError
}
