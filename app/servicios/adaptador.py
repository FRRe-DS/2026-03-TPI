from abc import ABC, abstractmethod
from app.esquemas.esquemas import ConsultaGeocodificacion

"""
usamos un patron adaptador para poder cambiar de proveedor de geocodificacion sin afectar el resto del sistema
dependemos de clases abstractas no de clases concretas, implementamos solid de esta forma y reducimos acoplamiento
"""

class GeoProveedor(ABC):
    
    @abstractmethod
    def buscar(self, body: ConsultaGeocodificacion) -> dict:
        """
        Contrato obligatorio para cualquier proveedor de geolocalización.
        Debe retornar un diccionario con la lista de coincidencias estructuradas.
        Recibe datos concretos del contrato definido en esquemas.py (ConsultaGeocodificacion).
        """
        pass
    