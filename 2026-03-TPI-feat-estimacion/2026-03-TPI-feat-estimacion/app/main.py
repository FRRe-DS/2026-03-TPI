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

#usamos el middleware para lograr respetar el string necesario en el head que documenta el contrato
@app.middleware("http")
async def agregar_o_respetar_request_id(request: Request, call_next):
    #Obtenemos el header que mandó el cliente
    xrequest_id = request.headers.get("x-request-id")
    
    #Si no vino O no cumple con el formato del contrato, generamos uno nuevo
    if not xrequest_id or not REQUEST_ID_PATTERN.match(xrequest_id):
        xrequest_id = str(uuid.uuid4())

    #Lo guardamos en request.state para que handlerManage.py lo use como trace_id
    request.state.request_id = xrequest_id

    #Mostramos en la terminal (logs) la petición junto con su ID de rastreo (alineado con RNF-14)
    logger.info(
        f"Endpoint: {request.method} {request.url.path} | X-Request-ID: {xrequest_id}"
    )

    #Dejamos que la petición continúe su camino hacia los endpoints
    response = await call_next(request)

    #Inyectamos obligatoriamente el X-Request-ID en las cabeceras de la respuesta (éxito o error)[cite: 1]
    response.headers["x-request-id"] = xrequest_id

    return response

'''
la idea es crear tantas delegaciones de prefijos especializados en funcionalidades, de esa manera centralizamos
funcionalidades y creamos tantos .py por funcionalidad especifica o responsabilidad especifica para modular 
el codigo, si algo saliera mal no haria falta buscar tanto codigo o como premisa se sabria que modulo fallo en 
cumplir su responsabilidad asociada.

'''
ruta1 = APIRouter(prefix="/api/v1",tags=["Ubicaciones"])
ruta2 = APIRouter(prefix="/api/v1",tags=["Geocodificacion"])
ruta3 = APIRouter(prefix="/api/v1",tags=["Rutas"])
ruta4 = APIRouter(prefix="/api/v1",tags=["Disponibilidad"])
ruta5 = APIRouter(prefix="/health",tags=["Salud"])

@ruta2.post("/geocodificaciones",response_model=ResultadoGeocodificacion,status_code=200,
            description="Consulta realizada; coincidencias puede ser una lista vacía.")
def RealizarGeocodificacion(datos:ConsultaGeocodificacion):
    #si regla de negocio dictara solo argentina entonces aqui va la validacion y si da error es 422
    resultado=obtener_coordenadas(datos)
    return resultado

@ruta3.get(
    "/rutas/estimacion",
    response_model=ResultadoEstimacionRuta,
    status_code=status.HTTP_200_OK,
    summary="Estimar distancia y tiempo entre origen y destino",
    description="Consumido por M5 (despacho), M7 (tarifas) y M9 (reservas)",
)
def RealizarCalculosEstimados(
    origen_latitud: float = Query(..., ge=-90.0, le=90.0),
    origen_longitud: float = Query(..., ge=-180.0, le=180.0),
    destino_latitud: float = Query(..., ge=-90.0, le=90.0),
    destino_longitud: float = Query(..., ge=-180.0, le=180.0),
    tipo_vehiculo: Optional[VehiculosSoportados] = Query(
        default=VehiculosSoportados.AUTO
    ),
):
    datos = ConsultaEstimacionRuta(
        origen_latitud=origen_latitud,
        origen_longitud=origen_longitud,
        destino_latitud=destino_latitud,
        destino_longitud=destino_longitud,
        tipo_vehiculo=tipo_vehiculo,
    )
    return CalculosDeViaje(datos)


app.include_router(ruta1)
app.include_router(ruta2)
app.include_router(ruta3)
app.include_router(ruta4)
app.include_router(ruta5)



