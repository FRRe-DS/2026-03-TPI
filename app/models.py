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
from datetime import datetime #tipo de datos en formato de fecha y hora
from .database import Base #importante para crear desde 0 la tabla

class Prueba(Base): #todo lo que herede Base, sera una tabla en la base de datos.
    __tablename__ = "Prueba"
    #esta clase y tabla sera borrada luego de inicializar tipos mas especificos de entidades, ya que esta clase es solo para inicializar la bd
    id = Column(UUID(as_uuid=True), primary_key=True, index=True,default=uuid.uuid4, unique=True, nullable=False)
    #restricciones de integridad de la tabla, para que no se repitan los valores y que no sean nulos.
    