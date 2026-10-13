"""
=============================================

Este modulo de codigo, realiza la "respuesta" y "comprobacion" de eventos que recibe la api, repescto 
a la sintaxis definida en schema que es consecuentemente el "contrato" que se debe cumplir los datos para tomarlos
como datos validos y procesables, de lo contrario se retornara un error 422
que es el estandar de fastapi para este tipo de errores.

==============================================

"""
from fastapi import APIRouter, HTTPException #modulos de fastapi para crear rutas y manejar excepciones
from app.schemas.schemas import EventoPruebaEntrada, EventoPruebaSalida #modulos de evento de entrada y salida que se definen en el schema
from app.servicios.procesadorDeEventos import procesarEventoPrueba #aqui se importan las funciones o clases que determinan la respuesta o logica del evento a procesar

prueba = APIRouter(tags=["PruebaPilotoM4"]) # atajo para crear rutas url con prefijo /eventos 
#y tag "Eventos" en el swagger que es la UI por defecto de fasapy

'''
segun el decorador y lo que le sigue del . podemos manipular el tipo de desencadenante y validacion openapi
que se definio en schemas, existen 2 formas de validacion, las de entrada y salida de la api,
otra cosa es que las peticiones POST pueden recibir "cuerpo" o BODY con datos estructurados, en este caso 
los .json o diccionarios por lo que por mas que "pidamos" o "devolvamos" informacion, normalmente usaremos POST.

estrucutra del decorador las cuales son las siguientes:

@router.post("/", response_model=EventoRespuesta) # <--- Aqui se valida datos de salida
async def recibir_senal(evento: EventoEntrada): # <--- Aqui se valida datos de entrada

como se observa las validaciones tienen un caracter abajo hacia arriba.


decorador que indica que esta funcion es un endpoint POST, con respuesta del modelo EventoRespuesta
el decorador ejecuta el codigo siguiente cuando se recibe un evento en la ruta /eventos, y 
valida que el evento cumpla con el esquema definido en EventoEntrada

'''
@prueba.post("/Piloto", response_model=EventoPruebaSalida) 
async def recibir_evento(evento: EventoPruebaEntrada): #es asincrona para poder manejar multiples eventos al mismo tiempo, recibe un evento de tipo EventoEntrada
    try:
        resultado = await procesarEventoPrueba(evento.dict())# llama a la funcion procesarEventoPrueba, 
        #que es asincrona, y le pasa el evento convertido a diccionario
        #para que lo procese y devuelva un resultado, es decir realiza el formateo de datos
        return resultado
    except ValueError as ve: #en el procesador de eventos definimos valueError como la coordenada en jamiaca, es decir msn=no es posible
        #si llego un el tipo de dato correcto pero no dentro de los parametros o valores aceptados aqui lo mencionamos
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:#si por algun motivo falla devolvera error de servidor 500, con el detalle del error
        raise HTTPException(status_code=500, detail=str(e))
    #si falla la funcion, devolvera 500, si falla el tipo de dato, devolvera 422, si todo sale bien devolvera 200 con el resultado del procesamiento del evento
