'''
En este codigo se realizaran pruebas de respuesta a eventos especificos, concretamente al recibimiento de ciertos 
paquetes de datos json, que veremos como se comportan ante los datos esperados tanto de salida como de entrada.
obligatoriamente tanto el propio archivo como las funciones deben tener el prefijo "test_"
'''
from fastapi.testclient import TestClient #herramienta de fastapi que da soporte similar a postman
from app.main import app  # Asegúrate de que importe tu instancia principal de FastAPI

client = TestClient(app) #trae el modelo de cliente cual utilizamos para realizar el codigo fuente y ejecutar verbos REST

#recordar que en los endpoints normalmente se tienen prefijos definidos, como api/v1 o en este caso piloto /m4
#debe ir el prefijo sino dara error al intentar comprobar la "salida" mediante el decorador en eventos

def test_entrada_correcta():#Pytest solo ejecuta las funciones que empiezan con test, contrario lo ignora.
    """
    Prueba que un evento con coordenadas válidas dentro de la zona 
    (Chaco/Corrientes) responda exitosamente (200 OK).
    """
    entrada = {
        "evento_id": "123e4567-e89b-12d3-a456-426614174000",
        "lat": -27.4512,  # Dentro del rango (-28.5 a -27.2)
        "lon": -58.9866,  # Dentro del rango (-59.5 a -58.7)
        "ubicacion_texto": "Plaza 25 de Mayo, Resistencia"
    } #definicion de diccionario que luego se convertira en json en la variable respuesta
    
    respuesta = client.post("/PruebaM4/Piloto", json=entrada) #realiza la peticion con el head y body adecuados
    #luego de simular todo el codigo, captura el HTTP en la variable respuesta
    # Validamos el éxito del contrato de schemas con assert de la sigueinte manera 
    assert respuesta.status_code == 200 #valida que 
    diccionariojson = respuesta.json() #convierte en diccionario el json del body
    assert diccionariojson["estado"] == "PROCESADO_EXITOSAMENTE"
    assert diccionariojson["evento_id"] == "123e4567-e89b-12d3-a456-426614174000"
    # Verificamos que el módulo externo simulado haya devuelto el ID correcto
    assert diccionariojson["detalles_externos"]["modulo_origen_id"] == "123e4567-e89b-12d3-a456-426614174000"
    #linea 30 valida que la respuesta de la simulacion de peticion dentro de procesador de eventos, sea igual al definido


def test_entrada_invalida():
    """
    Prueba que si mandamos coordenadas fuera de la zona permitida 
    (ej: Buenos Aires), el negocio rechace el evento con un código 400.
    """
    entrada = {
        "evento_id": "123e4567-e89b-12d3-a456-426614174000",
        "lat": -34.6037,  # Buenos Aires (fuera de zona)
        "lon": -58.3816,
        "ubicacion_texto": "Obelisco"
    }
    
    respuesta = client.post("/PruebaM4/Piloto", json=entrada)
    
    # Verificamos que devuelva codigo de error de negocio (400)
    assert respuesta.status_code == 400
    assert "fuera de la zona de cobertura" in respuesta.json()["detail"] #podemos validar incluso el string de respuesta


def test_errorDeContrato():
    """
    Prueba que si mandamos datos mal formados (ej: texto en lugar de número 
    en la latitud), Pydantic bloquee la entrada con un código 422.
    """
    entrada = {
        "evento_id": "123e4567-e89b-12d3-a456-426614174000",
        "lat": "esto-no-es-un-numero",  # Tipo de dato inválido para el contrato
        "lon": -58.9866
    }
    
    respuesta = client.post("/PruebaM4/Piloto", json=entrada)
    
    # verificamos que recibimos el mismo codigo que el definido
    assert respuesta.status_code == 422