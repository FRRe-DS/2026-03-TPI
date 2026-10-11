""""
============================================================
Este archivo es el punto de entrada de la aplicación FastAPI.
Aquí se inicializa la base de datos y se crean las tablas definidas en models.py.
Tambien se configura la aplicación FastAPI y se definen los endpoints principales.
Asi como la inyeccion de dependencias para la base de datos.
Y codigo autoejecutable segun decoradores, los cuales responden a los endpoints de la API.
============================================================
"""
from .database import engine, Base #se importan para crear las tablas en la base de datos, y para poder realizar consultas a la bd
from . import models #se importa models para que se ejecute el codigo de models.py y se creen las tablas en la base de datos
from fastapi import FastAPI

Base.metadata.create_all(bind=engine) #si no habia una tabla, la crea, si ya existia, no hace nada. 
#Esto es para inicializar la base de datos y crear las tablas que se definan en models.py que hereden de Base.

# Instanciamos la aplicación principal de FastAPI
app = FastAPI(
    title="M4 - Ubicación y Disponibilidad",
    description="API encargada del rastreo de entidades",
    version="1.0.0"
)

# Endpoint raíz para verificar que la API está viva
@app.get("/") #si viene "/" en el navegador, le aplicara app.get y el codigo debajo
def read_Home():
    return {
        "estado": "activo",
        "mensaje": "M4 corriendo correctamente en Docker"
    }