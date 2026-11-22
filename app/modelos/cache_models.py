from typing import Dict, Any, Optional
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
    conductor_id: UUID = Field(...,primary_key=True)
    event_id: Optional[str] = Field(default=None, index=True,description="a confirmar con m3")
    connected:bool = Field(...,description="si es true el conductor desea esta conectado a la app")
    available:bool = Field(...,description="si es true el conductor desea recibir solicitudes")
    timestamp_evento: Optional[datetime] = Field(default=None, description="Opcional hasta confirmación de M3. Si se informa, instante UTC de la intención que M4 usa para detectar eventos fuera de orden.")
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
    status_code: int = Field(...,ge=200, le=599,description="codigo error http") 
    body: Dict[str, Any] = Field(...,description="body json que debe resguardar/retornar")
    body_hash: str = Field(...,description="codigo hash unico para cada body")
    
    """" 
        resultado.model_dump(mode="json") hay que guardar asi en la cache 
        
        ejemplo:
        registro = RegistroIdempotencia(
        status_code=status_code_final,
        body=resultado.model_dump(mode="json"),
        body_hash=body_hash)
    
    """


