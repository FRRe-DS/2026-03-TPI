"""
=============================================
Este archivo contiene la definición de las tablas de la base de datos, que se definen como clases que heredan de Base. 
Cada clase representa una tabla y cada atributo de la clase representa una columna en esa tabla junto con sus restricciones 
de integridad y tipo de dato.
=============================================
"""
import uuid
from sqlalchemy import Column, Integer, Float, String, DateTime #tipos de datos mas comunes
from sqlalchemy.dialects.postgresql import UUID #restricciones de tipo mas complejos e incrementales
from datetime import datetime, timezone#tipo de datos en formato de fecha y hora
from .database import Base #importante para crear desde 0 la tabla

'''
    class Prueba(Base): #todo lo que herede Base, sera una tabla en la base de datos.
    __tablename__ = "Prueba"
    #esta clase y tabla sera borrada luego de inicializar tipos mas especificos de entidades, ya que esta clase es solo para inicializar la bd
    id = Column(UUID(as_uuid=True), primary_key=True, index=True,default=uuid.uuid4, unique=True, nullable=False)
    #restricciones de integridad de la tabla, para que no se repitan los valores y que no sean nulos.
'''
    
# Tablas

#Tabla n° 1: Registro de solicitudes de unicacion conductor
class RegistroSolicitud(Base):
    """
    Tabla de registro histórico o mitigación de solicitudes de viajes.
    """
    __tablename__ = "registro_solicitudes"

    solicitud_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    origen_lat = Column(Float, nullable=False) # Float para almacenar coordenadas geográficas. nullable=False para que no se permitan valores nulos.
    origen_long = Column(Float, nullable=False)
    destino_lat = Column(Float, nullable=False)
    destino_long = Column(Float, nullable=False)
    fecha_solicitud = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), #Si al guardar no le pasas fecha, Python tomará automáticamente la fecha y hora actual en tiempo universal coordinado (UTC)
        nullable=False
    )

#TAbla n° 2: Posición y estado de conductores en tiempo real
class ConductorTiempoReal(Base):
    """
    Tabla de posición y estado de conductores en tiempo real.
    """
    __tablename__ = "conductor_tiempo_real"

    conductor_id = Column(Integer, primary_key=True, index=True) # A diferencia de la tabla anterior, no tiene autoincrement=True porque el ID del conductor seguramente vendrá asignado desde otro módulo (por ejemplo, el módulo de usuarios/conductores)
    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)
    tipo_vehiculo = Column(String(50), nullable=False)
    ultima_actualizacion = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), #Asigna la fecha/hora actual cuando el conductor se registra por primera vez.
        onupdate=lambda: datetime.now(timezone.utc), #Muy importante: cada vez que modifiques la fila (por ejemplo, cuando el conductor cambie de latitud/longitud), este campo se actualizará automáticamente con la hora actual sin que tengas que cambiarlo a mano.
        nullable=False #No puede ser nulo
    )


