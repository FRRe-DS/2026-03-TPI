// Tipos derivados del contrato generado (schema.ts). Nada se define a mano:
// todo se extrae de openapi.yml a través de openapi-typescript.
import type { components, operations } from './generated/schema'

// Esquema de error del contrato (RFC 7807 con extensiones).
export type ApiProblem = components['schemas']['Problema']

// Identificador canónico (UUID) del contrato.
export type Identificador = components['schemas']['Identificador']

export type TipoVehiculo = components['schemas']['TipoVehiculo']

// --- Helpers de extracción a partir de `operations` ---

type JsonDe<R> = R extends { content: { 'application/json': infer J } } ? J : never

/** Body JSON de la respuesta 200 de una operación. */
export type Exito200<Op> = Op extends { responses: infer R }
  ? R extends { 200: infer Resp }
    ? JsonDe<Resp>
    : never
  : never

/** Body JSON de la respuesta 201 de una operación (never si no la tiene). */
export type Exito201<Op> = Op extends { responses: infer R }
  ? R extends { 201: infer Resp }
    ? JsonDe<Resp>
    : never
  : never

/** Body JSON del request de una operación (never si no tiene body). */
export type CuerpoJson<Op> = Op extends { requestBody: infer RB }
  ? RB extends { content: { 'application/json': infer B } }
    ? B
    : never
  : never

/** Parámetros de query de una operación (never si no los tiene). */
export type ConsultaQuery<Op> = Op extends { parameters: infer P }
  ? P extends { query: infer Q }
    ? Q
    : never
  : never

// Alias de operaciones usadas por los wrappers (endpoints.ts).
export type OpUbicacion = operations['actualizarUbicacionConductor']
export type OpEstadoOperativo = operations['actualizarEstadoOperativo']
export type OpCercanos = operations['buscarConductoresCercanos']
export type OpReserva = operations['cambiarReservaTemporalConductor']
export type OpEstimacion = operations['estimarRuta']
export type OpGeocodificacion = operations['geocodificarDireccion']
export type OpLiveness = operations['consultarLiveness']
export type OpReadiness = operations['consultarReadiness']
