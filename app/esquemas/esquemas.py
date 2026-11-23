'''
================================================
En este archivo de codigo estaran los esquemas de contratos definidos por nosotros,
mas concretamente en formato de pydantic el cual mapea clases declaradas en python
para luego realizar contratos en rest o openAPI tengo entendido.
================================================

'''
from pydantic import BaseModel, Field, field_validator, ConfigDict #importantes para decirle a fastapi que debe validar y restrigir a quienes las usan
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
    model_config = ConfigDict(extra="forbid") #debido a que el contrato las propiedades adicionales es false
    latitud: float = Field(..., ge=-90.0, le=90.0, description="Latitud en grados decimales")
    longitud: float = Field(..., ge=-180.0, le=180.0, description="Longitud en grados decimales")

class FuenteInfo(str,Enum):
    PROVEEDOR_MAPA="PROVEEDOR_MAPA"
    ESTIMACION_LOCAL="ESTIMACION_LOCAL"

class VehiculosSoportados(str,Enum):
    AUTO="AUTO"
    MOTO="MOTO"

class ActualizarUbicacion(BaseModel): 
    model_config = ConfigDict(extra="forbid") #debido a que el contrato las propiedades adicionales es false
    latitud: float = Field(..., ge=-90.0, le=90.0, description="Latitud en grados decimales")
    longitud: float = Field(..., ge=-180.0, le=180.0, description="Longitud en grados decimales")
    timestamp_ubicacion: datetime = Field(..., description="Timestamp de la ubicación en formato ISO 8601")

class UbicacionRegistrada(BaseModel):
    model_config = ConfigDict(extra="forbid") #debido a que el contrato las propiedades adicionales es false
    conductor_id: UUID = Field(..., description="Identificador único del conductor") 
    timestamp_ubicacion: datetime = Field(..., description="Timestamp de la ubicación en formato ISO 8601")
    recibida_en: datetime = Field(..., description="Timestamp de recepción en formato ISO 8601")
    vigente: bool = Field(..., description="Indica si la ubicación es la más reciente y válida")
    expira_en: datetime = Field(..., description="Timestamp de expiración en formato ISO 8601")
    
class ConsultaGeocodificacion(BaseModel):
    model_config = ConfigDict(extra="forbid") #debido a que el contrato las propiedades adicionales es false
    direccion: str = Field(..., min_length=1, description="Calle y altura")
    provincia: str = Field(default=None, description="Provincia o región")
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
    model_config = ConfigDict(extra="forbid") #debido a que el contrato las propiedades adicionales es false
    latitud: float =Field(...,ge=-90,le=90,description="latitud resultante con limitancias terricolas")
    longitud: float =Field(...,ge=-180,le=180,description="longitud resultante con limitancias terricolas")
    etiqueta: str =Field(...,description="direccion lenguaje natural el cual se asocia la coordenada")
    confianza: float =Field(ge=0,le=1)
    #son cosas que nos devuelve el servicio externo o el diccionario de ubicaciones, no es posible dejarlos en blanco

class ResultadoGeocodificacion(BaseModel):
    model_config = ConfigDict(extra="forbid") #debido a que el contrato las propiedades adicionales es false
    coincidencias:List[CoincidenciasGeolocalizacion] = Field(description="puede devolver vacio")

class QueryEstimacionRuta(BaseModel):
    model_config = ConfigDict(extra="forbid") #debido a que el contrato las propiedades adicionales es false
    origen_latitud: float = Field(..., ge=-90.0, le=90.0)
    origen_longitud: float = Field(..., ge=-180.0, le=180.0)
    destino_latitud: float = Field(..., ge=-90.0, le=90.0)
    destino_longitud: float = Field(..., ge=-180.0, le=180.0)
    tipo_vehiculo: VehiculosSoportados = Field(...)
    
class ResultadoEstimacionRuta(BaseModel):
    model_config = ConfigDict(extra="forbid") #debido a que el contrato las propiedades adicionales es false
    distancia_estimada_km: float = Field(..., gt=0, description="Distancia estimada de ruta en km")
    eta_minutos: int = Field(..., gt=0, description="Tiempo estimado en minutos")
    calculado_en: datetime = Field(..., description="Timestamp UTC del momento del cálculo")
    fuente: FuenteInfo = Field(..., description="proveedor_mapa o estimacion_local")

class SolicitudReserva(BaseModel):
    model_config = ConfigDict(extra="forbid") #debido a que el contrato las propiedades adicionales es false
    reserva_id: UUID = Field(..., description="ID temporal de la reserva simulada")
    conductor_id: UUID = Field(..., description="ID del conductor reservado")
    estado: EstadoTmp = Field(default=EstadoTmp.RESERVADO, description="Estado de la reserva")

class QueryCercanos(BaseModel):
    model_config = ConfigDict(extra="forbid") #debido a que el contrato las propiedades adicionales es false
    origen_latitud: float = Field(...,ge=-90,le=90)
    origen_longitud: float = Field(...,ge=-180,le=180)
    tipo_vehiculo: VehiculosSoportados = Field(description="solo n posibles datos en mayusculas definidas en la enumeracion")
    limite: Optional[int] = Field(default=20, ge=1, le=100, description="cantidad maxima de candidatos devueltos")

class Candidatos(BaseModel):
    model_config = ConfigDict(extra="forbid") #debido a que el contrato las propiedades adicionales es false
    conductor_id: UUID = Field(..., description="Identificador único del conductor")
    distancia_origen_km: float = Field(..., description="Distancia entre el conductor y el origen en kilómetros")
    eta_retiro_minutos: Optional[int] = Field(ge=0,description="Tiempo estimado de llegada del conductor al origen en minutos")
    tipo_vehiculo: VehiculosSoportados = Field(..., description="Tipo de vehículo del conductor")

class ResultadoBusquedaConductores(BaseModel):
    model_config = ConfigDict(extra="forbid") #debido a que el contrato las propiedades adicionales es false
    conductores: List[Candidatos] = Field(description="lista de conductores encontrados, puede estar vacia si no hay coincidencias")
    radio_aplicado_km: float = Field(...,gt=0, description="radio de busqueda aplicado en kilometros")
    generado_en: datetime = Field(...,description="timestamp de generacion del resultado en formato ISO 8601")
    
class EstadoOperativo(BaseModel):
    model_config = ConfigDict(extra="forbid") #debido a que el contrato las propiedades adicionales es false
    event_id: Optional[str] = Field(default=None, description="ID del evento asociado (opcional)")
    connected: bool = Field(..., description="Indica si el conductor desea estar conectado a la app")
    available: bool = Field(..., description="Indica si el conductor desea recibir solicitudes")
    timestamp_evento: Optional[datetime] = Field(default=None, description="Timestamp del evento en formato ISO 8601")

class EstadoOperativoRegistrado(BaseModel):
    model_config = ConfigDict(extra="forbid") #debido a que el contrato las propiedades adicionales es false
    conductor_id: UUID = Field(..., description="Identificador único del conductor")
    event_id: Optional[str] = Field(default=None, description="ID del evento asociado (opcional)")
    connected: bool = Field(..., description="Indica si el conductor desea estar conectado a la app")
    available: bool = Field(..., description="Indica si el conductor desea recibir solicitudes")
    actualizado_en: Optional[datetime] = Field(default=None, description="Timestamp del evento aplicado, si M3 lo envió; en caso contrario, puede omitirse.")
    recibido_en: datetime = Field(..., description="Timestamp en que M4 recibió el evento de intención de M3 en formato ISO 8601")

