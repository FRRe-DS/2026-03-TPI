from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import engine, get_db, SessionLocal, Base
from models import ProductoModel
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator  # <--- 1. Importar el instrumentador
import logging

# =========================================================
# CAMBIO 1: Importamos las herramientas de OpenTelemetry
# =========================================================
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


# ---------------------------------------------------------
# NUEVO: Definimos la estructura del objeto para recargar stock
# ---------------------------------------------------------
class RecargaStock(BaseModel):
    cantidad: int


# Configuramos cómo queremos que se vean los logs en la consola
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cafeteria-api")

# 1. SQLAlchemy crea automáticamente las tablas en PostgreSQL basándose en nuestras clases
Base.metadata.create_all(bind=engine)

# =========================================================
# CAMBIO 2: Le decimos a Python que envíe las trazas al contenedor "tempo" por el puerto 4317
# =========================================================
provider = TracerProvider()
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="tempo:4317", insecure=True))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

app = FastAPI()

# <--- 2. Inicializar y exponer las métricas para Prometheus automáticamente
Instrumentator().instrument(app).expose(app)

# =========================================================
# CAMBIO 3: Activamos la captura automática de trazas para FastAPI
# =========================================================
FastAPIInstrumentor.instrument_app(app)


# 2. Apenas arranca la app, nos aseguramos de que exista el producto 'Cafe' con stock inicial
@app.on_event("startup")
def startup_db():
    db = SessionLocal()
    try:
        cafe = db.query(ProductoModel).filter(ProductoModel.nombre == "Cafe").first()
        if not cafe:
            nuevo_cafe = ProductoModel(nombre="Cafe", stock=10)
            db.add(nuevo_cafe)
            db.commit()
            print("¡Producto inicial 'Café' creado con éxito en la base de datos!")
    finally:
        db.close()

@app.get("/")
def leer_raiz():
    return {"mensaje": "¡Bienvenido al sistema de stock de la cafetería con SQLAlchemy!"}

@app.get("/healthz/ready")
def health_check(db: Session = Depends(get_db)):
    try:
        # Probamos hacer una consulta rápida a la base de datos
        db.execute("SELECT 1")
        return {"status": "ready", "database": "connected"}
    except Exception:
        raise HTTPException(status_code=500, detail="Database not connected")

# 3. Ruta para pedir café usando el ORM
@app.post("/pedir-cafe")
def pedir_cafe(db: Session = Depends(get_db)):
    logger.info("Recibida una petición para pedir un café ☕")
    
    cafe = db.query(ProductoModel).filter(ProductoModel.nombre == "Cafe").first()
    
    if not cafe:
        logger.warning("Intento de pedido fallido: El producto 'Cafe' no existe en la base de datos.")
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    if cafe.stock <= 0:
        logger.warning("Intento de pedido fallido: Stock agotado.")
        return {"mensaje": "¡Lo sentimos! Nos quedamos sin stock de café."}
    
    cafe.stock -= 1
    db.commit()
    db.refresh(cafe)
    
    logger.info(f"Pedido exitoso. Stock restante de café: {cafe.stock}")
    return {
        "mensaje": "¡Pedido realizado con éxito!",
        "producto": cafe.nombre,
        "stock_restante": cafe.stock
    }

@app.post("/cargar-stock")
def cargar_stock(recarga: RecargaStock, db: Session = Depends(get_db)):
    logger.info(f"Recibida solicitud para recargar stock en {recarga.cantidad} unidades.")
    
    cafe = db.query(ProductoModel).filter(ProductoModel.nombre == "Cafe").first()
    
    if not cafe:
        cafe = ProductoModel(nombre="Cafe", stock=recarga.cantidad)
        db.add(cafe)
        logger.info("El producto no existía. Creado inicialmente con el stock indicado.")
    else:
        cafe.stock += recarga.cantidad
        logger.info(f"Stock actualizado. Nuevo total: {cafe.stock}")
    
    db.commit()
    db.refresh(cafe)
    
    return {
        "mensaje": "¡Stock recargado con éxito! ☕",
        "producto": cafe.nombre,
        "stock_actual": cafe.stock
    }