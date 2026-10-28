from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.servicios.exceptionsSemanticos import *

def registrar_manejadores_excepciones(app: FastAPI):
    
    @app.exception_handler(RequestValidationError) #levantar excepcion especifica en validaciones pydantic, 400 segun documentacion
    async def pydantic_validation_handler(request: Request, exc: RequestValidationError):
        detalles_error = []
        for error in exc.errors():
            ubicacion = " -> ".join(str(loc) for loc in error["loc"])
            detalles_error.append({
                "campo": ubicacion,
                "error": error["msg"]
        })
        return JSONResponse(
            status_code=400,
            headers={"Content-Type": "application/problem+json"},
            content={
                "type": "https://api.sistematransporte.local/errors/validacion-datos",
                "title": "Solicitud Invalida",
                "status": 400,
                "detail": "Los datos de entrada no cumplen con el formato requerido. ",#deberia ir str(exec)
                "invalid_params":detalles_error,#aqui rompemos el patron nomenclatura establecido, para esta respuesta a errores de consistencia de datos
                "instance": request.url.path
            }
        )

    @app.exception_handler(NoAutenticado)#401
    async def Error401(request: Request, exc: NoAutenticado):
        pass

    @app.exception_handler(SinPermiso)#403
    async def Error403(request: Request, exc: SinPermiso):
        pass

    @app.exception_handler(NoProcesable)#422
    async def Error422(request: Request, exc: NoProcesable):
        pass

    @app.exception_handler(LimiteExcedido)#429
    async def Error429(request: Request, exc: LimiteExcedido):
        pass

    @app.exception_handler(ErrorInterno) #500
    async def Error500(request: Request, exc: ErrorInterno):
        pass

    @app.exception_handler(DependenciaNoDisponible) #503
    async def campo_vacio_handler(request: Request, exc: DependenciaNoDisponible):
        return JSONResponse(
            status_code=503,
            headers={"Content-Type": "application/problem+json"},
            content={
                "type": "https://api.sistematransporte.local/errors/DependenciaNoDisponible",
                "title": "Dependencia no Disponible",
                "status": 503,
                "detail": str(exc),
                "instance": request.url.path
            }
        )
    

    @app.exception_handler(TiempoAgotado) #504
    async def Error504(request: Request, exc: TiempoAgotado):
        pass

    
