# Backlog técnico — Módulo 4

Este backlog desglosa la arquitectura de [plan.md](./plan.md) en unidades de implementación pequeñas. Cada estimación es de **20–30 minutos** de trabajo enfocado e incluye una verificación PyTest. No ejecutar integraciones contra servicios reales en las pruebas unitarias.

## 0. Acuerdos y preparación

- [ ] **20 min — Confirmar contratos pendientes con M3 y M1.** Registrar endpoint/esquema de elegibilidad, estados, scopes, orden/event IDs de eventos y autenticación en una decisión de integración. **Prueba/criterio:** revisión de contrato/API examples aprobada antes de codificar clientes.
- [ ] **20 min — Acordar TTL, radio y reserva con M5.** Resolver TTL fijo de GPS (30 s), default/expansión del radio, TTL de reserva y eventos que causan liberación. **Prueba/criterio:** casos límite y valores aprobados reflejados en configuración/contrato.
- [ ] **20 min — Acordar integración asíncrona con M7.** Elegir push/outbox o consulta pull, identificador correlacionado, reintentos y deduplicación; no asumir que el GET actual satisface el push de la constitución. **Prueba/criterio:** contrato de integración revisado y trazable a OpenAPI actualizado/aprobado.
- [ ] **20 min — Definir proveedor de mapas y fallback.** Seleccionar geocoder/router, límites, formato, fuente de ETA, timeout y fallback local permitido. **Prueba/criterio:** escenarios de éxito, ambigüedad, timeout y no disponibilidad definidos.
- [x] **20 min — Aprobar almacén efímero GPS.** Seleccionar Redis con expiración nativa de 30 s para el despliegue. **Criterio:** decisión acordada e integrada en Compose.
- [ ] **20 min — Aprobar cobertura geográfica.** Acordar geometría autorizada Chaco/Corrientes. **Prueba/criterio:** fixtures geográficos con límites aprobados.

## 1. Fundamentos de aplicación y contratos

- [x] **25 min — Crear configuración tipada de M4.** Definir TTL GPS, radio/límite, expiración de reservas y timeouts por dependencia mediante settings, sin secretos por defecto. **PyTest:** carga de defaults aprobados, overrides y validación de valores inválidos.
- [x] **25 min — Separar bootstrap y ciclo de vida FastAPI.** Inicializar routers, clientes y repositorios en lifespan y evitar creación de tablas en importación. **PyTest:** app inicia/cierra dependencias y los módulos se pueden importar sin conexión DB.
- [x] **25 min — Implementar middleware `X-Request-Id`.** Aceptar ID válido, generar uno ante ausencia/formato inválido y propagarlo al contexto. **PyTest:** request válido, ausente e inválido.
- [x] **25 min — Implementar respuesta Problem Details común.** Mapear errores de validación, dominio y dependencia a `application/problem+json` con status coincidente y sin datos internos. **PyTest:** snapshots/campos requeridos por varios status.
- [x] **25 min — Definir enums y schemas de ubicación.** Implementar DTOs compatibles con `ActualizarUbicacion` y `UbicacionRegistrada`. **PyTest:** límites WGS 84, timestamp UTC y rechazo de propiedades no permitidas.
- [x] **25 min — Definir schemas de estado, candidato y reserva.** Implementar DTOs Pydantic de `EstadoOperativo`, `Candidato`, `CambioReservaTemporal` y respuestas. **PyTest:** campos obligatorios, enums y que `Candidato` no admita latitud/longitud.
- [x] **25 min — Definir schemas de ruta, geocodificación y salud.** Implementar respuestas conforme a OpenAPI. **PyTest:** unidades/rangos, fuente permitida y coincidencias vacías/ambiguas.
- [x] **25 min — Añadir registro estructurado y redacción de datos sensibles.** Configurar correlación y eliminar query strings sensibles, coordenadas y credenciales. **PyTest:** capturar logs y verificar ausencia de GPS/token/URL completa.

## 2. Persistencia y repositorios

