'''
================================================
En este archivo de codigo estaran los esquemas de contratos definidos por nosotros,
mas concretamente en formato de pydantic el cual mapea clases declaradas en python
para luego realizar contratos en rest o openAPI tengo entendido.
================================================

'''
from pydantic import BaseModel, Field, field_validator #importantes para decirle a fastapi que debe validar y restrigir a quienes las usan
from typing import List,Optional # para determinar si es opcional el contenido de un campo, es decir puede ser null o none
from uuid import UUID
from datetime import datetime
from enum import Enum

'''
importante, si un dato no viene y DEBE fallar, es decir es obligatorio el dato, debe ir ... en field si o si
'''
class EstadoTmp(str,Enum):
    RESERVADO="RESERVADO"
    LIBERADO="LIBERADO"

class Coordenada(BaseModel):
    latitud: float = Field(..., ge=-90.0, le=90.0, description="Latitud en grados decimales")
    longitud: float = Field(..., ge=-180.0, le=180.0, description="Longitud en grados decimales")

class FuenteInfo(str,Enum):
    MAPA="MAPA"
    ESTIMACION_LOCAL="ESTIMACION LOCAL"

class VehiculosSoportados(str,Enum):
    AUTO="AUTO"
    MOTO="MOTO"

class ConsultaGeocodificacion(BaseModel):
    direccion: str = Field(..., min_length=1, description="Calle y altura")
    provincia: str = Field(description="Provincia o región")
    pais: str = Field(..., min_length=2, max_length=2, description="Código ISO de país de 2 letras (ej. ar)")

    @field_validator('direccion', 'provincia', 'pais')
    @classmethod
    def validar_textos_no_vacios(cls, v: str) -> str:
        # v ya es un string garantizado por Pydantic. 
        # Verificamos que no esté vacío tras quitarle espacios a los costados.
        if not v.strip():
            raise ValueError("El campo no puede estar vacío o contener solo espacios en blanco.")
        return v.strip()
    
    @field_validator('pais')
    @classmethod
    def validar_codigo_pais(cls, v: str) -> str:
        v_limpio = v.strip().lower()
        
        if len(v_limpio) != 2:
            raise ValueError("El código de país debe tener exactamente 2 caracteres (estándar ISO alfa-2).")
            
        """
        si fuera necesario si o si que sea argentino
        if v_limpio != "ar":
            raise ValueError("El país debe ser 'ar' (Argentina) según la cobertura de la región.")
            """
            
        return v_limpio

class CoincidenciasGeolocalizacion(BaseModel):
    latitud: float =Field(...,ge=-90,le=90,description="latitud resultante con limitancias terricolas")
    longitud: float =Field(...,ge=-180,le=180,description="longitud resultante con limitancias terricolas")
    etiqueta: str =Field(...,description="direccion lenguaje natural el cual se asocia la coordenada")
    confianza: int =Field(ge=0,le=1)
    #son cosas que nos devuelve el servicio externo o el diccionario de ubicaciones, no es posible dejarlos en blanco

class ResultadoGeocodificacion(BaseModel):
    coincidencias:List[CoincidenciasGeolocalizacion] = Field(description="puede devolver vacio")

class ConsultaEstimacionRuta(BaseModel):
    origen_latitud: float = Field(...,ge=-90,le=90,)
    origen_longitud: float = Field(...,ge=-180,le=180)
    destino_latitud: float = Field(...,ge=-90,le=90)
    destino_longitud: float = Field(...,ge=-180,le=180)
    tipo_vehiculo: VehiculosSoportados = Field(...,description="solo n posibles datos en mayusculas definidas en la enumeracion")

class ResultadoEstimacionRuta(BaseModel):
    origen:Coordenada = Field(...,description="coordenadas lat y lon del origen")
    destino:Coordenada = Field(...,description="coordenadas lat y lon del destino")
    distancia_estimada_km: float = Field(...,description="distancia entre conductor y cliente")
    eta_minutos:int = Field(...,description="tiempo entre conductor cliente")
    calculado_en:datetime = Field(...,description="tiempo en que fue enviado/calculado")
    fuente:FuenteInfo = Field(...,description="fuente de la informacion")


#se usara fieldvalidator para validar entradas por pydantic y que salte antes de entrar a codigo una exepcion de error
#especifica
#ojo con los string se debe verificar que no es un espacio en blanco " ", asi que se debe validar con la funcion
#anterior para rechazar ese tipo de strings y levantar excepcion asociada.
"""
422: Falló la estructura o los tipos de datos (Sintaxis / Pydantic).

400: La estructura era correcta, pero el contenido rompió una regla de negocio (Dominio / Tus excepciones).
"""

