"""
el propocito de este codigo es la utilizacion de un diccionario de ubicaciones conocidas que es utilizado
como opcion predeterminada para la geocodificacion, para evitar utilizar el servicio externo que es muchisimo
mas lento y costoso, ademas de que el diccionario puede ser actualizado y mejorado con el tiempo.
"""
import json, unicodedata, logging
from pathlib import Path
from app.servicios.adaptador import GeoProveedor
from app.esquemas.esquemas import ConsultaGeocodificacion

BASE_DIR = Path(__file__).resolve().parent.parent

class Dicc_geocodif(GeoProveedor):

    def __init__(self, ruta: str = str(BASE_DIR / "data" / "cache_geografico_nea.json")):
        self.logger = logging.getLogger(__name__)
        # Se ejecuta UNA SOLA VEZ al iniciar la app, cargando el archivo en RAM
        self.ubicaciones_conocidas = self._cargar_en_memoria(ruta)
        if self.ubicaciones_conocidas:
            self.logger.info("Diccionario cargado exitosamente")


    def _cargar_en_memoria(self, ruta: str) -> dict:
        try:
            archivo_path = Path(ruta)
            if archivo_path.exists():
                with open(archivo_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            self.logger.warning("Archivo de diccionario local no encontrado ruta=%s",ruta,)
        except Exception:# el .exeption ya muestra el valor de la excepcion al final, asi que no hace falta colocarla, lo hace por detras
            self.logger.exception("No se pudo cargar el diccionario local: %s",ruta,)
        return {}
    
    @staticmethod
    def _normalizar_texto(texto: str) -> str:
        """
        Pasa a minúsculas, quita espacios extra y remueve acentos/diacríticos.
        Ejemplo: 'Plaza 25 de Mayo, Resistencia' -> 'plaza 25 de mayo, resistencia'
        """
        if not texto:
            return ""
        texto = texto.strip().lower()
        # Elimina acentos (NFD separa la letra del acento, Mn son los diacríticos)
        texto = "".join(
            c for c in unicodedata.normalize("NFD", texto)
            if unicodedata.category(c) != "Mn"
        )
        return texto
    
    def buscar(self, body: ConsultaGeocodificacion,trace_id:str) -> dict:
        self.logger.info("[trace_id=%s]|Busqueda por diccionario local.",trace_id)
        query_normalizada = self._normalizar_texto(body.direccion)
        if not query_normalizada:
            return {"coincidencias": []}
        pais_normalizado = self._normalizar_texto(body.pais) if body.pais else ""
        coincidencias_encontradas = []
        for _, lista_lugares in self.ubicaciones_conocidas.items():
            for lugar in lista_lugares:
                if pais_normalizado:
                    lugar_pais = self._normalizar_texto(lugar.get("pais", ""))
                    if lugar_pais != pais_normalizado:
                        continue
                for alias in lugar.get("alias", []):
                    alias_normalizado = self._normalizar_texto(alias)
                    # Coincidencia bidireccional (subcadena)
                    if (alias_normalizado in query_normalizada
                        or query_normalizada in alias_normalizado):
                        coincidencias_encontradas.append({
                            "latitud": lugar["latitud"],
                            "longitud": lugar["longitud"],
                            "etiqueta": lugar["etiqueta"],
                            "confianza": lugar["confianza"],})
                        break  # Evita duplicar el mismo lugar si coinciden varios alias
        if coincidencias_encontradas:
            self.logger.info("[trace_id=%s]|Busqueda local exitosa.|Cantidad encontrada = %d",trace_id,len(coincidencias_encontradas))
        else:
            self.logger.info("[trace_id=%s]|Busqueda local no encontro resultados.",trace_id)
        return {"coincidencias": coincidencias_encontradas}