from uuid import uuid4

from app.db.cache_config import cache
from app.modelos.cache_models import CacheResTemp


def test_reserva_repite_resultado_y_rechaza_body_distinto(cliente_test):
    conductor_id = uuid4()
    solicitud_id = uuid4()
    clave = f"integration-{uuid4()}"
    url = f"/api/v1/conductores/{conductor_id}/reserva"
    body = {
        "estado_temporal": "RESERVADO",
        "solicitud_id": str(solicitud_id),
    }
    headers = {"Idempotency-Key": clave}

    try:
        primera = cliente_test.post(url, json=body, headers=headers)
        repetida = cliente_test.post(url, json=body, headers=headers)
        diferente = cliente_test.post(
            url,
            json={"estado_temporal": "LIBERADO", "solicitud_id": str(solicitud_id)},
            headers=headers,
        )

        assert primera.status_code == 201
        assert primera.json()["estado_temporal"] == "RESERVADO"
        assert repetida.status_code == 201
        assert repetida.json() == primera.json()
        assert diferente.status_code == 422
        assert diferente.json()["status"] == 422
        assert diferente.headers["content-type"] == "application/problem+json"
        assert all(
            respuesta.headers["x-request-id"]
            for respuesta in (primera, repetida, diferente)
        )
    finally:
        cache.delete(f"idempotency:{clave}")
        CacheResTemp.delete(str(conductor_id))
