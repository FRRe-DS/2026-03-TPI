from sqlalchemy import Column, Integer, String
from database import Base

class ProductoModel(Base):
    """
    Esta clase representa la tabla 'productos' en la base de datos, 
    pero escrita puramente como un objeto de Python.
    """
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column(String(100), unique=True, index=True)
    stock = Column(Integer)