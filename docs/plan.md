# Plan técnico — Módulo 4: Ubicación y Disponibilidad

## 1. Propósito y alcance

M4 mantiene la proyección vigente de ubicación y disponibilidad de conductores, identifica candidatos geográficamente próximos, coordina reservas temporales e informa estimaciones de ruta y cobertura a los módulos consumidores. Es propietario de la ubicación recibida desde la aplicación del conductor y de las reservas temporales; no es propietario de perfiles, habilitaciones ni catálogo maestro de vehículos, que pertenecen a M3.

Este plan describe la arquitectura objetivo de M4 según `docs/agents.md`, `docs/constitution.md`, `docs/spec.md` y el contrato público `openapi.yml`. OpenAPI define las rutas, esquemas y respuestas de referencia hasta que los grupos acuerden formalmente un cambio. No se debe implementar una ruta o cambiar un contrato fuera de dicho proceso.

### Dentro del alcance

- Recepción, validación cronológica, vigencia y privacidad de ubicaciones GPS.
- Proyección de la intención operativa enviada por M3.
- Búsqueda geoespacial de candidatos con validación de elegibilidad en M3.
- Reserva temporal atómica, liberación e idempotencia.
- Geocodificación, cálculo de ruta/distancia/ETA y validación de cobertura para M9.
- Contratos HTTP, seguridad de servicio, trazabilidad, errores, resiliencia y pruebas.

### Fuera del alcance

- Alta, perfil, habilitación, suspensión o catálogo maestro de conductores/vehículos (M3).
- Despacho de ofertas y ciclo de vida del viaje (M5).
- Cálculo de tarifas, cobros o pagos (M7).
- Creación/gestión de reservas de viaje y su persistencia de dominio (M9).
- Autenticación y emisión de credenciales (M1); M4 aplica el contrato de autorización acordado.

## 2. Principios y restricciones

1. **Contrato primero:** las rutas, métodos, esquemas y estados HTTP públicos siguen `openapi.yml`. Cada comportamiento debe trazarse a RF/RNF del contrato.
2. **TTL de ubicación:** la constitución fija 30 segundos. Una ubicación vencida nunca cuenta como activa ni participa en proximidad; la proyección efímera debe expirar y no conservarse indefinidamente.
3. **Elegibilidad cerrada (fail-closed):** no devolver candidatos sin verificación satisfactoria de M3. Solo son elegibles habilitación `APPROVED`, `connected=true`, `available=true`, tipo de vehículo compatible, ubicación vigente y ausencia de reserva activa.
4. **Reserva atómica:** una sola solicitud puede poseer la reserva activa de un conductor. Si otra solicitud ya lo posee, devolver `409`; repetir la misma operación con la misma clave de idempotencia y cuerpo devuelve el resultado original.
5. **Minimización de datos:** a M5 no se exponen coordenadas GPS del conductor. No registrar coordenadas exactas, query strings sensibles, tokens ni datos de credenciales.
6. **Resiliencia externa:** timeouts finitos, reintentos limitados solo donde sean seguros, manejo explícito de fallo y propagación de `503`/`504` según contrato. No degradar a candidatos sin validar.
7. **Trazabilidad y errores:** toda respuesta incluye `X-Request-Id`; generar uno si falta o no es válido. Errores de negocio se serializan como `application/problem+json` según el esquema Problem Details del OpenAPI.
8. **UTC y unidades explícitas:** timestamps RFC 3339/UTC, coordenadas WGS 84, distancias en km y ETA en minutos.

## 3. Arquitectura lógica

La aplicación se organiza por responsabilidad; los routers traducen HTTP y delegan en servicios, y los servicios dependen de interfaces de repositorio y clientes externos. Ningún router debe contener algoritmos de negocio ni llamar directamente a proveedores externos.

