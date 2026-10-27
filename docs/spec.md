# Especificación Funcional (Spec) - Módulo 4: Ubicación y Disponibilidad

Este documento define el comportamiento funcional, contratos y reglas de negocio del Módulo 4 (M4) bajo el enfoque de Spec-Driven Development (SDD).

---

## RF-4.1 & RF-4.3: Recepción y TTL de Ubicación del Conductor
- **Descripción:** La aplicación móvil del conductor envía su posición GPS vigente de forma periódica.
- **Reglas de Negocio:**
  - M4 recibe, valida y almacena la posición en una proyección efímera (memoria/BD).
  - **TTL de 30 segundos:** Las posiciones GPS expiran estrictamente a los 30 segundos de su marca temporal. Las ubicaciones vencidas no deben utilizarse en búsquedas ni conservarse como activas.
  - Se valida el orden cronológico de los timestamps: una posición anterior no sobrescribe una más nueva. El mismo timestamp con coordenadas distintas retorna `409 Conflict`.

---

## RF-4.2 & RF-4.5: Búsqueda de Conductores Cercanos (Proximidad y Geocodificación)
- **Descripción:** M5 solicita candidatos disponibles próximos a un origen.
- **Flujo y Reglas de Negocio:**
  - **Origen en Lenguaje Natural:** M5 envía el origen como texto (ej. *"Plaza 25 de Mayo, Resistencia"*). M4 utiliza `geopy` (Nominatim) para geocodificar la dirección a coordenadas WGS 84 y valida que caiga dentro de la zona permitida (Chaco/Corrientes).
  - **Delegación a M3:** M4 consulta a M3 para obtener los conductores operativos con el tipo de vehículo solicitado. Se asume que M3 entrega exclusivamente aquellos con habilitación **`APPROVED`**, **`connected=true`** y **`available=true`**.
  - **Filtro de Estado Temporal:** M4 descarta a los conductores que posean una reserva temporal activa (`estado_temporal = RESERVADO`).
  - **Radio Fijo de 5 km:** Se evalúa la última posición GPS vigente (dentro del TTL de 30s) y se filtran aquellos cuya distancia lineal supere el radio fijo de **5 km**.
  - **Privacidad (RF-4.7):** M4 retorna a M5 una lista con `conductor_id`, `distancia_origen_km`, `eta_retiro_minutos` y `tipo_vehiculo`. **Nunca se exponen las coordenadas exactas** del conductor.

---

## RF-4.4 & RF-5.4: Reserva Temporal e Idempotencia
- **Descripción:** Bloqueo temporal de un conductor tras la aceptación de una oferta de viaje.
- **Flujo y Reglas de Negocio:**
  - Una vez que M5 despacha y ofrece el viaje a la lista de conductores cercanos provista por M4, el conductor acepta la oferta (notificado a través de M3/M5).
  - En ese instante, M5 notifica a M4 invocando el endpoint de reserva temporal para bloquear a ese conductor específico (`conductor_id`) asociado al `solicitud_id`.
  - **Atomicidad y Concurrencia:** La operación de reserva debe ser atómica para evitar conflictos ante respuestas concurrentes. Si el conductor ya fue tomado por otra solicitud, M4 responde incondicionalmente con **`409 Conflict`**.
  - **Idempotencia:** La repetición de la misma petición con el mismo identificador de idempotencia (`Idempotency-Key`) debe retornar el resultado original de forma segura.
  - M5 debe liberar explícitamente la reserva enviando `estado_temporal = LIBERADO` cuando el viaje avance de estado o se cancele.
  
---

## RF-4.6: Estimación de Rutas, M7 y M9
- **Descripción:** Cálculo de distancias y tiempos estimados de viaje.
- **Reglas de Negocio:**
  - **Integración con M9:** M9 consulta la viabilidad geográfica (si un viaje es posible dentro de la zona de cobertura) y obtiene el ETA/distancia preliminar para reservas a futuro.
  - **Integración con M7:** M4 procesa proactivamente los cálculos de distancia (`dod`) y tiempo (`ett`) asociados al identificador del viaje y se los envía a M7 para el cálculo de tarifas, operando de forma asíncrona y resiliente (sin bloqueos ante caídas de dependencias).