- [x] **25 min — Diseñar modelos SQLAlchemy persistentes de estado operativo.** Crear tabla/proyección con UUID, connected/available y timestamps sin guardar GPS. **PyTest:** constraints, defaults UTC y serialización.
- [x] **25 min — Diseñar modelo de reserva temporal.** Añadir titular, estado, marcas de tiempo y expiración con índice/restricción para reserva activa única. **PyTest:** migración de ida/vuelta y restricción de unicidad.
- [x] **25 min — Diseñar almacenamiento de idempotencia.** Persistir operación, actor, key, hash, status/respuesta y vencimiento con clave única. **PyTest:** duplicado de key y comportamiento de transacción.
- [x] **25 min — Crear migración Alembic de las tablas nuevas.** No modificar destructivamente las migraciones existentes; documentar incompatibilidad de identificadores legacy. **PyTest:** upgrade/downgrade en DB de prueba.
- [x] **25 min — Definir interfaz de repositorio efímero de ubicación.** Separar interfaz de servicio del backend; soportar upsert condicional, consulta vigente y expiración. **PyTest:** integración Redis verifica interfaz y semántica de vigencia.
- [x] **25 min — Implementar backend efímero elegido (Redis).** Conectar el adapter acordado, añadir servicio Redis saludable en Compose y aplicar expiración nativa de 30 s. **PyTest:** ubicación desaparece o deja de estar vigente al vencer TTL; orden cronológico e idempotencia atómicos.
- [x] **25 min — Implementar repositorio operacional y transaccional.** Encapsular lecturas/escrituras y rollback, sin operaciones ORM dentro de routers. **PyTest:** persistencia y rollback ante excepción.

## 3. Ubicación y disponibilidad

- [ ] **25 min — Implementar validación de coordenadas y timestamp.** Validar WGS 84, UTC y timestamp aceptable con reloj inyectable. **PyTest:** extremos, valores fuera de rango y timestamp inválido.
- [ ] **25 min — Implementar escritura cronológica de ubicación.** Impedir que actualización anterior pise una posterior; repetición idéntica es idempotente. **PyTest:** anterior, igual idéntica y actualización posterior.
- [ ] **25 min — Implementar conflicto de timestamp duplicado.** Mismo timestamp y coordenadas distintas produce error de dominio HTTP `409`. **PyTest:** aserción de status, Problem Details y no modificación del dato guardado.
- [ ] **25 min — Implementar servicio de vigencia TTL GPS.** Calcular expiración desde recepción y comprobar el umbral estricto de 30 s al consultar. **PyTest:** reloj congelado antes, justo al vencer y después.
- [ ] **25 min — Publicar `POST /api/v1/ubicaciones`.** Conectar schema, auth, servicio, códigos `200`/`201` y errores contratados. **PyTest:** endpoint de creación/actualización, headers y payload de respuesta sin coordenadas innecesarias.
- [ ] **25 min — Implementar normalización del estado operativo.** Forzar `available=false` cuando `connected=false` sin modificar GPS/habilitación. **PyTest:** combinaciones connected/available.
- [ ] **25 min — Implementar deduplicación y orden de eventos M3.** Aplicar event ID/timestamp si el contrato acordado los incorpora y devolver error acordado para conflicto. **PyTest:** repetición idéntica, mismo ID con cuerpo distinto y evento fuera de orden.
- [ ] **25 min — Publicar `POST /api/v1/conductores/{id}/estado-operativo`.** Conectar router a servicio y repositorio con respuestas `200`/`201`. **PyTest:** primera proyección, actualización, esquema de respuesta y correlación.

## 4. Integración M3 y proximidad M5