| Módulo lógico | Responsabilidad principal | Dependencias |
|---|---|---|
| `app/main.py` y bootstrap | Construir FastAPI, configurar lifespan, routers, middleware y health; no crear tablas en importación | configuración, infraestructura |
| `app/api/` (routers) | Validar/serializar contratos y convertir resultados/errores en HTTP | schemas, servicios |
| `app/schemas/` | DTOs Pydantic alineados con componentes OpenAPI, enums, validación estructural | ninguna |
| `app/services/location_service.py` | Validar coordenadas/timestamps, aplicar orden, guardar ubicación y vigencia | repositorio de ubicación, reloj |
| `app/services/availability_service.py` | Aplicar eventos puntuales, deduplicar/ordenar cuando el contrato lo permita, normalizar `available=false` si desconectado | repositorio operacional |
| `app/services/proximity_service.py` | Coordinar origen, consulta de elegibilidad M3, estado local, radio, distancias, ETA y privacidad | M3 client, location/availability/reservation repositories, routing |
| `app/services/reservation_service.py` | Reserva/liberación transaccional, titularidad e idempotencia | PostgreSQL repository |
| `app/services/geocoding_service.py` | Resolver dirección mediante proveedor y validar cobertura | geocoder adapter |
| `app/services/routing_service.py` | Calcular distancia de ruta y ETA; normalizar proveedor/fallback permitido | routing adapter |
| `app/services/coverage_service.py` | Validar origen y destino en el polígono/área autorizada de Chaco/Corrientes | configuración de cobertura |
| `app/clients/m3_client.py` | Cliente HTTP tipado para estado/habilitación/tipo de vehículo | configuración HTTP |
| `app/clients/map_client.py` | Cliente HTTP/proveedor para geocodificación y rutas | configuración HTTP |
| `app/repositories/` | Acceso a datos, aislamiento de transacciones y proyecciones | SQLAlchemy, backend efímero |
| `app/core/` | Configuración, correlación, Problem Details, logging redactado y errores de dominio | FastAPI |
| `alembic/` | Migraciones versionadas de las tablas persistentes | PostgreSQL |
| `tests/` | Pruebas unitarias, integración API/repositorio y escenarios de concurrencia | PyTest, fixtures, mocks |

La implementación HTTP actual conserva el paquete existente `app/enrutador/` y separa los routers de ubicaciones, estado operativo, reservas y estimación de rutas. La lógica común está en `app/servicios/operaciones.py`; el contrato inyectable para mapas está en `app/servicios/route_estimation.py`. Los routers obtienen repositorios mediante `Depends`; no ejecutan consultas ORM directamente.

La autenticación de solicitudes con credenciales HTTP delega en el adaptador `app.state.token_authenticator`, que debe validar identidad y autorización de la operación con M1. Como ese acuerdo/adapter aún no existe, la API falla cerrada: credenciales ausentes producen `401` y una credencial recibida sin verificador configurado produce `503`. De modo análogo, rutas no fabrican distancias: `GET /api/v1/rutas/estimacion` necesita un estimador configurado y responde `503` si no está disponible. `RESERVATION_TTL_SECONDS` debe configurarse conforme al acuerdo con M5; no se reutiliza el TTL de GPS.

El cliente M3 en `app/clients/m3.py` usa credencial Bearer de servicio, timeouts finitos y propaga el `X-Request-Id` del contexto. `M3_BASE_URL`, `M3_SERVICE_TOKEN` y `M3_ELIGIBILITY_PATH` se configuran juntos; la ruta debe incluir `{conductor_id}` y se deja configurable porque su forma pertenece al OpenAPI de M3. El lifespan crea y cierra el cliente. El mapeo sigue `ElegibilidadDesdeM3` del OpenAPI de M4, exige ambos campos, rechaza enums desconocidos y propiedades extra, y nunca convierte fallos de M3 en una lista vacía.

La proximidad usa distancia Haversine en línea recta, aplica el radio y el límite configurados y ordena por distancia e ID de conductor. El área se carga mediante `COVERAGE_GEOJSON` como `Polygon` o `MultiPolygon`; origen y ubicación candidata deben estar cubiertos. Si no se configura geometría, el servicio falla cerrado con `503`. Los GeoJSON sintéticos de pruebas verifican el algoritmo y no constituyen aprobación de la cobertura real de Chaco/Corrientes; esa geometría continúa pendiente en los acuerdos de preparación y debe aprobarse antes de habilitar búsqueda en producción.

### Infraestructura y persistencia

