# Tests unitarios del Módulo 4

Ejecutar desde la raíz con el entorno del proyecto activado:

```powershell
pytest tests/unitarios -v
```

No se importa `app.main`, se instancia FastAPI, se usa TestClient ni se hacen
peticiones HTTP. Los servicios que usan infraestructura se cargan con módulos
sustitutos bajo `patch.dict`; los modelos/cache y `NotFoundError` de Redis se
reemplazan por fakes en memoria. No se conecta a PostgreSQL ni a Redis.
Archivos, reloj, esperas, geocodificadores y persistencia se sustituyen por
mocks. Los handlers se invocan directamente con objetos simples y una app mock.

Los tests de esquemas cubren nombres de campos, obligatoriedad, límites y enums
del `openapi.yml` vigente. Los tests de servicios comprueban las transiciones
unitarias, errores HTTP y TTL con dependencias simuladas.

Si coverage está instalado, medir por ramas los módulos aislados:

```powershell
coverage run --branch --source=app.esquemas,app.servicios,app.errores,app.seguridad.idempotenciaManager -m pytest tests/unitarios -v
coverage report -m
```

El objetivo de menos de dos segundos debe medirse en el entorno de ejecución.
No se pudo ejecutar aquí: el intérprete del entorno virtual apunta a una ruta
fuera del sandbox y se rechazó la aprobación para ejecutarlo.
