'''
================================================
En este archivo de codigo estaran los esquemas de contratos definidos por nosotros,
mas concretamente en formato de pydantic el cual mapea clases declaradas en python
para luego realizar contratos en rest o openAPI tengo entendido.
================================================

'''
from pydantic import BaseModel, Field #importantes para decirle a fastapi que debe validar y restrigir a quienes las usan
from typing import List,Optional # para determinar si es opcional el contenido de un campo, es decir puede ser null o none
from uuid import UUID
from datetime import datetime
from enum import Enum

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

class ListaDeConductoresM5(BaseModel):
    conductor_id: UUID = Field (...,"id conductor unico")
    distancia_km: float=Field(...,"distancia desde el origen hasta el conductor")
    eta_minutos:int = Field(...,"distancia estimada en minutos de arribo al cliente u origen")
    class Config:
        from_attributes = True  # Para compatibilidad con modelos ORM si los mapeas directamente

class EntradaM5Normal(BaseModel):
    solicitud_id: UUID =Field (..., description="Id de solicitud")
    destino_text: str = Field(...,"destino del viaje")
    origen_text: str = Field(...,"origen del viaje")
    tipo_v: str = Field(...,"tipo de vehiculo")#de momento str, luego hacemos enumeracion
    radio_max_km: int =Field(...,"kilometros de radio en base al origen, para busqueda de conductores")

class SalidaHaciaM5Normal (BaseModel):
    solicitud_id:UUID = Field(...,"id de solicitud")
    conductores:List[ListaDeConductoresM5]
    class Config:
        from_attributes = True

class ListaDeConductoresM3(BaseModel):
    conductor_id: UUID = Field (...,"id conductor unico")
    lat_conductor: float = Field(...,description=" latitud geografica conductor")
    lon_conductor:float = Field(...,description=" longitud geografica conductor")
    tipo_v: str= Field(...,description="tipo de vehiculo, posible enumeracion")
    class Config:
        from_attributes = True  # Para compatibilidad con modelos ORM si los mapeas directamente

class EntradaM3Conductores(BaseModel):
    conductores:List[ListaDeConductoresM3]
    class Config:
        from_attributes = True  # Para compatibilidad con modelos ORM si los mapeas directamente

class SalidaHaciaM7(BaseModel): #en duda porque no se sabe si m7 debe enviar un mensaje antes de realizar la salida
    solicitud_id:UUID = Field(...,description="id univoco")
    ett:int =Field(...,description="tiempo estimado de viaje en minutos")
    dod:float = Field(...,description="distancia origen destino en km")

class EntradaM9(BaseModel):
    origen_text:str = Field (...,description="origen en lenguaje natural")
    destino_text:str = Field (...,description="destino en lenguaje natural")

class SalidaHaciaM9(BaseModel):
    posible: bool =Field(...,description="verificacion de integridad sobre el viaje, si es verosimil")
    ett: int=Field(...,description="Tiempo estimado de viaje origen destino")
    dod: float = Field(...,description="distancia origen-destino en km")

#enumeraciones y tipos compuestos que intervienen en cache
class EstadoTmp(str,Enum):
    RESERVADO="RESERVADO"
    LIBERADO="LIBERADO"

class Coordenada(BaseModel):
    latitud: float = Field(..., ge=-90.0, le=90.0, description="Latitud en grados decimales")
    longitud: float = Field(..., ge=-180.0, le=180.0, description="Longitud en grados decimales")



