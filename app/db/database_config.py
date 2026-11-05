"""
===================================================
Este archivo contiene la configuración de la base de datos y la creación del motor de conexión a Postgres
así como la definición de la clase Base para declarar las tablas (modelos) y la función get_db() 
para inyectar dependencias en los endpoints de FastAPI.
Si fuera necesario, aqui tambien se redefinirian las configuraciones de pool de coneccion como ser la cantidad maxima 
de conecciones, el tiempo de espera, etc. Sus valores predeterminados nos serviran por el momento
===================================================
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

#Capturamos la URL que inyectó Docker desde el archivo .env
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

#Creamos el motor (engine) que establece el canal de comunicación con Postgres
engine = create_engine(SQLALCHEMY_DATABASE_URL)

#Fábrica de sesiones temporales para realizar transacciones
#es algo asi como un secretario de pools de conectividad sobre la bd, pero que no realiza conecciones hasta que la 
#obligamos a realizar una, se podira decir que con esto, se "prepara" pero no la conecta.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

#Clase base para declarar las futuras tablas (modelos)
Base = declarative_base()

#Función de inyección de dependencias para los endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()