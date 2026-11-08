import geopy
from app.esquemas.esquemas import ConsultaEstimacionRuta


def CalculosDeViaje(datos:ConsultaEstimacionRuta):
    """
    asi se acceden a los elementos del query_params del url
    lat_origen = params.origen_latitud
    vehiculo = params.tipo_vehiculo
    """
    