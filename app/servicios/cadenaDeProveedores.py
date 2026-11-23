import logging, threading
from app.esquemas.esquemas import ConsultaGeocodificacion
from app.servicios.adaptador import GeoProveedor
from app.servicios.geocodif_diccionario import Dicc_geocodif
from app.servicios.geocodif_Geopy import ProovedorGeoRef_Geopy
from app.servicios.geocodif_photon import ProveedorPhoton

logger = logging.getLogger(__name__)

class BalanceadorExternoGeocodif(GeoProveedor):
    """Selecciona un proveedor externo por consulta en Round-Robin."""

    def __init__(self, proveedores: list[GeoProveedor] | None = None):
        #se deja abierta la opcion de inyectar un proveedor manualmente
        self.proveedores: list[GeoProveedor] = proveedores or [ProveedorPhoton(),ProovedorGeoRef_Geopy(),] 
        self._lock = threading.Lock()
        self._indice = 0
        logger.info("BalanceadorExternoGeocodif inicializado proveedores=%s",[type(p).__name__ for p in self.proveedores],)

    def _siguiente_proveedor(self) -> GeoProveedor:
        with self._lock:
            proveedor = self.proveedores[self._indice % len(self.proveedores)]
            self._indice = (self._indice + 1) % len(self.proveedores)
            return proveedor

    def buscar(self, body: ConsultaGeocodificacion, trace_id:str) -> dict:
        proveedor = self._siguiente_proveedor()#alterna proveedores cada vez que se usa
        logger.info("[trace_id=%s]|Delegando geocodificación externa|Proveedor=%s",trace_id,type(proveedor).__name__,)
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

    def resolver(self, body: ConsultaGeocodificacion,trace_id:str) -> dict:
        try:
            resultado_local = self.proveedorLocal.buscar(body,trace_id)
            if resultado_local.get("coincidencias"):#si encontro algo el diccionario lo devuelve y para el proceso
                self.logger.info("[trace_id=%s]|Geocodificación resuelta desde proveedor local=%s",trace_id,type(self.proveedorLocal).__name__,)
                return resultado_local
            self.logger.info("[trace_id=%s]|Sin coincidencias en proveedor local=%s; derivando a externo",trace_id,type(self.proveedorLocal).__name__,)
        except Exception as e:# si no encontro nada o surgio un error inesperado, se deriva a proveedor externo
            self.logger.warning("[trace_id=%s]|Fallo en proveedor local=%s error_tipo=%s; derivando a proveedor externo",trace_id,type(self.proveedorLocal).__name__,
                type(e).__name__,exc_info=True,)
            #se registra el error en logs y se sigue con el flujo normal, no se interrumpe la ejecucion
        return self.proveedorExt.buscar(body,trace_id) #retorna el resultado de 1 proveedor ya sea error/excepcion o lista vacia