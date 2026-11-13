from datetime import datetime, timezone
from typing import List
from uuid import UUID
from geopy.distance import geodesic
from app.db.cache_config import cache
from app.modelos.cache_models import UbicacionesCond, CacheEstOp, CacheResTemp
from app.esquemas import QueryCercanos, ResultadoBusquedaConductores, Candidatos, VehiculosSoportados

def _mock_verificar_habilitacion_m3(conductor_id: UUID, tipo_vehiculo: VehiculosSoportados) -> bool:
    """
    PUNTO DE INTEGRACIÓN SINCRÓNICA CON M3 (MOCK / SIMULACIÓN)
    """
    return True

class CandidatosCercanos:
    @staticmethod
    def buscar(query: QueryCercanos) -> ResultadoBusquedaConductores:
        try:
            todas_ubicaciones = UbicacionesCond.find().all()
        except Exception:
            todas_ubicaciones = []
        candidatos_validos: List[Candidatos] = [] #lista final valida
        #for para cada ubicacion de la redis, analisamos 1 por una, si cumple con los requisitos
        for ubicacion in todas_ubicaciones:
            conductor_id = ubicacion.conductor_id
            lat_cond = ubicacion.geo.latitud
            lon_cond = ubicacion.geo.longitud
            #utilizamos geopy para calcular distancia entre 2 coordenadas
            punto_origen = (query.origen_latitud, query.origen_longitud)
            punto_conductor = (lat_cond, lon_cond)
            distancia_km = geodesic(punto_origen, punto_conductor).kilometers
            if distancia_km > query.radio_km:
                continue #descarta la ubicacion actual y pasa al siguiente bucle
            
            #validamos inicialmente sus estados posibles de NUESTRA redis
            try:
                estado_op = CacheEstOp.get(str(conductor_id))
                connected = getattr(estado_op, 'connected', False)
                available = getattr(estado_op, 'available', False)
                if not estado_op or not connected or not available:# si alguna de las 2 es falsa no es candidato
                    continue
            except Exception:#ocurre un error inesperado o no existe registro pasamos a la siguiente ubicacion
                continue
            #comprobamos que el conductor no este reservado actualmente en otra solicitud, si lo esta no es candidato
            try:
                reserva = CacheResTemp.get(str(conductor_id))
                if reserva and reserva.estado_temporal == "RESERVADO":
                    continue #esta reservado por lo tanto no es candidato
            except Exception:
                pass #no se encontro, es posible candidato
            #####
            #aqui iria la segunda verificacion con M3, si no esta habilitado no es candidato
            if not _mock_verificar_habilitacion_m3(conductor_id, query.tipo_vehiculo):
                continue#si M3 no valida, entonces no es candidato
            ####
            #si llegamos hasta aqui, es candidato valido, agregamos a la lista final
            # 6. Construcción del candidato apto (ETA estimado simple: ~3 min por kilómetro)
            eta_estimado = max(1, round(distancia_km * 3))

            candidato = Candidatos(
                conductor_id=conductor_id,
                distancia_origen_km=round(distancia_km, 2),
                eta_retiro_minutos=eta_estimado,
                tipo_vehiculo=query.tipo_vehiculo
            )
            candidatos_validos.append(candidato)
        #ordenar candidatos por distancia de menor a mayor (del más cercano al más lejano)
        candidatos_validos.sort(key=lambda x: x.distancia_origen_km)
        # si exite limite entonces se aplica aqui.
        if query.limite:
            candidatos_validos = candidatos_validos[:query.limite]
        #devolvemos a la salida.
        return ResultadoBusquedaConductores(
            conductores=candidatos_validos,
            radio_aplicado_km=query.radio_km,#esto podira cambiar a futuro
            generado_en=datetime.now(timezone.utc)
        )
            