- **PostgreSQL 15 + SQLAlchemy + Alembic:** persistencia relacional del estado operativo requerido entre llamadas, reservas, registro de idempotencia y, si el acuerdo de retención lo permite, datos de auditoría no sensibles.
- **Proyección GPS efímera:** `LocationRepository` separa la interfaz del backend. La decisión acordada es Redis, con TTL nativo de 30 s y actualización cronológica atómica; PostgreSQL no debe usarse como archivo histórico de GPS. Compose ejecuta Redis sin persistencia en disco y espera su healthcheck antes de iniciar la API. Si Redis no está disponible, la aplicación no inicia con un adapter GPS falsamente saludable.
- **Reservas:** PostgreSQL permite transacción y exclusión por conductor; las reservas tienen `expira_en` y toda lectura comprueba vigencia. El vencimiento configurable del contrato se debe acordar y no sustituye la liberación explícita de M5.
- **Proveedor de mapas:** encapsular geocodificación y rutas detrás de adaptadores para poder simularlos en pruebas. La política de fallback debe distinguir estimación aproximada de resultado del proveedor y reflejar `fuente` según OpenAPI.
- **Clientes HTTP:** clientes de vida útil de aplicación, timeouts de conexión/lectura configurados y cierre ordenado. No bloquear el event loop; usar cliente asíncrono para dependencias HTTP.

## 4. Modelos y datos

Los siguientes son modelos conceptuales y no deben confundirse con las tablas piloto existentes. Los identificadores públicos son UUID conforme al OpenAPI; cualquier diferencia con identificadores legacy enteros requiere migración y acuerdo, no conversión implícita.

### 4.1 Proyección efímera `UbicacionVigente`

| Campo | Tipo/semántica | Restricción |
|---|---|---|
| `conductor_id` | UUID | Clave de la proyección |
| `latitud`, `longitud` | decimal WGS 84 | Rangos [-90,90] y [-180,180] |
| `timestamp_ubicacion` | datetime UTC del dispositivo | Orden cronológico; más antigua no pisa una nueva |
| `recibida_en` | datetime UTC de M4 | Observabilidad/expiración |
| `expira_en` | datetime UTC | `recibida_en + 30 s` por regla constitucional |

Escritura repetida del mismo timestamp y mismas coordenadas: idempotente. El mismo timestamp con coordenadas diferentes: `409`. Una actualización fuera de orden no reemplaza la más nueva y responde conflicto según contrato. El servicio determina vigencia con reloj inyectable y elimina/expira datos; una búsqueda siempre aplica el TTL incluso si la limpieza física todavía no ocurrió.

El schema rechaza timestamps sin UTC y Redis conserva el orden relativo entre muestras vigentes. El endpoint rechaza cualquier timestamp posterior al reloj UTC inyectado. No se impone antigüedad máxima al timestamp del dispositivo, ya que el contrato no la define y el TTL de 30 segundos se calcula desde la recepción.

### 4.2 Estado operacional `EstadoOperativoConductor`

| Campo | Tipo/semántica |
|---|---|
| `conductor_id` | UUID del conductor |
| `connected` | booleano recibido desde M3 |
| `available` | booleano normalizado; siempre `false` cuando `connected=false` |
| `event_id` | UUID opcional mientras M3 no confirme su obligatoriedad; clave de deduplicación si existe |
| `timestamp_evento` | datetime UTC opcional mientras se acuerde el contrato de orden |
| `recibido_en`, `actualizado_en` | marcas UTC de recepción y evento aplicado |

M4 no infiere habilitación ni inventa eventos faltantes. Sin `event_id`/timestamp, el contrato de integración debe especificar entrega ordenada; la proyección se actualiza según orden de recepción hasta resolver el acuerdo.

Cuando `event_id` está presente, `eventos_operativos` conserva el hash canónico y la respuesta original para deduplicar reintentos incluso después de que la proyección reciba eventos más recientes. Una clave reutilizada con distinto cuerpo responde `422`.

### 4.3 Reserva `ReservaTemporal`

| Campo | Tipo/semántica | Restricción |
|---|---|---|
| `conductor_id` | UUID | Clave/lock lógico por conductor |
| `solicitud_id` | UUID | Titular de la reserva |
| `estado_temporal` | enum `RESERVADO` / `LIBERADO` | Estado |
| `creada_en`, `actualizado_en` | datetime UTC | Auditoría operacional |
| `expira_en` | datetime UTC nullable | Requerida para reserva activa |

Se impone una única reserva activa por conductor mediante transacción/lock o restricción equivalente. La liberación solo aplica si coincide el `solicitud_id` titular; una solicitud distinta recibe conflicto.

### 4.4 Registro `Idempotencia`

