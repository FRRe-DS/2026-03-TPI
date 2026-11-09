from typing import Dict, Any
from pydantic import BaseModel, Field, field_validator
from redis_om import HashModel
from uuid import UUID
from app.db.cache_config import cache
from datetime import datetime
from app.esquemas.esquemas import EstadoTmp, Coordenada
from enum import Enum

# --- PARCHES TEMPORALES (Simulando lo que falta importar/crear) ---
class EstadoConductor(str, Enum):
    DESCONECTADO = "DESCONECTADO"
    CONECTADO = "CONECTADO"
    OCUPADO = "OCUPADO"

class DetalleVehiculo(BaseModel):
    modelo: str = "Simulado"
# ------------------------------------------------------------------

#mal definidos todos, si son tablas deberan usar atributo coleccion y ahi recien la definicion normal

class ConductorCache(HashModel):
    # Campos primitivos con tipos de datos comunes estrictos
    conductor_id: int = Field(..., index=True)  # Indexado para búsquedas rápidas
    latitud: float
    longitud: float
    estado: EstadoConductor = EstadoConductor.DESCONECTADO  # Enum con valor por defecto
    viajes_completados: int = 0
    activo: bool = True
    
    # Campo Compuesto / Anidado:
    vehiculo: DetalleVehiculo

    # 4. VALIDACIONES PERSONALIZADAS
    @field_validator("latitud")
    def validar_latitud(cls, v):
        if not (-90.0 <= v <= 90.0):
            raise ValueError("La latitud debe estar entre -90 y 90 grados.")
        return v

    @field_validator("longitud")
    def validar_longitud(cls, v):
        if not (-180.0 <= v <= 180.0):
            raise ValueError("La longitud debe estar entre -180 y 180 grados.")
        return v

    class Meta:
        database = cache  # <-- Corregido: variable unificada con el import

class UbicacionesCond(HashModel):#usa ttl
    conductor_id: UUID = Field(...,primary_key=True,description="id del conductor que reporta la ubicacion")
    geo:Coordenada = Field(...)
    timestamp_ubicacion: datetime =Field(...)
    class Meta:
        database = cache

class CacheEstOp(HashModel):
    conductor_id: UUID = Field(...,index=True)
    event_id: None = Field(description="a confirmar con m3")
    connected:bool = Field(...,description="si es true el conductor desea esta conectado a la app")
    avalible:bool = Field(...,description="si es true el conductor desea recibir solicitudes")
    actualizado_en: datetime = Field()
    recibido_en: datetime = Field(...,description="util para determinar cuando dejamos de recibir act")
    class Meta:
            database = cache

class CacheResTemp(HashModel):#usa ttl
    conductor_id: UUID = Field(...,index=True)
    solicitud_id: UUID = Field(...,index=True)
    estado_temporal: EstadoTmp = Field(...,description="")
    origen: Coordenada = Field(...)
    destino: Coordenada = Field(...)
    actualizado_en: datetime = Field()
    class Meta:
            database = cache

class RegistroIdempotencia(BaseModel):
    status: int = Field(...,ge=200, le=599,description="codigo error http") 
    body: Dict[str, Any] = Field(...,description="body json que debe resguardar/retornar")
    body_hash: str = Field(...,description="codigo hash unico para cada body")