- [ ] **25 min — Crear cliente HTTP asíncrono de M3.** Aplicar auth de servicio, timeouts finitos, propagación de request ID y cierre en lifespan. **PyTest:** transporte simulado, timeout, respuesta inválida y cierre.
- [ ] **25 min — Mapear respuesta de elegibilidad de M3.** Convertir el contrato acordado a tipos internos sin asumir campos ausentes ni solicitar listados completos. **PyTest:** habilitación `APPROVED`, estados no elegibles, vehículo y respuesta incompleta.
- [ ] **25 min — Implementar regla fail-closed de M3.** Convertir timeout/fallo/no respuesta a error explícito; asegurar lista de candidatos vacía no se confunde con error de dependencia. **PyTest:** ningún candidato se devuelve si M3 no valida.
- [ ] **25 min — Implementar cálculo de distancia lineal y orden.** Calcular distancia origen-conductor, aplicar radio/límite y ordenar determinísticamente. **PyTest:** distancias conocidas, borde del radio y límite.
- [ ] **25 min — Implementar servicio de cobertura geográfica.** Validar punto en zona aprobada mediante geometría acordada, no asumir que el rectángulo piloto es definitivo. **PyTest:** punto interior, borde y exterior para Chaco/Corrientes.
- [ ] **25 min — Implementar filtro de candidatos completo.** Combinar ubicación vigente, estado, reserva, tipo de vehículo, M3 y cobertura. **PyTest:** un caso por condición de exclusión y candidato válido.
- [ ] **25 min — Añadir ETA de retiro a candidatos.** Consultar router para origen/conductor sin exponer posiciones; permitir omisión solo ante fallo según política. **PyTest:** ETA obtenido, degradación aprobada y falla M3 no degradable.
- [ ] **25 min — Publicar `GET /api/v1/conductores/cercanos`.** Validar parámetros, aplicar default y límites acordados y retornar contrato sin GPS. **PyTest:** respuesta vacía, candidato válido, radio/límite y ausencia de latitud/longitud.
- [ ] **25 min — Añadir protección de privacidad al endpoint de proximidad.** Aplicar `Cache-Control: no-store` y verificar sanitización de access logs/traces. **PyTest:** headers y logs sin coordenadas ni URL completa.

## 5. Reservas atómicas e idempotencia M5

- [ ] **25 min — Implementar transacción de reserva por conductor.** Usar lock/constraint/operación atómica PostgreSQL para serializar intentos concurrentes. **PyTest:** dos conexiones concurrentes, una reserva confirmada y una en conflicto.
- [ ] **25 min — Implementar semántica de mismo titular.** Repetir reserva del mismo conductor y solicitud no crea una reserva adicional. **PyTest:** respuesta estable y una sola fila/estado activo.
- [ ] **25 min — Implementar conflicto entre solicitudes.** Devolver `409` cuando otra solicitud conserva reserva activa. **PyTest:** no modifica titular ni expiración de la reserva existente.
- [ ] **25 min — Implementar liberación con validación de titular.** Solo solicitud propietaria libera; liberar una reserva ajena produce conflicto y no cambia estado. **PyTest:** propietario y no propietario.
- [ ] **25 min — Implementar expiración de reserva.** Considerar vencida una reserva cuyo `expira_en` ya pasó y permitir nueva reserva según TTL acordado. **PyTest:** antes/en/después de expiración con reloj congelado.
- [ ] **25 min — Implementar middleware/servicio de idempotencia.** Guardar hash canónico y resultado junto al efecto dentro de la misma transacción. **PyTest:** misma key/mismo cuerpo reproduce resultado; misma key/cuerpo distinto devuelve `422`.
- [ ] **25 min — Publicar `POST /api/v1/conductores/{id}/reserva`.** Aplicar `Idempotency-Key`, respuesta `200`/`201`, `404`, `409` y `422`. **PyTest:** reservar, repetir, conflicto, liberar y headers.

## 6. Mapas, geocodificación, M7 y M9