Clave compuesta por actor/operación y `Idempotency-Key`; almacenar hash canónico del cuerpo, estado HTTP y respuesta original, con vencimiento/retención acordados. Misma clave y cuerpo reproduce la respuesta; misma clave con cuerpo distinto responde `422` según el contrato. La creación del registro y el efecto de negocio se confirman en la misma transacción para evitar respuestas sin efecto o efectos duplicados.

### 4.5 DTOs de consulta (no persistidos como maestros)

- `Candidato`: `conductor_id`, `distancia_origen_km`, `eta_retiro_minutos` opcional y `tipo_vehiculo`. No contiene latitud/longitud del conductor.
- `EstimacionRuta`: puntos de origen/destino, `distancia_estimada_km`, `eta_minutos`, `calculado_en` y `fuente`.
- `ResultadoGeocodificacion`: lista de coincidencias (latitud, longitud, etiqueta y confianza opcional); coincidencias ambiguas no se eligen silenciosamente.
- `Problema`: respuesta RFC 7807 según esquema OpenAPI, con código estable y correlación.

### Datos y retención

No usar `RegistroSolicitud` ni las tablas piloto como histórico de coordenadas por defecto. Guardar solo la información necesaria para operación. Definir retención para claves de idempotencia y auditoría; excluir coordenadas, tokens, secretos y query strings de logs. Si un registro necesita ubicación de origen/destino para una operación funcional, documentar finalidad, acceso y expiración específica antes de persistirlo.

La capa ORM relacional mantiene `estado_operativo`, `eventos_operativos`, `reservas_temporales` y `registros_idempotencia`. La ubicación GPS permanece en el repositorio efímero previsto en 4.1 y `Candidato` se calcula como DTO; ninguno se materializa como tabla SQL. Los DTOs de respuesta de estado y reserva habilitan `from_attributes` para serializar proyecciones ORM, y los timestamps se normalizan a UTC tanto en PostgreSQL como en SQLite de pruebas. `expira_en` del registro de idempotencia queda nullable mientras se acuerda una política de retención.

## 5. Contratos HTTP y errores

Todos los endpoints de negocio usan prefijo `/api/v1` y los esquemas exactos del contrato:

| Endpoint | Consumidor/origen | Operación |
|---|---|---|
| `POST /api/v1/ubicaciones` | app móvil de conductor | registrar o actualizar GPS vigente |
| `POST /api/v1/conductores/{conductor_id}/estado-operativo` | M3 | reflejar intención puntual de conexión/disponibilidad |
| `GET /api/v1/conductores/cercanos` | M5 | devolver candidatos elegibles sin coordenadas exactas |
| `POST /api/v1/conductores/{conductor_id}/reserva` | M5 | reservar o liberar con `Idempotency-Key` |
| `GET /api/v1/rutas/estimacion` | M5, M7 y M9 según contrato | calcular distancia de ruta y ETA |
| `POST /api/v1/geocodificaciones` | módulos autorizados | resolver dirección enviada en cuerpo |
| `GET /health/live`, `GET /health/ready` | plataforma | liveness/readiness sin token según OpenAPI |

`X-Request-Id` se valida o genera en middleware y se devuelve también en fallos. `X-Request-Id` debe propagarse a llamadas HTTP salientes. Las respuestas de proximidad incluyen `Cache-Control: no-store`; logs y trazas no deben almacenar URL completa en endpoints con coordenadas.

Mapeo de errores a acordar con los casos del OpenAPI: validación estructural `400`/`422` según definición del endpoint, no autenticado `401`, permisos `403`, no encontrado `404`, conflicto temporal/orden/idempotencia `409` según caso, rate limit `429`, dependencia no disponible `503`, timeout `504`, e inesperado `500`. El cuerpo no expone stack traces ni detalles internos.

## 6. Flujos de negocio

### 6.1 Actualización de ubicación

1. Middleware determina/genera `X-Request-Id`, autentica y autoriza al conductor según M1.
2. Schema valida UUID, rangos WGS 84 y timestamp RFC 3339.
3. Servicio compara con el valor vigente del conductor de forma atómica.
4. Si no había posición, registra y responde `201`; si reemplaza una posición válida, responde `200`.
5. Si es idéntica (incluyendo timestamp y coordenadas), la trata idempotentemente; timestamp antiguo o timestamp igual con coordenadas distintas devuelve conflicto según el contrato.
6. Establece expiración estricta de 30 s; las consultas nunca leen una posición cuyo TTL expiró. Respuesta informa `recibida_en`, `vigente` y expiración, sin revelar coordenadas innecesarias.

