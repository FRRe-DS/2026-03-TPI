""""
============================================================
Este archivo es el punto de entrada de la aplicación FastAPI.
Aquí se inicializa la base de datos y se crean las tablas definidas en models.py.
Tambien se configura la aplicación FastAPI y se definen los endpoints principales.
Asi como la inyeccion de dependencias para la base de datos.
Y codigo autoejecutable segun decoradores, los cuales responden a los endpoints de la API.
============================================================
"""
from app.db.database_config import engine, Base #se importan para crear las tablas en la base de datos, y para poder realizar consultas a la bd
from app.modelos import db_models #se importa models para que se ejecute el codigo de models.py y se creen las tablas en la base de datos
from fastapi import FastAPI, Request, APIRouter, Depends, status, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
import logging,uuid,re
from app.esquemas.esquemas import *
from app.errores.handlerManager import registrar_manejadores_excepciones
from app.servicios.cadenaDeProveedores import AdaptadorEncadenado
from app.servicios.calculosDeEstimacion import CalculosDeViaje
from app.servicios.manejarReserva import RegistrarReserva
from app.servicios.actualizarUbicacion import ActualizarUbicacionService
from app.servicios.candidatosCercanos import CandidatosCercanos
from app.seguridad.idempotenciaManager import verificar_idempotencia
from app.servicios.actEstadoOperativo import ServicioEstadoOperativo
from app.errores.exceptionsSemanticos import ErrorHealthCheck
from app.db.cache_config import cache
from app.servicios.calculosDeEstimacion import CalculosDeViaje
from app.logs.logs_config import configurar_logging
from app.seguridad.authManager import verificar_roles
from app.seguridad.rate_limit_config import verificar_rate_limit

configurar_logging()
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine) #si no habia una tabla, la crea, si ya existia, no hace nada. 
#Esto es para inicializar la base de datos y crear las tablas que se definan en models.py que hereden de Base.

REQUEST_ID_PATTERN = re.compile(r'^[A-Za-z0-9._-]{1,128}$')
# Configuración básica para que los mensajes salgan en tu terminal (consola)

# Instanciamos la aplicación principal de FastAPI
app = FastAPI(
    title="M4 - Ubicación y Disponibilidad",
    description="API encargada del rastreo de entidades",
    version="1.0.0")
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
    logger.info("[trace_id=%s]|Peticion recibida|metodo=%s|ruta=%s",xrequest_id,request.method,request.url.path,)
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
ruta1 = APIRouter(prefix="/api/v1/",tags=["Ubicaciones"])
ruta2 = APIRouter(prefix="/api/v1/",tags=["Geocodificacion"])
ruta3 = APIRouter(prefix="/api/v1/",tags=["Rutas"])
ruta4 = APIRouter(prefix="/api/v1/",tags=["Disponibilidad"])
ruta5 = APIRouter(prefix="/health/",tags=["Salud"])
adaptadorJerarquico = AdaptadorEncadenado()

@ruta1.put("conductores/{conductor_id}/ubicacion",response_model=UbicacionRegistrada,
            dependencies=[Depends(verificar_roles("conductores-be", "ubicacion-be")),
            Depends(verificar_rate_limit("actualizar_ubicacion"))])
def endpoint_actualizar_ubicacion(conductor_id: UUID,datos: ActualizarUbicacion,response: Response,request: Request):
    # Delegamos la lógica al servicio
    resultado, es_nuevo = ActualizarUbicacionService.procesar(conductor_id, datos, trace_id=request.state.request_id,)
    # Definimos el código de éxito según corresponda al contrato
    response.status_code = status.HTTP_201_CREATED if es_nuevo else status.HTTP_200_OK
    return resultado

@ruta2.post("geocodificaciones",response_model=ResultadoGeocodificacion,
            dependencies=[Depends(verificar_roles("solicitud-be", "ubicacion-be")),
            Depends(verificar_rate_limit("geocodificar"))],
            status_code=200,
            description="Consulta realizada; coincidencias puede ser una lista vacía.")
def RealizarGeocodificacion(datos:ConsultaGeocodificacion,request: Request,response:Response):
    response.headers["Cache-Control"] = "no-store"
    logger.info("[trace_id=%s]|Consulta de geocodificacion",request.state.request_id,)
    resultado = adaptadorJerarquico.resolver(datos,trace_id=request.state.request_id,)
    return resultado

@ruta3.get("rutas/estimacion",response_model=ResultadoEstimacionRuta,
            dependencies=[Depends(verificar_roles("solicitud-be", "tarifas-be", "reservas-be", "ubicacion-be")),
            Depends(verificar_rate_limit("estimar_ruta"))],
            status_code=status.HTTP_200_OK,
            summary="Estimar distancia y tiempo entre origen y destino",)
