from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.servicios.exceptionsSemanticos import *
from app.main import logger

def registrar_manejadores_excepciones(app: FastAPI):
    
    @app.exception_handler(RequestValidationError) #familia de errores del dominio pero levantados por pydantic
    async def pydantic_validation_handler(request: Request, exc: RequestValidationError):
        trace_id = getattr(request.state, "xrequest_id", None)
        detalles_error = []
        for error in exc.errors():
            ubicacion = " -> ".join(str(loc) for loc in error["loc"])
            detalles_error.append({
                "name": ubicacion,
                "reason": error["msg"]
        })
        return JSONResponse(
            status_code=400,
            headers={"Content-Type": "application/problem+json"},
            content={
                "type": "about:blank",
                "title": "Solicitud Invalida",
                "status_code": 400,
                "detail": "Los datos de entrada no cumplen con el formato requerido. ",
                "instance": str(request.url.path),
                "trace_id":trace_id,
                "invalid_params":detalles_error
            }
        )

    @app.exeption_handler(ProblemaGenerico) #familia de errores genericos
    async def HandlerGenerico(request:Request,exc:ProblemaGenerico):
        trace_id = getattr(request.state, "xrequest_id", None)
        contenido={
            "type": exc.type,
            "title": exc.title,
            "status": exc.status_code,
            "detail": exc.detail,
            "instance": str(request.url.path),
            "trace_id":trace_id
        }
        if exc.code is not None:
            contenido["code"] = exc.code
        
        return JSONResponse(
                    status_code=exc.status_code,
                    headers={"Content-Type": "application/problem+json"},
                    content=contenido                    
        )

    @app.exception_handler(ProblemaDominio) #familia de errores del domino
    async def HandlerDominio(request:Request,exc:ProblemaDominio):
        trace_id = getattr(request.state, "xrequest_id", None)
        return JSONResponse(
                    status_code=exc.status_code,
                    headers={"Content-Type": "application/problem+json"},
                    content={# code aqui esta en duda si siempre aparece o es cirscunstancial
                        "type": exc.type,
                        "title": exc.title,
                        "status_code": exc.status_code,
                        "detail": exc.detail,
                        "instance": str(request.url.path),
                        "code":exc.code,
                        "trace_id":trace_id
                    }
        )

    @app.exception_handler(Exception)  # Captura cualquier error no controlado en la app
    async def global_exception_handler(request: Request, exc: Exception):
        trace_id = getattr(request.state, "xrequest_id", None)
        # Opcional: Aquí puedes registrar el error real en la terminal con un logger
        logger.error(f"Error 500 no controlado: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            headers={"Content-Type": "application/problem+json"},
            content={
                "type": "about:blank",
                "title": "Error Interno del Servidor",
                "status": 500,
                "detail": "Ocurrió un error inesperado al procesar la solicitud.",
                "instance": str(request.url.path),
                "trace_id": trace_id
            }
        )
    
