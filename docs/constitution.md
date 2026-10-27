# Constitución del Módulo 4: Ubicación y Disponibilidad (TPI 2026)

Esta constitución define los principios arquitectónicos, de diseño y de negocio innegociables para el desarrollo del Módulo 4 (M4). Ningún componente, endpoint o agente de IA puede violar estas reglas.

## 1. TTL de Ubicaciones (30 Segundos)
- Las posiciones GPS enviadas por los dispositivos de los conductores tienen un tiempo de vida útil (TTL) estricto de **30 segundos** en almacenamiento efímero/memoria/base de datos.
- Las ubicaciones que superen este umbral se consideran vencidas, no deben conservarse como activas ni pueden ser utilizadas en las búsquedas de proximidad.

## 2. Atomicidad e Idempotencia en Reservas
- La operación de reserva temporal de un conductor (`/api/v1/conductores/{conductor_id}/reserva`) debe ser **atómica y concurrente** para evitar que dos solicitudes de viaje distintas tomen al mismo conductor.
- Si una solicitud intenta reservar un conductor que ya se encuentra ocupado por otra solicitud activa, M4 debe responder incondicionalmente con un código HTTP **409 Conflict**.
- La repetición de la misma solicitud con el mismo identificador de idempotencia (`Idempotency-Key`) debe retornar el resultado original de forma segura.

## 3. Validación Externa y Elegibilidad (M3)
- M4 no gestiona perfiles de conductores ni habilitaciones de vehículos; el propietario de esos datos es el **Módulo 3 (M3)**.
- Para cualquier operación de filtrado o despacho de conductores cercanos, M4 exige y consulta obligatoriamente a M3 que el conductor posea un estado de habilitación **`APPROVED`**, además de los estados booleanos **`connected=true`** y **`available=true`**.
- Ante la caída o ausencia de respuesta del M3, M4 **nunca** debe retornar candidatos sin validar.

## 4. Privacidad Absoluta de Coordenadas (RF-4.7)
- Las consultas de conductores cercanos (`/api/v1/conductores/cercanos`) destinadas al **Módulo 5 (M5)** deben retornar exclusivamente la identificación del conductor, la distancia calculada y el ETA estimado.
- Queda terminantemente prohibido exponer las coordenadas exactas (`latitud`, `longitud`) del conductor hacia M5, cumpliendo estrictamente con la minimización de datos.

## 5. Integración Asíncrona con M7 y M9
- **M7 (Tarifas y Pagos):** M4 calcula de forma proactiva las métricas de ruta (distancia y tiempo estimado) y se las comunica a M7 vinculadas al identificador del viaje/solicitud.
- **M9 (Reservas de Viajes):** M4 valida la viabilidad geográfica de los orígenes y destinos consultados por M9 frente a la zona de cobertura permitida (Chaco/Corrientes).
- **Resiliencia (RNF-13):** Las comunicaciones con módulos externos deben aplicar timeouts estrictos y manejo explícito de errores, evitando bloqueos indefinidos en el hilo principal de M4.