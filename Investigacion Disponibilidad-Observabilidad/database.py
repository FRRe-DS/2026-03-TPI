import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Leemos la dirección de la base de datos desde el entorno de Docker
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password123@postgres:5432/cafeteria_db")

# 1. Creamos el motor de conexión de SQLAlchemy
engine = create_engine(DATABASE_URL)

# 2. Creamos una "fábrica de sesiones" (las sesiones son los tubos temporales para hablar con la base)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Base declarativa que usarán nuestros modelos de clases
Base = declarative_base()

def get_db():
    """
    Función de dependencia: abre una sesión con la base de datos 
    y se asegura de cerrarla cuando la petición termina.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()