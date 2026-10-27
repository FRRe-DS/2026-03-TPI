'''
================================================
En este archivo de codigo estaran los esquemas de contratos definidos por nosotros,
mas concretamente en formato de pydantic el cual mapea clases declaradas en python
para luego realizar contratos en rest o openAPI tengo entendido.
================================================

'''
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator #importantes para decirle a fastapi que debe validar y restrigir a quienes las usan
from typing import List, Literal, Optional # para determinar si es opcional el contenido de un campo, es decir puede ser null o none
from enum import Enum
from uuid import UUID
from datetime import datetime, timezone


class TipoVehiculo(str, Enum):
    AUTO = "AUTO"
    MOTO = "MOTO"


class EstadoTemporal(str, Enum):
    RESERVADO = "RESERVADO"
    LIBERADO = "LIBERADO"


def _validate_utc_timestamp(value: datetime | None) -> datetime | None:
    if value is not None and value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("El timestamp debe tener zona horaria UTC.")
    return value


class ActualizarUbicacion(BaseModel):
    conductor_id: UUID
    latitud: float = Field(ge=-90, le=90, description="Latitud en grados WGS 84.")
    longitud: float = Field(ge=-180, le=180, description="Longitud en grados WGS 84.")
    timestamp_ubicacion: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("timestamp_ubicacion")
    @classmethod
    def timestamp_must_be_utc(cls, value: datetime) -> datetime:
        if value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("timestamp_ubicacion debe tener zona horaria UTC.")
        return value


class UbicacionRegistrada(BaseModel):
    conductor_id: UUID
    timestamp_ubicacion: datetime
    recibida_en: datetime
    vigente: Literal[True]
    expira_en: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("timestamp_ubicacion", "recibida_en", "expira_en")
    @classmethod
    def timestamps_must_be_utc(cls, value: datetime | None) -> datetime | None:
        return _validate_utc_timestamp(value)


class EstadoOperativo(BaseModel):
    event_id: UUID | None = None
    connected: bool
    available: bool
    timestamp_evento: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("timestamp_evento")
    @classmethod
    def timestamp_must_be_utc(cls, value: datetime | None) -> datetime | None:
        return _validate_utc_timestamp(value)


class EstadoOperativoRegistrado(BaseModel):
    conductor_id: UUID
    event_id: UUID | None = None
    connected: bool
    available: bool
    actualizado_en: datetime | None = None
    recibido_en: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("actualizado_en", "recibido_en")
    @classmethod
    def timestamps_must_be_utc(cls, value: datetime | None) -> datetime | None:
        return _validate_utc_timestamp(value)

    @model_validator(mode="after")
    def disconnected_driver_cannot_be_available(self) -> "EstadoOperativoRegistrado":
        if not self.connected and self.available:
            raise ValueError("available debe ser false cuando connected es false.")
        return self


class Candidato(BaseModel):
    conductor_id: UUID
    distancia_origen_km: float = Field(ge=0)
    eta_retiro_minutos: int | None = Field(default=None, ge=0)
    tipo_vehiculo: TipoVehiculo

    model_config = ConfigDict(extra="forbid")


class ResultadoBusquedaConductores(BaseModel):
    conductores: list[Candidato]
    radio_aplicado_km: float = Field(gt=0)
    generado_en: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("generado_en")
    @classmethod
    def timestamp_must_be_utc(cls, value: datetime) -> datetime:
        return _validate_utc_timestamp(value)


class CambioReservaTemporal(BaseModel):
    estado_temporal: EstadoTemporal
    solicitud_id: UUID

    model_config = ConfigDict(extra="forbid")


class ResultadoReservaTemporal(BaseModel):
    conductor_id: UUID
    solicitud_id: UUID
    estado_temporal: EstadoTemporal
    actualizado_en: datetime
    expira_en: datetime | None = None
    idempotente: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("actualizado_en", "expira_en")
    @classmethod
    def timestamps_must_be_utc(cls, value: datetime | None) -> datetime | None:
        return _validate_utc_timestamp(value)


class PuntoGeografico(BaseModel):
    latitud: float = Field(ge=-90, le=90)
    longitud: float = Field(ge=-180, le=180)

    model_config = ConfigDict(extra="forbid")


class FuenteEstimacion(str, Enum):
    PROVEEDOR_MAPA = "proveedor_mapa"
    ESTIMACION_LOCAL = "estimacion_local"


class EstimacionRuta(BaseModel):
    origen: PuntoGeografico
    destino: PuntoGeografico
    distancia_estimada_km: float = Field(ge=0)
    eta_minutos: int = Field(ge=0)
    calculado_en: datetime
    fuente: FuenteEstimacion

    model_config = ConfigDict(extra="forbid")

    @field_validator("calculado_en")
    @classmethod
    def timestamp_must_be_utc(cls, value: datetime) -> datetime:
        return _validate_utc_timestamp(value)


class ConsultaGeocodificacion(BaseModel):
    direccion: str = Field(min_length=1, max_length=300)
    localidad: str | None = Field(default=None, max_length=120)
    pais: str = Field(min_length=2, max_length=2)

    model_config = ConfigDict(extra="forbid")


class CoincidenciaGeocodificacion(BaseModel):
    latitud: float = Field(ge=-90, le=90)
    longitud: float = Field(ge=-180, le=180)
    etiqueta: str
    confianza: float | None = Field(default=None, ge=0, le=1)

    model_config = ConfigDict(extra="forbid")


class ResultadoGeocodificacion(BaseModel):
    coincidencias: list[CoincidenciaGeocodificacion]

    model_config = ConfigDict(extra="forbid")


class LivenessResponse(BaseModel):
    status: Literal["UP"]


class ReadinessResponse(BaseModel):
    status: Literal["READY"]


class ParametroInvalido(BaseModel):
    name: str
    reason: str

    model_config = ConfigDict(extra="allow")


class Problema(BaseModel):
    type: str
    title: str
    status: int = Field(ge=400, le=599)
    detail: str
    instance: str
    code: str | None = None
    trace_id: str | None = None
    invalid_params: list[ParametroInvalido] | None = None

    model_config = ConfigDict(extra="allow")


class ProblemaGenerico(Problema):
    type: Literal["about:blank"]


class ProblemaDominio(Problema):
    @field_validator("type")
    @classmethod
    def type_must_identify_a_domain_problem(cls, value: str) -> str:
        if value == "about:blank":
            raise ValueError("Los problemas de dominio requieren un type específico.")
        return value


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
    conductor_id: UUID = Field(..., description="id conductor unico")
    distancia_km: float = Field(..., description="distancia desde el origen hasta el conductor")
    eta_minutos: int = Field(
        ..., description="distancia estimada en minutos de arribo al cliente u origen"
    )
    class Config:
        from_attributes = True  # Para compatibilidad con modelos ORM si los mapeas directamente

class EntradaM5Normal(BaseModel):
    solicitud_id: UUID = Field(..., description="Id de solicitud")
    destino_text: str = Field(..., description="destino del viaje")
    origen_text: str = Field(..., description="origen del viaje")
    tipo_v: str = Field(..., description="tipo de vehiculo")
    radio_max_km: int = Field(
        ..., description="kilometros de radio en base al origen, para busqueda de conductores"
    )

class SalidaHaciaM5Normal (BaseModel):
    solicitud_id: UUID = Field(..., description="id de solicitud")
    conductores:List[ListaDeConductoresM5]
    class Config:
        from_attributes = True

class ListaDeConductoresM3(BaseModel):
    conductor_id: UUID = Field(..., description="id conductor unico")
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
