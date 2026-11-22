""""
============================================================
Este archivo es el punto de entrada de la aplicación FastAPI.
Aquí se inicializa la base de datos y se crean las tablas definidas en models.py.
Tambien se configura la aplicación FastAPI y se definen los endpoints principales.
Asi como la inyeccion de dependencias para la base de datos.
Y codigo autoejecutable segun decoradores, los cuales responden a los endpoints de la API.
============================================================
"""
from fastapi import FastAPI, Request, APIRouter, Query, status
import logging,uuid,re
from typing import Optional
from app.esquemas.esquemas import (
    ConsultaGeocodificacion,
    ResultadoGeocodificacion,
    ConsultaEstimacionRuta,
    ResultadoEstimacionRuta,
    VehiculosSoportados,
)
from app.errores.handlerManager import registrar_manejadores_excepciones
from app.servicios.geocodificacion import obtener_coordenadas
from app.servicios.calculosDeEstimacion import CalculosDeViaje

REQUEST_ID_PATTERN = re.compile(r'^[A-Za-z0-9._-]{1,128}$')
# Configuración básica para que los mensajes salgan en tu terminal (consola)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("m4_backend")

# Instanciamos la aplicación principal de FastAPI
app = FastAPI(
    title="M4 - Ubicación y Disponibilidad",
    description="API encargada del rastreo de entidades",
    version="1.0.0"
)
#vinculamos los handlers de errores y excepciones personalizados
registrar_manejadores_excepciones(app)


ruta1 = APIRouter(prefix="/api/v1/",tags=["Ubicaciones"])
ruta2 = APIRouter(prefix="/api/v1/",tags=["Geocodificacion"])
ruta3 = APIRouter(prefix="/api/v1/",tags=["Rutas"])
ruta4 = APIRouter(prefix="/api/v1/",tags=["Disponibilidad"])
ruta5 = APIRouter(prefix="/health/",tags=["Salud"])


@ruta3.get("rutas/estimacion",response_model=ResultadoEstimacionRuta,status_code=status.HTTP_200_OK,
    summary="Estimar distancia y tiempo entre origen y destino",)
def RealizarCalculosEstimados(origen_latitud: float = Query(..., ge=-90.0, le=90.0),
    origen_longitud: float = Query(..., ge=-180.0, le=180.0),
    destino_latitud: float = Query(..., ge=-90.0, le=90.0),
    destino_longitud: float = Query(..., ge=-180.0, le=180.0),
    tipo_vehiculo: Optional[VehiculosSoportados] = Query(default=VehiculosSoportados.AUTO),):

    respuesta = ConsultaEstimacionRuta(origen_latitud=origen_latitud,origen_longitud=origen_longitud,
        destino_latitud=destino_latitud,destino_longitud=destino_longitud,tipo_vehiculo=tipo_vehiculo,)
    return CalculosDeViaje(respuesta)

for router in (ruta1, ruta2, ruta3, ruta4, ruta5):
    app.include_router(router)


