'''
================================================
En este archivo de codigo estaran los esquemas de contratos definidos por nosotros,
mas concretamente en formato de pydantic el cual mapea clases declaradas en python
para luego realizar contratos en rest o openAPI tengo entendido.
================================================

'''
from pydantic import BaseModel, Field #importantes para decirle a fastapi que debe validar y restrigir a quienes las usan
from typing import Optional # para determinar si es opcional el contenido de un campo, es decir puede ser null o none
from uuid import UUID
from datetime import datetime

'''
importante, si un dato no viene y DEBE fallar, es decir es obligatorio el dato, debe ir ... en field si o si
'''
class InfoExterna(BaseModel):
    modulo_origen_id: UUID = Field(..., description="UUID del modulo que inicio la comunicacion") 
    datos_enriquecidos: str = Field(..., description="datos string de prueba") 

class EventoPruebaEntrada(BaseModel):
    evento_id: UUID = Field(..., description="Identificador único del evento recibido") 
    lat: float = Field(..., description="Coordenada de latitud geográfica") 
    lon: float = Field(..., description="Coordenada de longitud geográfica") 
    ubicacion_texto: str = Field(..., description="ubicacion en lenguaje natural") 
    timestamp: Optional[datetime] = Field(default_factory=datetime.now, description="Marca temporal del evento") 

class EventoPruebaSalida(BaseModel):
    evento_id: UUID = Field(..., description="ID del evento que fue procesado") 
    estado: str = Field(..., description="Estado del procesamiento, ej: OK") 
    ubicacion_procesada: str = Field(..., description="ubicacion en lenguaje natural") 
    detalles_externos: InfoExterna = Field(..., description="Forma de definir estructuras anidadas") 
    mensaje: str = Field(..., description="Mensaje explicativo del resultado") 