### 6.2 Ingesta de estado operativo desde M3

1. M3 invoca el endpoint autenticado de servicio, identificando conductor y evento.
2. Validar `connected`/`available`; normalizar `available=false` si `connected=false`.
3. Deduplicar por `event_id` si está presente y rechazar la misma clave con cuerpo inconsistente conforme a OpenAPI.
4. Si hay timestamp, ignorar/rechazar eventos fuera de orden conforme al contrato; si falta, depender de la entrega ordenada que M3 debe garantizar.
5. Persistir la proyección. No modificar ubicación ni habilitación. Responder `200` al actualizar o `201` al crear.

### 6.3 Búsqueda de conductores cercanos para M5

1. M5 solicita origen WGS 84, tipo de vehículo, radio y límite; valores deben validarse contra configuración/rangos acordados.
2. Validar que el origen cae dentro de cobertura. Para la variante textual que describe RF-4.5, geocodificar por servicio; el OpenAPI actual define coordenadas en esta ruta.
3. Leer ubicaciones vigentes y estado operacional local; excluir posición vencida, desconectado, no disponible y reserva activa.
4. Consultar M3 solo para el conjunto candidato necesario (no pedir listado completo): habilitación vigente `APPROVED` y vehículo compatible, junto con estado conectado/disponible según contrato de M3.
5. Si M3 falla, devolver error de dependencia (`503` o `504`) sin candidatos; nunca aplicar fallback abierto.
6. Calcular distancia lineal y filtrar por radio (el OpenAPI usa valor por defecto 5 km y permite parámetros; la constitución/spec hablan de radio fijo de 5 km). Ordenar/priorizar y limitar.
7. Calcular ETA al origen con proveedor de mapas. `eta_retiro_minutos` puede omitirse ante timeout o indisponibilidad del proveedor de mapas cuando `PROXIMITY_ETA_DEGRADATION_ENABLED=true` (predeterminado, conforme al OpenAPI). Si se deshabilita la degradación, el error de mapas se propaga como `503`/`504`; los errores de M3 siempre se propagan sin candidatos.
8. Responder `200`, incluso lista vacía, con `Cache-Control: no-store` y solamente los campos de `Candidato`. Nunca incluir coordenadas GPS del conductor.

### 6.4 Reserva y liberación desde M5

1. M5 envía conductor, `solicitud_id`, acción y `Idempotency-Key`.
2. Validar identidad, cuerpo y titularidad; calcular hash canónico para la clave.
3. En una sola transacción, buscar clave idempotente, bloquear/excluir la fila lógica del conductor y comprobar expiración.
4. Si la clave ya existe con mismo hash, devolver la respuesta original. Si existe con hash distinto, devolver `422`.
5. Si se solicita reserva y otra solicitud posee reserva activa, devolver `409`; si la misma solicitud ya la posee, devolver resultado idempotente. De lo contrario crear reserva expirable y confirmar clave/resultado atómicamente.
6. Si se solicita liberación, exigir titularidad por `solicitud_id`; liberar solo la reserva propia. No permitir que otra solicitud la borre.
7. M5 debe liberar explícitamente al cerrar/cancelar/avanzar el ciclo indicado por su contrato; TTL es salvaguarda y requiere un valor acordado.

### 6.5 Geocodificación y estimación de ruta

1. Geocodificación acepta dirección/localidad/país en cuerpo y devuelve cero o más coincidencias; valida coordenadas y cobertura cuando se utilice para un flujo que solo admite Chaco/Corrientes.
2. Estimación valida puntos WGS 84 y tipo de vehículo opcional, consulta proveedor de rutas con timeout y devuelve ruta, ETA, instante y fuente.
3. Cuando no hay proveedor, solo usar `estimacion_local` si está definida y aprobada como fallback; no presentar distancia lineal como distancia de ruta sin declararlo. Si no existe fallback válido, devolver `503`/`504`.
4. M9 usa estimación y validación de cobertura para decidir viabilidad; M4 no crea ni confirma una reserva del viaje.
5. M7 requiere métricas asociadas a `solicitud_id` para tarifación. El mecanismo proactivo/asíncrono de envío descrito por la constitución no está modelado como operación saliente en el OpenAPI actual (la ruta actual es GET y los consumidores consultan). No introducir callback/evento no contratado: acordar contrato, entrega, reintentos e idempotencia con M7 y actualizar OpenAPI antes de implementar ese envío.

