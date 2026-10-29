from fastapi import Request
from app.main import logger


class CodHTTPErrores(Exception):
    #clase padre para codigos genericos que varian segun quien lo usa debido a convencion de formato de errores
    pass


class NoAutenticado (CodHTTPErrores):
    # 401
    pass

class SinPermiso (CodHTTPErrores):
    # 403
    pass

class NoProcesable (CodHTTPErrores):
    # 422
    pass

class LimiteExcedido (CodHTTPErrores):
    # 429
    pass

class ErrorInterno (CodHTTPErrores):
    # 500
    pass

class TiempoAgotado (CodHTTPErrores):
    # 504
    pass

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

class DependenciaNoDisponible(ProblemaDominio): #falta retry-after
    def __init__(self, detail:str="La dependencia externa tardo demasiado en responder o no esta disponible"):
        super().__init__(
            type = "/errores/dependencianodisponible/",
            title = "Dependencia No Disponible",
            status_code = 503,
            detail = detail,
            code = "GEOCODIFICACION_FRACASO")


