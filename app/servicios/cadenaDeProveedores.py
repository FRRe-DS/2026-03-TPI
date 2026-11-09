from app.esquemas.esquemas import ConsultaGeocodificacion
from app.servicios.geocodif_diccionario import Dicc_geocodif
from app.servicios.geocodif_Geopy import ProovedorGeoRef_Geopy

class AdaptadorEncadenado:
    """
    Clase que implementa un adaptador encadenado para la geocodificación.
    Permite encadenar múltiples proveedores de geocodificación y buscar en ellos secuencialmente. segun preferencia.
    """

    def __init__(self):
        #Inicializa el adaptador encadenado con una lista de proveedores.
        #El orden de llamado es el mismo orden de la lista.
        self.proveedorLocal=Dicc_geocodif()
        self.proveedorExt=ProovedorGeoRef_Geopy()

    def resolver(self, body: ConsultaGeocodificacion) -> dict:
        # 1. Primer eslabón: Intentar buscar en el diccionario local (caché en RAM)
        resultado_local = self.proveedorLocal.buscar(body)
        
        if resultado_local.get("coincidencias"):
            print("[Chain] Coincidencia encontrada en el diccionario local.")
            return resultado_local
        
        # 2. Segundo eslabón (Fallback): Si no hay nada local, consultamos la API externa
        print("[Chain] Sin coincidencias locales. Derivando a Geopy...")
        resultado_externo = self.proveedorExt.buscar(body)
        
        return resultado_externo