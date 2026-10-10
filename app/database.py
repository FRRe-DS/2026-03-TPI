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