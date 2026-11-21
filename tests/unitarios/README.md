# Tests unitarios del Módulo 4

Ejecutar desde la raíz con el entorno del proyecto activado:

```powershell
pytest tests/unitarios -v
```

No se importa `app.main`, se instancia FastAPI, se usa TestClient ni se hacen
peticiones HTTP. Los servicios que importan infraestructura se cargan con
módulos sustitutos bajo `patch.dict`, sin ejecutar configuración ni modelos Redis.
Archivos, reloj, esperas, geocodificador y persistencia se sustituyen por mocks.
Los handlers se invocan directamente con objetos simples y una app mockeada.

## Limitaciones detectadas en el código de producción

- `CalculosDeViaje` contiene `pass`. No existen velocidades para AUTO/MOTO.
- `RegistrarReserva` contiene `pass`, sin parámetros ni operaciones de persistencia.
- La cadena propaga errores locales en lugar de consultar el proveedor externo.
- Idempotencia intenta leer `body_hash` de la clave string en lugar del registro;
  además usa `status_code` aunque el modelo declara `status`.

Los contratos afectados usan `xfail(strict=True)` y restringen el tipo de error
esperado. No representan funcionalidades verificadas: un XPASS exige revisar
la prueba al implementar/corregir el servicio. Los tests de rutas definen una
posible integración con geodesic; la fórmula de ETA necesita velocidades oficiales.
No puede afirmarse cobertura funcional completa mientras existan estos pendientes.

Si coverage está instalado, medir por ramas los módulos aislados:

```powershell
coverage run --branch --source=app.esquemas,app.servicios,app.errores,app.seguridad.idempotenciaManager -m pytest tests/unitarios -v
coverage report -m
```

El objetivo de menos de dos segundos debe medirse en el entorno de ejecución.
No se pudo ejecutar aquí: el intérprete del entorno virtual apunta a una ruta
fuera del sandbox y se rechazó la aprobación para ejecutarlo.