El endpoint GET y el límite inyectable del estimador están publicados; la implementación del proveedor, geocodificación, fallback y cobertura permanece pendiente del acuerdo de mapas/M9. Las pruebas API inyectan un proveedor simulado y verifican éxito, límites, timeout y ausencia del proveedor sin afirmar integración externa.

## 7. Integraciones externas

| Módulo | Interacción desde M4 | Garantía/decisión |
|---|---|---|
| M3 | Recibe eventos puntuales de intención; consulta elegibilidad/habilitación/tipo de vehículo al filtrar | Cliente HTTP asíncrono con token Bearer de servicio, timeout, correlación y respuesta validada. Ruta desplegada se configura hasta que conste en el contrato de M3. Timeout/fallo/respuesta incompleta producen error fail-closed |
| M5 | Consume candidatos/ETA; ordena/despacha ofertas; reserva y libera conductor | M4 no reserva al listar. La reserva atómica es autoridad final. Privacidad de coordenadas absoluta |
| M7 | Consume distancia y ETA asociados a la solicitud para tarifación | Definir si será push asíncrono/outbox o consulta por endpoint; no confundir ambas direcciones del OpenAPI vigente |
| M9 | Consume viabilidad geográfica y estimación para reservas de viaje | M4 verifica origen/destino dentro del área permitida y responde métrica; M9 conserva la reserva de viaje |
| M1 | Autenticación/claims y autorización | Acordar scopes por consumidor; M4 no emite tokens |
| proveedor de mapas | Geocodificación y ruta | Adaptador, timeout/reintentos limitados, atribución de fuente y política explícita de fallback |

### Resiliencia y consistencia

- Configurar límites separados de conexión y lectura por integración; los valores deben acordarse y probarse.
- Reintentar solo fallos transitorios y operaciones idempotentes, con número finito, backoff y jitter. No reintentar un conflicto de negocio ni una solicitud de escritura no idempotente.
- Propagar `X-Request-Id`; registrar nombre lógico de dependencia, latencia y resultado sin credenciales, coordenadas ni URLs sensibles.
- M3 es dependencia crítica para elegibilidad. Error, timeout o respuesta incompleta impide devolver resultados de proximidad.
- La reserva se confirma localmente en transacción; no depende de la disponibilidad de mapas ni de M3 si el contrato no lo requiere para reservar un candidato ya ofrecido. Esta regla requiere confirmación con M5/M3 sobre revalidación en el instante de reservar.
- El envío asíncrono a M7, si se acuerda, debe tener mensaje con `solicitud_id`, métricas/unidades, clave de deduplicación, persistencia/outbox, reintentos finitos y observabilidad; la entrega no debe bloquear el ciclo HTTP.

## 8. Seguridad, privacidad y observabilidad

- Autorización por actor/servicio en M1; health exceptuado como define OpenAPI.
- Validar todas las entradas en límites de schema y reglas de dominio; no confiar en elegibilidad enviada por M5.
- Enmascarar/rechazar headers sensibles y redactar coordenadas de query string en access logs, tracing y reportes de error.
- Retornar únicamente el mínimo de datos; en candidatos, conductor, distancia, ETA y tipo de vehículo.
- Respuestas de error RFC 7807 incluyen tipo/título/status/detail/instance, código de dominio cuando aplica y correlación; no contener datos internos.
- Métricas recomendadas: ubicaciones aceptadas/rechazadas/vencidas; latencia/fallos de M3/mapas; candidatos y lista vacía; conflictos/idempotencia de reserva; expiraciones/liberaciones; errores por endpoint. Evitar etiquetas de alta cardinalidad con UUID y no incluir GPS.
- `liveness` comprueba que proceso responde; `readiness` comprueba dependencias imprescindibles para atender de forma segura, sin exponer información interna.

## 9. Estrategia de pruebas PyTest

