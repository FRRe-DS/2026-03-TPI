// Store en memoria del panel de logs (RNF-14). Cada request emitido por el
// cliente HTTP agrega una entrada aquí; el panel se suscribe con
// useSyncExternalStore. La ruta siempre entra ya sanitizada (sin query).
import type { ApiProblem } from '@/api/types'

export interface EntradaLog {
  id: string
  /** Timestamp RFC 3339 UTC. */
  momento: string
  metodo: string
  /** Ruta sin query string (privacidad RF-4.7). */
  ruta: string
  /** Status HTTP; null si no hubo respuesta (fallo de red). */
  status: number | null
  requestId: string | null
  duracionMs: number
  problem: ApiProblem | null
  retryAfter: number | null
}

const MAX_ENTRADAS = 200

let entradas: EntradaLog[] = []
const listeners = new Set<() => void>()

export function agregarEntrada(entrada: EntradaLog): void {
  entradas = [entrada, ...entradas].slice(0, MAX_ENTRADAS)
  listeners.forEach((l) => l())
}

export function limpiarLogs(): void {
  entradas = []
  listeners.forEach((l) => l())
}

export function getSnapshotLogs(): EntradaLog[] {
  return entradas
}

export function suscribirLogs(callback: () => void): () => void {
  listeners.add(callback)
  return () => {
    listeners.delete(callback)
  }
}
