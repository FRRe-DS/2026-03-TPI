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
from app.enrutador.eventos import prueba #importamos los eventos sobre el el codigo fuente, para que "reconosca" lo segregado en el otro .py

Base.metadata.create_all(bind=engine) #si no habia una tabla, la crea, si ya existia, no hace nada. 
#Esto es para inicializar la base de datos y crear las tablas que se definan en models.py que hereden de Base.

# Instanciamos la aplicación principal de FastAPI
app = FastAPI(
    title="M4 - Ubicación y Disponibilidad",
    description="API encargada del rastreo de entidades",
    version="1.0.0"
)

'''
la idea es crear tantas delegaciones de prefijos especializados en funcionalidades, de esa manera centralizamos
funcionalidades y creamos tantos .py por funcionalidad especifica o responsabilidad especifica para modular 
el codigo, si algo saliera mal no haria falta buscar tanto codigo o como premisa se sabria que modulo fallo en 
cumplir su responsabilidad asociada.

'''

app.include_router(prueba, prefix="/PruebaM4") #aseguramos que el prefijo tanbien llegue aqui

# Endpoint raíz para verificar que la API está viva, luego de implementar separacion de responsabilidades en el codigo, es prescindible
@app.get("/") #si viene "/" en el navegador, le aplicara app.get y el codigo debajo
def read_Home():
    return {
        "estado": "activo",
        "mensaje": "M4 corriendo correctamente en Docker"
    }