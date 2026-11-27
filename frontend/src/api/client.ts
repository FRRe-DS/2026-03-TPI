// Cliente HTTP único del simulador (Etapa 1b).
//
// Todas las llamadas a la API pasan por `solicitar`:
//  - envía `Authorization: Bearer …` con el token en memoria (salvo /health),
//  - genera y envía `X-Request-Id` (patrón ^[A-Za-z0-9._-]{1,128}$ del contrato),
//  - convierte una respuesta `application/problem+json` en `ApiError`,
//  - devuelve el status HTTP real (distinción 200/201 para el llamador),
//  - lee el header `Retry-After` (segundos o fecha HTTP),
//  - registra la entrada del panel de logs SIN query (RF-4.7).
import { avisoUrlBase, getConfigApi } from '@/config/apiConfig'
import { agregarEntrada } from '@/logs/requestLog'
import { rutaSinQuery } from '@/logs/sanitize'
import { ApiError } from './problem'
import type { ApiProblem } from './types'

export type MetodoHttp = 'GET' | 'POST' | 'PUT'

/** Respuesta exitosa. `status` es el status real: permite distinguir 200 de 201. */
export interface Respuesta<Cuerpo> {
  status: number
  /** Cuerpo JSON parseado; null si la respuesta vino vacía o sin JSON válido. */
  cuerpo: Cuerpo | null
  /** X-Request-Id de la respuesta (o el enviado si el servidor no lo devolvió). */
  requestId: string | null
}

export interface OpcionesSolicitud {
  metodo: MetodoHttp
  /** Ruta relativa (p. ej. /api/v1/conductores/cercanos); la query va en `query`. */
  ruta: string
  query?: Record<string, string | number | undefined>
  cuerpo?: unknown
  /** Headers extra (Idempotency-Key, X-Request-Id ya válido, …). */
  headersExtra?: Record<string, string>
  /** Endpoints de salud: no envían Authorization. */
  sinAuth?: boolean
}

/** Patrón del header X-Request-Id según openapi.yml. */
const PATRON_REQUEST_ID = /^[A-Za-z0-9._-]{1,128}$/

function generarRequestId(): string {
  // UUID v4: solo hex y guiones → cumple el patrón del contrato.
  return crypto.randomUUID()
}

function requestIdValido(valor: string | undefined): string | null {
  return valor !== undefined && PATRON_REQUEST_ID.test(valor) ? valor : null
}

/** Retry-After: delta-seconds o fecha HTTP; cualquier otra cosa se ignora. */
function leerRetryAfter(resp: Response): number | null {
  const crudo = resp.headers.get('Retry-After')
  if (crudo === null || crudo.trim() === '') return null
  const segundos = Number(crudo)
  if (Number.isFinite(segundos)) return segundos
  const fecha = Date.parse(crudo)
  if (!Number.isNaN(fecha)) return Math.max(0, Math.round((fecha - Date.now()) / 1000))
  return null
}

function parsearProblema(texto: string): ApiProblem | null {
  try {
    const objeto: unknown = JSON.parse(texto)
    if (objeto !== null && typeof objeto === 'object') return objeto as ApiProblem
  } catch {
    // cuerpo no JSON: se maneja como problem null
  }
  return null
}

export async function solicitar<Cuerpo>(opc: OpcionesSolicitud): Promise<Respuesta<Cuerpo>> {
  const { token, urlBase } = getConfigApi()

  // URL base sin esquema http(s)://: no se intenta la llamada. El aviso ya
  // está visible en el campo de la UI; acá se aborta antes de todo (ni fetch
  // ni entrada de log, porque no hubo request).
  const aviso = avisoUrlBase(urlBase)
  if (aviso !== null) {
    throw new ApiError({ status: 0, message: aviso })
  }

  const requestId =
    requestIdValido(opc.headersExtra?.['X-Request-Id']) ?? generarRequestId()

  // Arma la URL final (con query para el fetch; el log NUNCA la ve, RF-4.7).
  const params = new URLSearchParams()
  for (const [clave, valor] of Object.entries(opc.query ?? {})) {
    if (valor !== undefined) params.set(clave, String(valor))
  }
  const qs = params.toString()
  const rutaConQuery = opc.ruta + (qs ? `?${qs}` : '')
  const base = urlBase.trim().replace(/\/+$/, '')
  // base vacía → ruta relativa → el proxy de Vite (Prism por defecto).
  const destino = base + rutaConQuery

  const headers: Record<string, string> = {
    Accept: 'application/json, application/problem+json',
    ...opc.headersExtra,
    // Siempre el último: valor validado contra el patrón o recién generado.
    'X-Request-Id': requestId,
  }
  if (opc.cuerpo !== undefined) headers['Content-Type'] = 'application/json'
  if (!opc.sinAuth && token.trim() !== '') {
    headers['Authorization'] = `Bearer ${token.trim()}`
  }

  const inicio = performance.now()
  let status: number | null = null
  let problem: ApiProblem | null = null
  let retryAfter: number | null = null
  let requestIdRespuesta: string | null = null

  try {
    const resp = await fetch(destino, {
      method: opc.metodo,
      headers,
      body: opc.cuerpo !== undefined ? JSON.stringify(opc.cuerpo) : undefined,
    })
    status = resp.status
    requestIdRespuesta = resp.headers.get('X-Request-Id') ?? requestId
    retryAfter = leerRetryAfter(resp)

    const tipoContenido = resp.headers.get('Content-Type') ?? ''
    const texto = await resp.text()

    if (tipoContenido.includes('application/problem+json')) {
      problem = parsearProblema(texto)
      if (retryAfter === null && typeof problem?.retry_after === 'number') {
        retryAfter = problem.retry_after
      }
      throw new ApiError({
        status: resp.status,
        message: problem?.detail ?? problem?.title ?? `HTTP ${resp.status}`,
        problem,
        requestId: requestIdRespuesta,
        retryAfter,
      })
    }

    if (!resp.ok) {
      throw new ApiError({
        status: resp.status,
        message: `HTTP ${resp.status} sin problem+json`,
        problem: null,
        requestId: requestIdRespuesta,
        retryAfter,
      })
    }

    let cuerpo: Cuerpo | null = null
    if (texto !== '') {
      try {
        cuerpo = JSON.parse(texto) as Cuerpo
      } catch {
        cuerpo = null
      }
    }
    return { status: resp.status, cuerpo, requestId: requestIdRespuesta }
  } catch (e) {
    if (e instanceof ApiError) throw e
    // Fallo de red / CORS / URL inválida: sin respuesta.
    throw new ApiError({
      status: 0,
      message: e instanceof Error ? e.message : String(e),
      problem: null,
      requestId,
      retryAfter: null,
    })
  } finally {
    // RF-4.7: solo la ruta, nunca la query (contiene coordenadas).
    agregarEntrada({
      id: crypto.randomUUID(),
      momento: new Date().toISOString(),
      metodo: opc.metodo,
      ruta: rutaSinQuery(opc.ruta),
      status,
      requestId: requestIdRespuesta ?? requestId,
      duracionMs: Math.round(performance.now() - inicio),
      problem,
      retryAfter,
    })
  }
}
