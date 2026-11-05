from fastapi import Request
from app.main import logger

class ProblemaGenerico (Exception):
    def __init__(self, type: str = "about:blank", title: str = "", status_code: int = None, detail: str = "", instance: str = "", code: str = None, trace_id: str = None, invalid_params = None):
        if not (400 <= status_code <= 599):
            raise ValueError(
                f"El código de estado HTTP '{status_code}' es inválido para un problema. "
                "Debe estar estrictamente entre 400 y 599."
            )
        
        self.type = type
        self.title = title
        self.status_code = status_code
        self.detail = detail
        self.instance = instance
        self.code = code
        self.trace_id = trace_id
        self.invalid_params= invalid_params
        super().__init__(detail)

class ProblemaDominio (Exception):
    def __init__(self, type: str = "", title: str = "", status_code: int = None, detail: str = "", instance: str = "", code: str = None, trace_id: str = None, invalid_params = None):
        if not (400 <= status_code <= 599):
            raise ValueError(
                f"El código de estado HTTP '{status_code}' es inválido para un problema. "
                "Debe estar estrictamente entre 400 y 599."
            )
        
        self.type = type
        self.title = title
        self.status_code = status_code
        self.detail = detail
        self.instance = instance
        self.code = code
        self.trace_id = trace_id
        self.invalid_params= invalid_params
        super().__init__(detail)

class NoAutenticado (ProblemaGenerico):
    # 401
    pass

class SinPermiso (ProblemaGenerico):
    # 403
    pass

class NoProcesable (ProblemaDominio):
    # 422
    pass

class LimiteExcedido (ProblemaGenerico): #tiene retry after
    # 429
    pass

class ErrorInterno (ProblemaGenerico):
    # 500
    pass

class TiempoAgotado (ProblemaDominio):
    # 504
    pass

class DependenciaNoDisponible(ProblemaDominio): #falta retry-after
    def __init__(self, detail:str="La dependencia externa tardo demasiado en responder o no esta disponible"):
        super().__init__(
            type = "/errores/dependencianodisponible/",
            title = "Dependencia No Disponible",
            status_code = 503,
            detail = detail,
            code = "GEOCODIFICACION_FRACASO")

class FaltaHeaderIdempotencia(ProblemaGenerico):
    def __init__(self,detail:str ="Peticion incompleta, header 'idempotencyKey' es obligatoria para procesar esta operación."):
        super().__init__(
        title="Solicitud Invalida",
        status_code=400,
        detail=detail,
        code="HEADER_IDEMPOTENCIA_FALTANTE"
        )

class HashBodyDiferente(ProblemaDominio):
    def __init__(self,detail:str="Conflicto reutilizacion de 'idempotency_key' con datos distintos"):
        super().__init__(
            type = "/errores/conflictohash/",
            title = "Conflicto",
            status_code = 409,
            detail = detail,
            code = "IDEMPOTENCIA_CONFLICTO"
        )