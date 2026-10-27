# Agent Context: Módulo 4 - Ubicación y Disponibilidad (TPI 2026)

## 🎯 Propósito del Módulo
El Módulo 4 (M4) gestiona la posición vigente de los conductores, su disponibilidad operativa, proximidad, cálculo de distancias y ETA (Estimated Time of Arrival) en una plataforma distribuida de movilidad urbana bajo demanda.

## 🛠️ Stack Tecnológico
- **Lenguaje:** Python 3.11-slim (contenedores Docker)
- **Framework:** FastAPI
- **Base de Datos / ORM:** PostgreSQL 15-alpine + SQLAlchemy + Alembic (migraciones)
- **Geocodificación y Rutas:** geopy (Nominatim / servicios locales)
- **Validación y Configuración:** Pydantic y Pydantic-Settings
- **Testing:** PyTest

## 📁 Estructura del Repositorio
- `app/main.py`: Punto de entrada de FastAPI.
- `app/database.py`: Configuración del motor y sesión de SQLAlchemy.
- `app/models.py`: Modelos ORM (`RegistroSolicitud`, `ConductorTiempoReal`).
- `app/schemas.py`: Contratos de validación con Pydantic.
- `app/enrutador/`: Endpoints REST bajo el prefijo `/api/v1/`.
- `tests/`: Pruebas unitarias e de integración con PyTest.
- `openapi.yml`: Contrato OpenAPI de referencia (Ley Suprema).


## 📌 Normas de Desarrollo
1. **Spec-Driven Development (SDD):** Ninguna ruta o lógica de negocio debe implementarse sin estar alineada con el contrato `openapi.yml`.
2. **Manejo de Errores:** Las respuestas de error deben estructurarse bajo el estándar RFC 7807 (Problem Details).
3. **Trazabilidad:** Toda respuesta debe incluir u obligatoriamente propagar el header `X-Request-Id`.
4. **Pruebas Unitarias:** Cada nueva funcionalidad o regla de negocio debe estar acompañada de su respectivo test en `tests/` ejecutado con PyTest vía Docker (`docker-compose exec api python -m pytest -v`).