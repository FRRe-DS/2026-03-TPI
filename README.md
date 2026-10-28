# # Sistema de Gestión de Logística y Viajes (TPI 2026)

Plataforma distribuida de movilidad urbana bajo demanda.

## 🚀 Integrantes - Grupo 03 -

* Acevedo Gomez, Amparo.
* Claver Gallino, Samira.
* Echeverria Melgratti, Lautaro.
* Gonzalez, Micaela.
* Sanchez, Abigail.
* Franco Quiroz, Facundo Agustin.
* Rocio V. Ramirez.
* Roubineau Ana Laura

* **Carrera:** Ingenieria en Sistemas
* **Materia:** Desarrollo de Software 2026

## Modulo asignado:
## ID: 
M4
## Módulo: 
Ubicación y Disponibilidad	
## Responsabilidad: 
Posición vigente, disponibilidad, proximidad, distancia y ETA (Estimated Time of Arrival / Tiempo Estimado de Llegada).
## Integraciones clave:
M3, M5, mapas

## 🛠️ Tecnologías utilizadas
* **Lenguaje:** python:3.11-slim. Version ultra ligera para ejecucion en docker sin tanta demanda de hardware
* **Framework:** FastApi: Framework moderno y liviano, desarrollado para construccion de API REST y comunicacion de las mismas.
    *  **Dependencias auxiliares:**
        * SQLAlchemy: ORM de base de datos.
        * psycopg2-binary==2.9.10: Driver para que el ORM detecte y conecte la base de datos.
        * Alembic: Control de migraciones de la base de datos en caso de ser necesario un versionado de la misma.
        * httpx: Soporte para eventos asincronicos en caso de ser necesario
        * Uvicorn: Soporte asincronico de ASGI web server, cual permite ejecucion sobre el codigo en la api
        * Pydantic-Settings: Dependencia de mapeo sobre datos de los entornos, abstrae datos y aumenta seguridad.
        * Base de datos utlizada: PostgreSQL 15-alphine debido a sus bajos requerimientos de hardware.
* **Control de Versiones:** Git & GitHub

## Despliegue y operación

### Requisitos

- Docker Engine y Docker Compose v2.
- Un archivo `.env` local (no versionado) con credenciales de PostgreSQL.
- El polígono GeoJSON oficial de cobertura aprobado para producción.
- Para las rutas que los requieren, la configuración vigente de M3 y un proveedor
  de rutas compatible con el adaptador inyectable.

Variables de entorno:

| Variable | Requisito | Uso |
| --- | --- | --- |
| `DB_USER`, `DB_PASS`, `DB_NAME` | Requeridas por Compose | Credenciales y base de datos PostgreSQL. |
| `COVERAGE_GEOJSON` | Requerida para geocodificación y estimación de rutas | Polígono autorizado oficial, serializado como GeoJSON. No usar la geometría de tests. |
| `M3_BASE_URL`, `M3_SERVICE_TOKEN`, `M3_ELIGIBILITY_PATH` | Requeridas juntas para proximidad | URL base, credencial de servicio y ruta acordada; la ruta debe incluir `{conductor_id}`. |
| `M3_TIMEOUT_SECONDS` | Opcional; default `5` | Timeout de la consulta a M3. |
| `MAPS_TIMEOUT_SECONDS` | Opcional; default `5` | Timeout de cálculo de ruta. |
| `GEOCODING_TIMEOUT_SECONDS` | Opcional; default `5` | Timeout del geocoder. |
| `GEOCODING_USER_AGENT` | Opcional | User-Agent requerido por Nominatim. |
| `GEOCODING_MIN_DELAY_SECONDS` | Opcional; default `1.1` | Pausa mínima entre solicitudes al geocoder. |
| `DATABASE_URL`, `REDIS_URL` | Compose las configura para `api` | URLs internas de PostgreSQL y Redis; no se deben publicar. |

Crear `.env` a partir de los nombres anteriores y cargar los valores desde el
gestor de secretos del entorno. No añadir credenciales ni tokens a Git, al
README, a imágenes Docker o a logs. El Compose monta PostgreSQL (`m4db`),
Redis (`redis`) y la API (`api`); Redis es el almacén efímero de ubicaciones con
TTL de 30 segundos. `COVERAGE_GEOJSON` debe contener el polígono aprobado para
el entorno y nunca una cobertura ficticia de desarrollo.

### Arranque reproducible

Desde la raíz del repositorio, con `.env` preparado:

```powershell
docker compose -f Docker-Compose.yml build api
docker compose -f Docker-Compose.yml up -d m4db redis api
docker compose -f Docker-Compose.yml exec -T api alembic upgrade head
docker compose -f Docker-Compose.yml exec -T api python -m pytest -q
```

El Compose publica la API en `http://localhost:8000`. Las pruebas de integración
requieren que PostgreSQL y Redis estén activos. El contrato versionado
`openapi.yml` se monta en el contenedor para que la prueba de contrato valide la
especificación publicada junto con la app. Para detener los servicios sin
eliminar los datos persistidos:

```powershell
docker compose -f Docker-Compose.yml down
```

Las migraciones se aplican explícitamente con Alembic antes de habilitar tráfico.
No se crean tablas automáticamente al importar o iniciar la aplicación.

### Health checks y dependencias externas

- `GET /health/live` devuelve `200` si el proceso está activo y no depende de
  servicios externos.
- `GET /health/ready` ejecuta comprobaciones de PostgreSQL y Redis: devuelve
  `200` cuando ambos responden, o `503` con Problem Details genérico si una
  dependencia crítica no está disponible. La respuesta no incluye direcciones,
  credenciales ni detalles internos.
- La falta de `COVERAGE_GEOJSON` o de un router configurado impide realizar
  operaciones de geocodificación/estimación que dependan de ellos: se falla de
  forma explícita con `503`; no se usa un fallback local. Un timeout del router
  se informa como `504`.
- El proveedor de rutas todavía se entrega por inyección en la aplicación; no
  existe una variable de entorno para seleccionarlo ni debe simularse una URL
  de proveedor en producción. Antes de habilitar endpoints que calculan ETA,
  el entorno debe integrar el adaptador y configurar sus credenciales en el
  mecanismo seguro de despliegue. Sin esa integración, las operaciones fallan
  de forma explícita con `503`.

### Privacidad y observabilidad

Las respuestas de proximidad usan `Cache-Control: no-store`, no incluyen las
coordenadas exactas de los conductores y devuelven `X-Request-Id` para
correlación. Los logs estructurados también propagan ese identificador. El
filtro de redacción elimina coordenadas GPS, URLs absolutas, credenciales y
tokens de los mensajes/campos estructurados, incluidas las líneas de acceso de
Uvicorn. No registrar manualmente cuerpos, query strings ni ubicaciones sin
sanitizar; evitar incorporar datos sensibles en excepciones o mensajes de
proveedores externos.
