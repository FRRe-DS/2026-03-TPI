# # Sistema de Gestión de Logística y Viajes (TPI 2026)

Plataforma distribuida de movilidad urbana bajo demanda

## 🚀 Integrantes - Grupo 03

* Acevedo Gomez, Amparo.
* Claver Gallino, Samira.
* Echeverria Melgratti, Lautaro.
* Gonzalez, Micaela.
* Sanchez, Abigail.
* Franco Quiroz, Facundo Agustin.
* Rocio V. Ramirez

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
* **Lenguaje:** Python 3.12.4
* **Framework:** FastApi: Framework moderno y liviano, desarrollado para construccion de API REST y comunicacion de las mismas.
    *  **Dependencias auxiliares:**
        * SQLAlchemy: ORM de base de datos modelo SQL.
        * PyMySQL: Driver para que el ORM detecte y conecte la base de datos.
        * Alembic: Control de migraciones de la base de datos en caso de ser necesario un versionado de la misma.
        * httpx: Soporte para eventos asincronicos en caso de ser necesario
        * Uvicorn: Soporte asincronico de ASGI web server, cual permite ejecucion sobre el codigo en la api
        * Pydantic-Settings: Dependencia de mapeo sobre datos de los entornos, abstrae datos y aumenta seguridad.
* **Control de Versiones:** Git & GitHub
