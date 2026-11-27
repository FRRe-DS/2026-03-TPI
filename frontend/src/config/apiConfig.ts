// Store en memoria de la configuración de conexión (token y URL base).
// Restricción: el token NUNCA se persiste (sin localStorage/sessionStorage);
// al recargar la página se pierde y hay que pegarlo de nuevo.
import { useSyncExternalStore } from 'react'

export interface ConfigApi {
  /** JWT Bearer; vacío = no enviar Authorization. */
  token: string
  /** URL base del API; vacío = usar el proxy de Vite (mismo origen). */
  urlBase: string
}

let config: ConfigApi = { token: '', urlBase: '' }
const listeners = new Set<() => void>()

export function getConfigApi(): ConfigApi {
  return config
}

export function setConfigApi(parcial: Partial<ConfigApi>): void {
  config = { ...config, ...parcial }
  listeners.forEach((l) => l())
}

export function suscribirConfigApi(callback: () => void): () => void {
  listeners.add(callback)
  return () => {
    listeners.delete(callback)
  }
}

export function useConfigApi(): ConfigApi {
  return useSyncExternalStore(suscribirConfigApi, getConfigApi, getConfigApi)
}

/**
 * Aviso de configuración de la URL base: `null` si es válida (vacía → proxy de
 * Vite, o con esquema `http://` / `https://`); si no, el mensaje a mostrar.
 * La UI lo muestra en el campo y el cliente HTTP se niega a hacer la llamada.
 */
export function avisoUrlBase(urlBase: string): string | null {
  const limpia = urlBase.trim()
  if (limpia === '' || /^https?:\/\//i.test(limpia)) return null
  return 'la URL debe empezar con http:// o https://'
}
