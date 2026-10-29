""""
============================================================
Este archivo es el punto de entrada de la aplicación FastAPI.
Aquí se inicializa la base de datos y se crean las tablas definidas en models.py.
Tambien se configura la aplicación FastAPI y se definen los endpoints principales.
Asi como la inyeccion de dependencias para la base de datos.
Y codigo autoejecutable segun decoradores, los cuales responden a los endpoints de la API.
============================================================
"""
from .database import engine, Base #se importan para crear las tablas en la base de datos, y para poder realizar consultas a la bd
from . import models #se importa models para que se ejecute el codigo de models.py y se creen las tablas en la base de datos
from fastapi import FastAPI, Request, APIRouter, HTTPException
import logging
import uuid
from app.schemas.schemas import ConsultaGeocodificacion,ResultadoGeocodificacion
from .handlerManager import registrar_manejadores_excepciones
from app.servicios.geocodificacion import obtener_coordenadas
import re
Base.metadata.create_all(bind=engine) #si no habia una tabla, la crea, si ya existia, no hace nada. 
#Esto es para inicializar la base de datos y crear las tablas que se definan en models.py que hereden de Base.

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
ruta5 = APIRouter(prefix="/health/",tags=["Salud"])

@ruta2.post("/geocodificaciones",response_model=ResultadoGeocodificacion,status_code=200,description="Consulta realizada; coincidencias puede ser una lista vacía.")
def RealizarGeocodificacion(datos:ConsultaGeocodificacion):
    #si regla de negocio dictara solo argentina entonces aqui va la validacion y si da error es 422
    resultado=obtener_coordenadas(datos)
    return resultado


