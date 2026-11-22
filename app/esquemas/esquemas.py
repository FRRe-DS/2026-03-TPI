
class FuenteInfo(str,Enum):
    PROVEEDOR_MAPA="proveedor_mapa"
    ESTIMACION_LOCAL="estimacion_local"

class VehiculosSoportados(str,Enum):
    AUTO="AUTO"
    MOTO="MOTO"

class ConsultaEstimacionRuta(BaseModel):
    origen_latitud: float = Field(..., ge=-90.0, le=90.0)
    origen_longitud: float = Field(..., ge=-180.0, le=180.0)
    destino_latitud: float = Field(..., ge=-90.0, le=90.0)
    destino_longitud: float = Field(..., ge=-180.0, le=180.0)
    tipo_vehiculo: Optional[VehiculosSoportados] = Field(
        default=VehiculosSoportados.AUTO
    )

class ResultadoEstimacionRuta(BaseModel):
    distancia_estimada_km: float = Field(
        ..., ge=0, description="Distancia estimada de ruta en km"
    )
    eta_minutos: int = Field(..., ge=0, description="Tiempo estimado en minutos")
    calculado_en: datetime = Field(
        ..., description="Timestamp UTC del momento del cálculo"
    )
    fuente: FuenteInfo = Field(
        ..., description="proveedor_mapa o estimacion_local"
    )


