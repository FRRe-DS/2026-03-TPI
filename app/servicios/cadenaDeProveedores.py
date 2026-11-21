import logging, threading
from app.esquemas.esquemas import ConsultaGeocodificacion
from app.servicios.adaptador import GeoProveedor
from app.servicios.geocodif_diccionario import Dicc_geocodif
from app.servicios.geocodif_Geopy import ProovedorGeoRef_Geopy
from app.servicios.geocodif_photon import ProveedorPhoton

class BalanceadorExternoGeocodif(GeoProveedor):
    """Selecciona un proveedor externo por consulta en Round-Robin."""

    def __init__(self, proveedores: list[GeoProveedor] | None = None):
        self.proveedores: list[GeoProveedor] = proveedores or [
            ProveedorPhoton(),ProovedorGeoRef_Geopy(),] #se deja abierta la opcion de inyectar un proveedor manualmente
        self._lock = threading.Lock()
        self._indice = 0

    def _siguiente_proveedor(self) -> GeoProveedor:
        with self._lock:
            proveedor = self.proveedores[self._indice % len(self.proveedores)]
            self._indice = (self._indice + 1) % len(self.proveedores)
            return proveedor

    def buscar(self, body: ConsultaGeocodificacion) -> dict:
        proveedor = self._siguiente_proveedor()#alterna proveedores cada vez que se usa
        return proveedor.buscar(body)


class AdaptadorEncadenado:
    """
    Clase que implementa un encadenamiento para la geocodificación.
    Permite encadenar múltiples proveedores de geocodificación y buscar en ellos alternamente. segun preferencia.
    implementa tambien un balanceador de carga para los proveedores externos, para no saturar uno solo.
    """
    def __init__(self,proveedor_local: GeoProveedor | None = None,proveedor_ext: GeoProveedor | None = None,):
        self.proveedorLocal = proveedor_local or Dicc_geocodif()#deja abierta posibilidad de inyeccion
        self.proveedorExt = proveedor_ext or BalanceadorExternoGeocodif()#deja abierta posibilidad de inyeccion
        self.logger = logging.getLogger(__name__)

    def resolver(self, body: ConsultaGeocodificacion) -> dict:
        try:
            resultado_local = self.proveedorLocal.buscar(body)
            if resultado_local.get("coincidencias"):#si encontro algo el diccionario lo devuelve y para el proceso
                return resultado_local
        except Exception as e:# si no encontro nada o surgio un error inesperado, se deriva a proveedor externo
            self.logger.warning(f"Fallo en proveedor local ({type(e).__name__}), derivando a proveedor externo.")
            #se registra el error en logs y se sigue con el flujo normal, no se interrumpe la ejecucion
        return self.proveedorExt.buscar(body) #retorna el resultado de 1 proveedor ya sea error/excepcion o lista vacia