def RealizarCalculosEstimados(origen_latitud: float,origen_longitud: float,destino_latitud: float,destino_longitud: float,
    tipo_vehiculo: VehiculosSoportados,request:Request):
    query = QueryEstimacionRuta(origen_latitud=origen_latitud,
                                origen_longitud=origen_longitud,
                                destino_latitud=destino_latitud,
                                destino_longitud=destino_longitud,
                                tipo_vehiculo=tipo_vehiculo,)
    logger.info("[trace_id=%s]|Consulta de calculo de tiempo/distancia estimados|tipo_vehiculo=%s",request.state.request_id,query.tipo_vehiculo,)
    return CalculosDeViaje(query,trace_id=request.state.request_id)

#TODO: falta implementar reserva
#TODO:posiblemente deberia colocar dentro del decorador del endpoint el Depends(verificar_rol("disponibilidad-be")) 
#TODO:para que se ejecute la verificacion de rol y si no cumple con el rol requerido, se lanza un error y ni entra en el endpoint
"""dependencies=[Depends(verificar_roles("solicitud-be", "ubicacion-be")),Depends(verificar_rate_limit("reservar_conductor")),]"""
@ruta4.post("conductores/{conductor_id}/reserva",response_model=SolicitudReserva,status_code=201,description="La reserva temporal se creó para esta solicitud.",)
async def RealizarReserva(datos:SolicitudReserva,idempotency_key: str = Depends(verificar_idempotencia)):
    resultado=RegistrarReserva()
    return resultado

@ruta4.get("conductores/cercanos", response_model=ResultadoBusquedaConductores,
        dependencies=[Depends(verificar_roles("solicitud-be", "ubicacion-be")),
        Depends(verificar_rate_limit("buscar_conductores_cercanos"))],
        status_code=200,
        description="Búsqueda realizada; conductores puede ser lista vacía si no hay candidatos en ningún radio.")
def BuscarConductoresCercanos(request:Request,response:Response,origen_latitud:float,origen_longitud:float,tipo_vehiculo:VehiculosSoportados,limite:int|None = None,):
    # Contrato exige Cache-Control: no-store (respuesta contiene coordenadas/ubicación)
    response.headers["Cache-Control"] = "no-store"
    query=QueryCercanos(origen_latitud=origen_latitud,
                        origen_longitud=origen_longitud,
                        tipo_vehiculo=tipo_vehiculo,
                        limite=limite,)
    logger.info("[trace_id=%s]|Consulta conductores cercanos|tipo_vehiculo=%s|limite=%s",request.state.request_id,query.tipo_vehiculo,query.limite,)
    resultado = CandidatosCercanos.buscar(query,trace_id=request.state.request_id)
    return resultado

@ruta4.put("conductores/{conductor_id}/estado-operativo",response_model=EstadoOperativoRegistrado,
        dependencies=[Depends(verificar_roles("conductores-be", "ubicacion-be")),
        Depends(verificar_rate_limit("buscar_conductores_cercanos"))])
def actualizarEstadoOperativo(request: Request,response: Response,conductor_id: UUID,body: EstadoOperativo):
    resultado, es_nuevo = ServicioEstadoOperativo.actualizar_estado(conductor_id=conductor_id,body=body,trace_id=request.state.request_id,)
    response.status_code = status.HTTP_201_CREATED if es_nuevo else status.HTTP_200_OK
    return resultado

@ruta5.get("live", status_code=200)
def consultar_liveness():
    """
    LIVENESS:
    Valida únicamente que el servidor de FastAPI esté respondiendo. 
    No consulta bases de datos para evitar reinicios innecesarios en bucle por problemas de red pasajeros.
    """
    return {"status": "UP"}

@ruta5.get("ready", status_code=200)
def consultar_readiness():
    """
    READINESS:
    Verifica la salud operativa de las dependencias críticas:
    1. PostgreSQL (via SQLAlchemy engine)
    2. Redis (via cliente de caché)
    Si alguna falla, dispara una excepción semántica que el manejador global traduce a 503.
    """
    
    # 1. Validación de PostgreSQL (m4db) usando el engine configurado en database_config
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        raise ErrorHealthCheck(
            detail="No se pudo establecer conexión con la base de datos relacional."
        )

    # 2. Validación de Redis (m4cache) usando tu objeto 'cache' de cache_config
    try:
        # El comando ping() verifica si el servidor Redis responde correctamente
        cache.ping()
    except Exception as e:
        raise ErrorHealthCheck(
            detail="El motor de caché Redis no responde a las solicitudes de ping.")

    return {"status": "READY"}

for router in (ruta1, ruta2, ruta3, ruta4, ruta5):
    app.include_router(router)
