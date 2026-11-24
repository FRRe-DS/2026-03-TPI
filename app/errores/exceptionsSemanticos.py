from typing import Any

class ProblemaGenerico (Exception):
    def __init__(self, type: str = "about:blank", title: str = "", status: int = None, 
                detail: str = "", instance: str = "", code: str = None, trace_id: str = None,
                invalid_params = None,retry_after:int|None=None):
        if not (400 <= status <= 599) or None:
            raise ValueError(
                f"El código de estado HTTP '{status}' es inválido para un problema. "
                "Debe estar estrictamente entre 400 y 599."
            )
        
        self.type = type
        self.title = title
        self.status = status
        self.detail = detail
        self.instance = instance
        self.code = code
        self.trace_id = trace_id
        self.invalid_params= invalid_params
        self.retry_after=retry_after
        super().__init__(detail)

class ProblemaDominio (Exception):
    def __init__(self, type: str = "", title: str = "", status: int = None, detail: str = "", instance: str = "", code: str = None, trace_id: str = None, invalid_params = None,retry_after:int|None=None):
        if not (400 <= status <= 599) or None:
            raise ValueError(
                f"El código de estado HTTP '{status}' es inválido para un problema. "
                "Debe estar estrictamente entre 400 y 599."
            )
        
        self.type = type
        self.title = title
        self.status = status
        self.detail = detail
        self.instance = instance
        self.code = code
        self.trace_id = trace_id
        self.invalid_params= invalid_params
        self.retry_after=retry_after
        super().__init__(detail)

class NoAutenticado (ProblemaGenerico):
    def __init__(self, detail:str="Falla en autenticacion o certificados no validos"):
            super().__init__(
                title = "No Autenticado",
                status = 401,
                detail = detail,
                code = "NO_AUTENTICADO")

class SinPermiso (ProblemaGenerico):
    def __init__(self, detail:str="El usuario no posee los permisos necesarios para acceder a este recurso"):
        super().__init__(
            title = "Sin Permiso",
            status = 403,
            detail = detail,
            code = "SIN_PERMISO")

class LimiteExcedido (ProblemaGenerico): #tiene retry after
    def __init__(self, detail:str="Se ha excedido en cantidad de consultas, intente en mas tarde.",retry_after:int|None=None):
        super().__init__(
            title = "Limite Excedido",
            status = 429,
            detail = detail,
            retry_after=retry_after,
            code = "LIMITE_EXCEDIDO")

class TiempoAgotado (ProblemaDominio): #TODO: tiene retry after y se implementa cuando se "consume" algo
    def __init__(self, detail:str="Se agoto el tiempo en espera de respuesta.",retry_after:int|None=None):
        super().__init__(
            type ="/errores/tiempoagotado/",
            title = "Tiempo Agotado",
            status = 504,
            detail = detail,
            retry_after=retry_after,
            code = "TIEMPO_AGOTADO")

class DependenciaNoDisponible(ProblemaDominio):
    def __init__(self, detail:str="La dependencia externa no esta disponible",retry_after:int|None=None):
        super().__init__(
            type = "/errores/dependencianodisponible/",
            title = "Dependencia No Disponible",
            status = 503,
            detail = detail,
            retry_after=retry_after,
            code = "DEPENDENCIA_NO_DISPONIBLE")

class FaltaHeaderIdempotencia(ProblemaGenerico):
    def __init__(self,detail:str ="Peticion incompleta, header 'idempotencyKey' es obligatoria para procesar esta operación."):
        super().__init__(
        title="Solicitud Invalida",
        status=400,
        detail=detail,
        code="HEADER_IDEMPOTENCIA_FALTANTE"
        )

class HashBodyDiferente(ProblemaDominio):
    def __init__(self,detail:str="Conflicto reutilizacion de 'idempotency_key' con datos distintos"):
        super().__init__(
            type = "/errores/conflictohash/",
            title = "Conflicto",
            status = 409,
            detail = detail,
            code = "IDEMPOTENCIA_CONFLICTO"
        )

class ErrorTimeStamp(ProblemaGenerico):
    def __init__(self, detail:str="Timestamp anterior a la ubicación vigente, o mismo timestamp con datos distintos/iguales."):
        super().__init__(
            title = "Conflicto",
            status = 409,
            detail = detail,
            code = "CONFLICTO_TIMESTAMP")


class ErrorEvento_id(ProblemaGenerico):
    def __init__(self, detail:str="Evento duplicado para la operacion."):
        super().__init__(
            title = "Conflicto",
            status = 409,
            detail = detail,
            code = "CONFLICTO_EVENTO_ID")

class ErrorHealthCheck(ProblemaDominio):
    def __init__(self, detail:str="Fallo en la verificacion de salud del servicio"):
        super().__init__(
            type = "/errores/healthcheck/",
            title = "Fallo en Health Check",
            status = 503,
            detail = detail,
            code = "HEALTH_CHECK_FALLO")
