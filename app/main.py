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
from fastapi import FastAPI, Request
from app.enrutador.eventos import prueba #importamos los eventos sobre el el codigo fuente, para que "reconosca" lo segregado en el otro .py
import logging
import uuid



Base.metadata.create_all(bind=engine) #si no habia una tabla, la crea, si ya existia, no hace nada. 
#Esto es para inicializar la base de datos y crear las tablas que se definan en models.py que hereden de Base.


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

#usamos el middleware para lograr respetar el string necesario en el head que documenta el contrato
@app.middleware("http")
async def agregar_o_respetar_request_id(request: Request, call_next):
    # 1. ¿El cliente (Node.js u otro) mandó el header x-request-id?
    # Si vino, lo usamos. Si no vino (viene vacío o None), generamos uno nuevo.
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

    # 2. Mostramos en la terminal (logs) la petición junto con su ID de rastreo
    logger.info(
        f"Endpoint: {request.method} {request.url.path} | X-Request-ID:"
        f" {request_id}"
    )

    # 3. Dejamos que la petición continúe su camino hacia tus endpoints (ej. /ubicaciones)
    response = await call_next(request)

    # 4. Inyectamos obligatoriamente el X-Request-ID en las cabeceras (headers) de la respuesta
    response.headers["x-request-id"] = request_id

    return response

'''
la idea es crear tantas delegaciones de prefijos especializados en funcionalidades, de esa manera centralizamos
funcionalidades y creamos tantos .py por funcionalidad especifica o responsabilidad especifica para modular 
el codigo, si algo saliera mal no haria falta buscar tanto codigo o como premisa se sabria que modulo fallo en 
cumplir su responsabilidad asociada.

'''

app.include_router(prueba, prefix="/PruebaM4") #aseguramos que el prefijo tanbien llegue aqui

# Endpoint raíz para verificar que la API está viva, luego de implementar separacion de responsabilidades en el codigo, es prescindible
@app.get("/") #si viene "/" en el navegador, le aplicara app.get y el codigo debajo
def read_Home():
    return {
        "estado": "activo",
        "mensaje": "M4 corriendo correctamente en Docker"
    }