- [ ] **25 min — Crear adaptador de geocodificación.** Encapsular proveedor y convertir resultado a coincidencias OpenAPI. **PyTest:** cero, una y varias coincidencias, respuesta malformada y timeout simulados.
- [ ] **25 min — Publicar `POST /api/v1/geocodificaciones`.** Validar país/dirección, no almacenar consulta y devolver lista vacía cuando no existan resultados. **PyTest:** entradas válidas, límites y errores de proveedor.
- [ ] **25 min — Crear adaptador de cálculo de rutas.** Devolver distancia de ruta, ETA, `calculado_en` y `fuente`; nunca etiquetar distancia lineal como ruta. **PyTest:** ruta de proveedor, fallback aprobado y error sin fallback.
- [ ] **25 min — Publicar `GET /api/v1/rutas/estimacion`.** Validar coordenadas/tipo y mapear éxito, timeout y dependencia no disponible a status Problem Details. **PyTest:** contrato, `504` y `503`.
- [ ] **25 min — Integrar verificación de cobertura para M9.** Asegurar que origen y destino fuera de área se rechazan con error de dominio según contrato acordado. **PyTest:** origen exterior, destino exterior y ambos interiores.
- [ ] **25 min — Implementar contrato de consulta de estimación M9.** Entregar métricas para evaluar viabilidad sin crear ni persistir una reserva de viaje. **PyTest:** origen/destino válidos, no viable y métricas/unidades.
- [ ] **25 min — Implementar mecanismo asíncrono de métricas para M7 tras aprobar contrato.** Si se aprueba push, usar outbox y consumidor/cliente con deduplicación; de lo contrario documentar el flujo pull. **PyTest:** mensaje incluye solicitud y métricas; reintento no duplica efecto y error no bloquea request.

## 7. Health, integración, pruebas y documentación

- [ ] **25 min — Implementar `GET /health/live` y `/health/ready`.** Mantener liveness independiente y readiness sin detalles internos. **PyTest:** liveness `200`, readiness listo `200` y dependencia crítica no disponible `503`.
- [ ] **25 min — Añadir fixture de reloj y fábrica de app de pruebas.** Evitar sueño real y dependencias globales; aislar settings/repositorios por test. **PyTest:** test de TTL instantáneo y teardown de recursos.
- [ ] **25 min — Añadir pruebas API de headers y Problem Details.** Verificar `X-Request-Id` en éxitos y errores, content type y status concordante. **PyTest:** cubrir `400`, `401`, `403`, `404`, `409`, `422`, `503` y `504` representativos.
- [ ] **25 min — Añadir pruebas de privacidad de punta a punta.** Recorrer respuesta, logs simulados y propagación de correlación. **PyTest:** ninguna coordenada GPS de conductor aparece en respuesta M5 ni logs.
- [ ] **25 min — Añadir prueba de contrato OpenAPI.** Comparar rutas, métodos, status y campos JSON de la app con el contrato versionado. **PyTest:** test de contrato falla ante campo requerido ausente o extra prohibido.
- [ ] **25 min — Ejecutar suite de integración en Docker y reparar regresiones relacionadas.** Ejecutar la suite prescrita con PostgreSQL y el backend efímero elegido. **Verificación:** `docker-compose exec api python -m pytest -v` (o comando `docker compose` configurado) completa correctamente.
- [ ] **25 min — Actualizar guía de despliegue y operación.** Documentar variables, servicios adicionales aprobados, migraciones, health, timeouts y redacción de logs. **Verificación:** instrucciones reproducibles en entorno limpio, sin secretos en documentación.

## Secuencia sugerida y gates

1. Cerrar acuerdos del bloque 0 antes de congelar interfaces externas.
2. Fundamentos y repositorios antes de servicios; ubicación/estado antes de proximidad.
3. La consulta de proximidad depende del contrato M3, cobertura, backend efímero y adaptador de mapas.
4. La reserva se valida con concurrencia real antes de considerarla lista; los tests unitarios solos no prueban atomicidad.
5. El push M7 queda bloqueado hasta acuerdo de contrato y actualización aprobada de OpenAPI.
6. Cada tarea debe dejar tests verdes y cambios pequeños. La suite Docker completa se ejecuta en integración y antes de entrega.