1. Unitarias de schemas, coordenadas, cobertura, TTL con reloj inyectable, orden/idempotencia de GPS, distancia y clasificación de errores.
2. Unitarias de servicios con repositorios, reloj, cliente M3 y proveedor de mapas simulados; comprobar fail-closed y propagación de timeouts.
3. Pruebas API con `TestClient`/cliente asíncrono para contratos JSON, status, headers, Problem Details, auth stub y ausencia de coordenadas en respuestas/logs.
4. Pruebas de integración con PostgreSQL para migraciones, transacciones, exclusión e idempotencia; pruebas concurrentes deben demostrar exactamente un ganador para dos reservas incompatibles.
5. Pruebas del backend efímero para expiración física/lógica de ubicación en 30 s y no reutilización de datos vencidos.
6. Fixtures deterministas: reloj congelable, proveedor de mapas y M3 controlados, datos de borde geográfico y UUIDs fijos.
7. Ejecutar mediante el flujo documentado del proyecto: `docker-compose exec api python -m pytest -v` (o equivalente `docker compose` adoptado por el entorno). Cada historia debe añadir pruebas dirigidas y no depender de servicios externos reales.

## 10. Decisiones y acuerdos previos a implementación

| Tema | Estado/documento actual | Acción necesaria |
|---|---|---|
| TTL de GPS | Constitución fija 30 s; OpenAPI lo describe configurable | Mantener 30 s como regla hasta aprobar formalmente un cambio y alinear OpenAPI |
| Almacén efímero | Compose actual contiene PostgreSQL; OpenAPI sugiere memoria/Redis | Aprobar Redis o un mecanismo equivalente con expiración comprobable; no persistir GPS indefinidamente |
| TTL de reserva | OpenAPI dice configurable, sin valor; constitución especifica atomicidad/idempotencia | M5/M4 acuerdan duración, expiración, renovación si existe y liberación |
| Radio | Spec habla de radio fijo de 5 km; OpenAPI admite `radio_km` y máximo configurable | Definir si 5 km es invariable o default con expansión solicitada por M5 |
| M3 | Endpoint/payload de consulta y garantías de eventos todavía pendientes en OpenAPI | Acordar ruta, campos, estados, paginación/lote, orden, idempotencia y scopes |
| M1 | Claims/roles/scopes pendientes | Definir scopes para app, M3, M5, M7 y M9 |
| M7 | Constitución pide envío proactivo asíncrono; OpenAPI solo publica estimación consultable | Acordar push/outbox frente a pull; versionar OpenAPI antes del desarrollo |
| Geocodificación | Spec describe origen en lenguaje natural; nearby OpenAPI recibe coordenadas | Determinar qué consumidor invoca geocodificación y el flujo de resolución/confirmación |
| Cobertura | Constitución especifica Chaco/Corrientes; código piloto tiene un rectángulo de ejemplo | Aprobar geometría/polígono, límites y fuente de verdad; no tratar rectángulo piloto como cobertura final |
| Mapas y ETA | OpenAPI permite omitir ETA de retiro y distingue fuente de ruta | Elegir proveedor, licencia, límites, fallback y reglas de estimación local |
| Timeouts/reintentos | RNF-13 exige límites estrictos sin valores acordados | Establecer presupuesto por dependencia y políticas finitas antes de desplegar |
| Identificadores | OpenAPI propone UUID; modelos piloto usan enteros | Alinear con M1/M3/M5/M9 y migrar de forma explícita |
| GET con coordenadas | OpenAPI conserva rutas GET y advierte fuga en URL/logs | Configurar redacción; evaluar POST solo como cambio de contrato aprobado |

## 11. Criterios de aceptación arquitectónicos

- Todos los endpoints documentados implementan el contrato OpenAPI y el middleware de correlación/error.
- Ninguna búsqueda de proximidad devuelve conductor no validado por M3; cualquier fallo de M3 termina en error controlado.
- Una ubicación de más de 30 s no puede producir candidato ni permanecer como activa.
- No aparece GPS exacto del conductor en payload dirigido a M5, logs, trazas o respuestas de error.
- Pruebas concurrentes demuestran que solo una solicitud obtiene una reserva; repetición idempotente reproduce respuesta y otra solicitud recibe `409`.
- Todos los clientes externos tienen timeout finito y errores explícitos; el flujo M7 no se implementa hasta cerrar su contrato asíncrono.
- Cobertura de M9 rechaza origen/destino fuera del área aprobada y no crea reservas de viaje.
- Los documentos de tareas de `docs/tasks.md` guían implementación incremental, con PyTest asociado a cada unidad.
