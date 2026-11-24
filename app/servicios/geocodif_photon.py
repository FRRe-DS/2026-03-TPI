import logging, threading, time, urllib.parse, urllib.request, json,urllib.error,socket
from app.errores.exceptionsSemanticos import DependenciaNoDisponible,TiempoAgotado
from app.esquemas.esquemas import ConsultaGeocodificacion
from app.servicios.adaptador import GeoProveedor

class ProveedorPhoton(GeoProveedor):
    def __init__(self,base_url: str = "https://photon.komoot.io/api/",tiempo_espera: float = 0.6,timeout: float = 5.0,):
        self.base_url = base_url
        self._lock = threading.Lock()
        self._ultimo_tiempo_consulta = 0.0
        self.TIEMPO_ESPERA_SEGUNDOS = tiempo_espera
        self.timeout = timeout
        # Zona permitida (Resistencia / Corrientes)
        self.ZONA_PERMITIDA = {
            "lat_min": -28.5000,
            "lat_max": -27.2000,
            "lon_min": -59.5000,
            "lon_max": -58.7000,
        }
        self.logger = logging.getLogger(__name__)

    def buscar(self, body: ConsultaGeocodificacion,trace_id:str) -> dict:
        self.logger.info("[trace_id=%s]|Utilizacion de proveedor externo Photon",trace_id)
        partes_consulta = [body.direccion.strip()]
        if body.localidad:
            partes_consulta.append(body.localidad.strip())
        if body.pais:
            partes_consulta.append(body.pais.strip())

        consulta_texto = ", ".join(p for p in partes_consulta if p)
        bbox = (
            f"{self.ZONA_PERMITIDA['lon_min']},"
            f"{self.ZONA_PERMITIDA['lat_min']},"
            f"{self.ZONA_PERMITIDA['lon_max']},"
            f"{self.ZONA_PERMITIDA['lat_max']}"
        )

        params = {"q": consulta_texto,"bbox": bbox,}
        url = f"{self.base_url}?{urllib.parse.urlencode(params)}"

        with self._lock:
            ahora = time.time()
            transcurrido = ahora - self._ultimo_tiempo_consulta
            if transcurrido < self.TIEMPO_ESPERA_SEGUNDOS:
                tiempo_a_dormir = self.TIEMPO_ESPERA_SEGUNDOS - transcurrido
                self.logger.info("[trace_id=%s]|Tiempo de espera activo.|Faltan=%.2f",trace_id,tiempo_a_dormir)
                time.sleep(tiempo_a_dormir)

            try:
                req = urllib.request.Request(url,headers={"User-Agent": "m4_transporte_app"},)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                self._ultimo_tiempo_consulta = time.time()
            except (TimeoutError, socket.timeout) as e:
                self._ultimo_tiempo_consulta = time.time()
                self.logger.warning("[trace_id=%s]|Timeout en Photon|Tipo: %s|Detalle: %s",
                    trace_id,type(e).__name__,e,)
                raise TiempoAgotado(detail="Photon tardo demaciado en responder.",retry_after=1) from e  # 504
            except urllib.error.URLError as e:
                self._ultimo_tiempo_consulta = time.time()
                if isinstance(e.reason, (TimeoutError, socket.timeout)):
                    self.logger.warning("[trace_id=%s]|Timeout de conexión en Photon|Tipo: %s|Detalle: %s",
                        trace_id,type(e.reason).__name__,e.reason,)
                    raise TiempoAgotado(detail="Photon tardo demaciado en responder.",retry_after=1) from e  # 504
                self.logger.exception("[trace_id=%s]|Photon no disponible por URLError (503)|Tipo: %s|Detalle: %s",
                    trace_id,type(e).__name__,e,)
                raise DependenciaNoDisponible(retry_after=1) from e  # 503
            except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
                self._ultimo_tiempo_consulta = time.time()
                self.logger.exception(
                    "[trace_id=%s]|Photon no disponible o respuesta inválida|Tipo: %s|Detalle: %s",
                    trace_id,type(e).__name__,e,)
                raise DependenciaNoDisponible(retry_after=1) from e  # 503

        respuesta = payload.get("features", [])
    
        coincidencias = []
        for candidato in respuesta:
            coords = candidato.get("geometry", {}).get("coordinates", [])
            if len(coords) < 2:
                continue
            lon, lat = float(coords[0]), float(coords[1])
            coincidencias.append({
                "latitud": lat,
                "longitud": lon,
                "etiqueta": body.direccion,
                "confianza": 0.8,
            })
        if coincidencias:
            self.logger.info("[trace_id=%s]|Proveedor Photon obtuvo resultados.|Cantidad=%d",trace_id,len(coincidencias))
        else:
            self.logger.info("[trace_id=%s]|Proveedor Photon no obtuvo resultados.",trace_id)
        return {"coincidencias": coincidencias}