#aqui se ralizaran las consultas de fastapi en primer instancia de momento
from fastapi import FastAPI

# Instanciamos la aplicación principal de FastAPI
app = FastAPI(
    title="M4 - Ubicación y Disponibilidad",
    description="API encargada del rastreo de entidades",
    version="1.0.0"
)

# Endpoint raíz para verificar que la API está viva
@app.get("/") #si viene "/" en el navegador, le aplicara app.get y el codigo debajo
def read_root():
    return {
        "estado": "activo",
        "mensaje": "M4 corriendo correctamente en Docker"
    }