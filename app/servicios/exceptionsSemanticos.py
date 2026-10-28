
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

class DependenciaNoDisponible (CodHTTPErrores):
    # 503
    pass

class TiempoAgotado (CodHTTPErrores):
    # 504
    pass

