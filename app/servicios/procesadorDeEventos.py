'''
========================================

Este modulo realiza el codigo de procesamiento de eventos, es decir, la logica de negocio que se ejecuta cuando se recibe un evento en la api
y que se encuentra en el modulo de enrutador/eventos.py, basicamente hace todo el formateo de datos y calculos.

========================================

'''
import os
from datetime import datetime

ZONA_PERMITIDA = {
    "lat_min": -28.5000,  # Límite Sur (ej: zona Empedrado)
    "lat_max": -27.2000,  # Límite Norte (ej: norte de Resistencia)
    "lon_min": -59.5000,  # Límite Oeste 
    "lon_max": -58.7000   # Límite Este
}

def validar_coordenadas(lat: float, lon: float) -> bool:
    """
        Verifica si las coordenadas caen dentro de la región permitida.
        es decir que si quiere ir a jamaica, no podra.

        aqui iria la implementacion con GEOPY o el framework de geolocalizacion externa de codigo abierto
        para lograr parcear los strings y/o los limietes de coordenadas del cuadrante valido geografico
        en este caso comprende la ZONA PERMITIDA que se encuentra como "constante" en la linea 13, con lo cual 
        decimos "la regla estricta de negocio es que solo se puedan realizar viajes desde norte de resistencia
        hasta empedrado, si necesitas mas de eso fuiste"
    """
    return (
        ZONA_PERMITIDA["lat_min"] <= lat <= ZONA_PERMITIDA["lat_max"] and
        ZONA_PERMITIDA["lon_min"] <= lon <= ZONA_PERMITIDA["lon_max"]
    )
    #si es verdadero todo bien, sino todo mal y se retornara un error 422 en la api, es decir
    #que el cliente o "algien" mando datos invalidos y es su culpa, no de la api.

async def simular_comunicacion_modulo_externo_prueba(entrada: dict) -> dict:
    """
    funcion que simula la solicitud de datos hacia otro módulo externo.
    en el futuro, esto se reemplazará por un cliente HTTP (httpx) real que es que hara la solicitud a otro microservicio 
    y que recibira una respuesta con datos.
    actualmente solo sirve para simular la comunicacion y devolver un resultado de prueba
    resultado que sirve para dar "explicaciones" adicionales sobre el evento y como comunicarse con el modulo externo.
    supongo que en el futuro, las comunicaciones empesaran mandando palabras clave y devolviendo datos complejos,
    es decir, mandamos "evento_id" y nos devuelven cosas correspondiente a ESE id evento.
    """
    id_origen=entrada.get("evento_id")
    return {
        "modulo_origen_id": id_origen,
        "datos_enriquecidos": "Información adicional procesada por el socio externo"
    }

    '''
    este dato de retorno, debe ser compatible con alguna definicion del schema, es decir que debe ser un diccionario con los 
    datos que se esperan en el schema de salida, para que la api pueda devolverlo al cliente
    aqui si hiciera falta el modulo simulado haria un procesamiento de datos con la variable parametrizada "entrada"
    '''

async def procesarEventoPrueba(datos_entrada: dict) -> dict:
    
    '''
    Función especifica que coordina todo el flujo de procesamiento de la señal.
    y devuelve un resultado especifico con un formato especifico que necesita alguien o algo
    es decir que es un contrato de datos que se debe cumplir.
    '''

    '''
    sacamos los datos del diccionario de entrada y colocamos en variables locales de la funcion 
    para poder trabajar con ellos y hacer los calculos o validaciones necesarias.
    '''

    evento_id = datos_entrada.get("evento_id")
    ubicacion_texto = datos_entrada.get("ubicacion_texto")
    lat=datos_entrada.get("lat")
    lon=datos_entrada.get("lon")

    #comprobamos las coordenadas
    if not validar_coordenadas(lat, lon): 
        # Si está fuera de rango, lanzamos una excepción que el router o FastAPI atrapara
        raise ValueError("La ubicación se encuentra fuera de la zona de cobertura permitida (Chaco/Corrientes).")

    '''
    simulamos interaccion o comunicacion con otro modulo externo, que nos devolvera datos adicionales
    esto puede estar tranquilamente mas arriba si es que nos devolviera datos que necesitamos para 
    validar las coordenadas, pero en este caso no es asi, solo es un ejemplo
    '''

    datos_externos = await simular_comunicacion_modulo_externo_prueba({"evento_id": evento_id})

    # ahora formateamos los datos para "entregar" a quien lo requiera.
    resultado_final = {
        "evento_id": evento_id,
        "estado": "PROCESADO_EXITOSAMENTE",
        "ubicacion_procesada": ubicacion_texto,
        "detalles_externos": datos_externos,
        "mensaje": "Señal procesada bajo las normas del microservicio."
    }
    return resultado_final
