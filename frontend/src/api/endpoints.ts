// Wrappers tipados de los endpoints del contrato (openapi.yml).
// Cada wrapper delega en el cliente único `solicitar` y devuelve la respuesta
// con el status real (200/201) y el cuerpo tipado desde schema.ts.
import { solicitar, type Respuesta } from './client'
import type {
  ConsultaQuery,
  CuerpoJson,
  Exito200,
  Exito201,
  OpCercanos,
  OpEstadoOperativo,
  OpEstimacion,
  OpGeocodificacion,
  OpLiveness,
  OpReadiness,
  OpReserva,
  OpUbicacion,
} from './types'

// --- Salud (sin autenticación) ---

/** GET /health/live — 200 si el proceso está activo. */
export function consultarLiveness(): Promise<Respuesta<Exito200<OpLiveness>>> {
  return solicitar({ metodo: 'GET', ruta: '/health/live', sinAuth: true })
}

/** GET /health/ready — 200 READY o 503 con Retry-After. */
export function consultarReadiness(): Promise<Respuesta<Exito200<OpReadiness>>> {
  return solicitar({ metodo: 'GET', ruta: '/health/ready', sinAuth: true })
}

// --- Negocio (requieren Authorization) ---

/** PUT /api/v1/conductores/{id}/ubicacion — 200 reemplazo / 201 primer registro. */
export function actualizarUbicacion(
  conductorId: string,
  cuerpo: CuerpoJson<OpUbicacion>,
): Promise<Respuesta<Exito200<OpUbicacion> | Exito201<OpUbicacion>>> {
  return solicitar({
    metodo: 'PUT',
    ruta: `/api/v1/conductores/${conductorId}/ubicacion`,
    cuerpo,
  })
}

/** PUT /api/v1/conductores/{id}/estado-operativo */
export function actualizarEstadoOperativo(
  conductorId: string,
  cuerpo: CuerpoJson<OpEstadoOperativo>,
): Promise<Respuesta<Exito200<OpEstadoOperativo> | Exito201<OpEstadoOperativo>>> {
  return solicitar({
    metodo: 'PUT',
    ruta: `/api/v1/conductores/${conductorId}/estado-operativo`,
    cuerpo,
  })
}

/** GET /api/v1/conductores/cercanos — 200 con lista posiblemente vacía. */
export function buscarCercanos(
  query: ConsultaQuery<OpCercanos>,
): Promise<Respuesta<Exito200<OpCercanos>>> {
  return solicitar({ metodo: 'GET', ruta: '/api/v1/conductores/cercanos', query })
}

/**
 * POST /api/v1/conductores/{id}/reserva — 200 liberación/repetición /
 * 201 reserva creada. Requiere Idempotency-Key única por operación.
 */
export function cambiarReservaTemporal(
  conductorId: string,
  cuerpo: CuerpoJson<OpReserva>,
  idempotencyKey: string,
): Promise<Respuesta<Exito200<OpReserva> | Exito201<OpReserva>>> {
  return solicitar({
    metodo: 'POST',
    ruta: `/api/v1/conductores/${conductorId}/reserva`,
    cuerpo,
    headersExtra: { 'Idempotency-Key': idempotencyKey },
  })
}

/** GET /api/v1/rutas/estimacion */
export function estimarRuta(
  query: ConsultaQuery<OpEstimacion>,
): Promise<Respuesta<Exito200<OpEstimacion>>> {
  return solicitar({ metodo: 'GET', ruta: '/api/v1/rutas/estimacion', query })
}

/** POST /api/v1/geocodificaciones — 200 con coincidencias posiblemente vacías. */
export function geocodificarDireccion(
  cuerpo: CuerpoJson<OpGeocodificacion>,
): Promise<Respuesta<Exito200<OpGeocodificacion>>> {
  return solicitar({ metodo: 'POST', ruta: '/api/v1/geocodificaciones', cuerpo })
}
