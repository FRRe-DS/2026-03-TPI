from datetime import datetime, timezone
from typing import List
from uuid import UUID
from geopy.distance import geodesic
from app.db.cache_config import cache
from app.modelos.cache_models import UbicacionesCond, CacheEstOp, CacheResTemp
from app.esquemas import QueryCercanos, ResultadoBusquedaConductores, Candidatos, VehiculosSoportados

# Radios progresivos según contrato: inicia en 5 km, amplía en +1.5 km hasta máx 9.5 km
RADIOS_PROGRESIVOS = [5.0, 6.5, 8.0, 9.5]

def _mock_verificar_habilitacion_m3(conductor_id: UUID, tipo_vehiculo: VehiculosSoportados) -> bool:
    """
    PUNTO DE INTEGRACIÓN SINCRÓNICA CON M3 (MOCK / SIMULACIÓN)
    Cuando M3 esté disponible, debe verificar que el conductor tenga estado APPROVED
    y el tipo de vehículo habilitado. Si M3 falla, se debe lanzar excepción para
    que el llamador descarte al candidato (no devolver candidatos sin validar).
    """
    return True

class CandidatosCercanos:
    @staticmethod
    def buscar(query: QueryCercanos) -> ResultadoBusquedaConductores:
        try:
            todas_ubicaciones = UbicacionesCond.find().all()
        except Exception:
            todas_ubicaciones = []

        candidatos_finales: List[Candidatos] = []
        # radio_aplicado por defecto al máximo (si no hay candidatos en ningún radio)
        radio_aplicado = RADIOS_PROGRESIVOS[-1]

        # Búsqueda progresiva: se detiene al primer radio que devuelva candidatos
        for radio_km in RADIOS_PROGRESIVOS:
            candidatos_radio: List[Candidatos] = []

            for ubicacion in todas_ubicaciones:
                conductor_id = ubicacion.conductor_id
                lat_cond = ubicacion.geo.latitud
                lon_cond = ubicacion.geo.longitud

                # Calcular distancia en línea recta con geopy
                punto_origen = (query.origen_latitud, query.origen_longitud)
                punto_conductor = (lat_cond, lon_cond)
                distancia_km = geodesic(punto_origen, punto_conductor).kilometers

                if distancia_km > radio_km:
                    continue  # fuera del radio actual, descartar

                # Validar connected y available desde cache propio (M4)
                try:
                    estado_op = CacheEstOp.get(str(conductor_id))
                    connected = getattr(estado_op, 'connected', False)
                    available = getattr(estado_op, 'available', False)
                    if not estado_op or not connected or not available:
                        continue
                except Exception:
                    continue  # no se pudo verificar estado operativo, descartar

                # Verificar que no tenga reserva temporal activa
                try: #TODO: Esto puede cambiar por contrato nuevo, verificar. 
                    reserva = CacheResTemp.get(str(conductor_id))
                    if reserva and reserva.estado_temporal == "RESERVADO":
                        continue  # reservado en otra solicitud, descartar
                except Exception:
                    continue  # no se pudo verificar reserva, descartar (no devolver sin validar)

                # Verificar habilitación con M3 (APPROVED + vehículo habilitado)
                # Si M3 falla, se descarta el candidato: M4 no devuelve candidatos sin validar
                try:
                    if not _mock_verificar_habilitacion_m3(conductor_id, query.tipo_vehiculo):
                        continue
                except Exception:
                    continue  # M3 no disponible → descartar según contrato

                # Candidato válido: construir objeto con ETA estimado (~3 min/km)
                eta_estimado = max(1, round(distancia_km * 3))
                candidato = Candidatos(
                    conductor_id=conductor_id,
                    distancia_origen_km=round(distancia_km, 2),
                    eta_retiro_minutos=eta_estimado,
                    tipo_vehiculo=query.tipo_vehiculo
                )
                candidatos_radio.append(candidato)

            if candidatos_radio: 
                """
                Si hay un solo candidato en cierto radio, se detiene la busqueda progresiva y 
                solo se devuelve un candidato por lo que si se rechaza ese conductor se queda 
                sin candidatos de radio mas lejanos
                """
                # Encontramos candidatos en este radio, detenemos la búsqueda progresiva
                candidatos_finales = candidatos_radio
                radio_aplicado = radio_km
                break
            # Sin candidatos en este radio → continuar con el siguiente (más amplio)

        # Ordenar por distancia ascendente (el más cercano primero)
        candidatos_finales.sort(key=lambda x: x.distancia_origen_km)

        # Aplicar límite si fue especificado
        if query.limite:
            candidatos_finales = candidatos_finales[:query.limite]

        return ResultadoBusquedaConductores(
            conductores=candidatos_finales,
            radio_aplicado_km=radio_aplicado,
            generado_en=datetime.now(timezone.utc)
        )
