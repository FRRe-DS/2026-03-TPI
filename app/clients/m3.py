from dataclasses import dataclass
from enum import Enum
import math
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.core.errors import M3TimeoutError, M3UnavailableError
from app.core.observability import request_id_context
from app.schemas.schemas import TipoVehiculo


class EstadoHabilitacionM3(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    OBSERVED = "OBSERVED"
    SUSPENDED = "SUSPENDED"
    REJECTED = "REJECTED"


class RespuestaElegibilidadM3(BaseModel):
    estado_habilitacion: EstadoHabilitacionM3
    tipos_vehiculo_habilitados: list[TipoVehiculo]

    model_config = ConfigDict(extra="forbid")

    @field_validator("tipos_vehiculo_habilitados")
    @classmethod
    def vehicle_types_must_be_unique(
        cls, value: list[TipoVehiculo]
    ) -> list[TipoVehiculo]:
        if len(value) != len(set(value)):
            raise ValueError("M3 no debe repetir tipos de vehículo.")
        return value


@dataclass(frozen=True)
class ElegibilidadConductor:
    estado_habilitacion: EstadoHabilitacionM3
    tipos_vehiculo_habilitados: tuple[TipoVehiculo, ...]

    @property
    def aprobado(self) -> bool:
        return self.estado_habilitacion is EstadoHabilitacionM3.APPROVED

    def habilitado_para(self, tipo_vehiculo: TipoVehiculo | None = None) -> bool:
        if not self.aprobado:
            return False
        if tipo_vehiculo is None:
            return bool(self.tipos_vehiculo_habilitados)
        return tipo_vehiculo in self.tipos_vehiculo_habilitados

    @classmethod
    def from_response(cls, response: RespuestaElegibilidadM3) -> "ElegibilidadConductor":
        return cls(
            estado_habilitacion=response.estado_habilitacion,
            tipos_vehiculo_habilitados=tuple(response.tipos_vehiculo_habilitados),
        )


class ClienteM3:
    def __init__(
        self,
        *,
        base_url: str,
        service_token: str,
        eligibility_path: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if (
            not eligibility_path.startswith("/")
            or "{conductor_id}" not in eligibility_path
        ):
            raise ValueError(
                "eligibility_path debe ser absoluta e incluir {conductor_id}."
            )
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds debe ser positivo y finito.")
        if not service_token.strip():
            raise ValueError("service_token no puede estar vacío.")
        parsed_base_url = httpx.URL(base_url)
        if (
            parsed_base_url.scheme not in {"http", "https"}
            or not parsed_base_url.host
            or parsed_base_url.username
            or parsed_base_url.password
            or parsed_base_url.query
            or parsed_base_url.fragment
        ):
            raise ValueError("base_url debe ser HTTP(S) y no incluir credenciales.")
        self._eligibility_path = eligibility_path
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {service_token}"},
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    async def get_eligibility(
        self, conductor_id: UUID
    ) -> ElegibilidadConductor:
        request_id = request_id_context.get()
        headers = {"X-Request-Id": request_id} if request_id else None
        path = self._eligibility_path.format(conductor_id=conductor_id)
        try:
            response = await self._client.get(path, headers=headers)
            response.raise_for_status()
            payload = RespuestaElegibilidadM3.model_validate(response.json())
        except httpx.TimeoutException as error:
            raise M3TimeoutError() from error
        except httpx.HTTPStatusError as error:
            if error.response.status_code in (408, 504):
                raise M3TimeoutError() from error
            raise M3UnavailableError() from error
        except (httpx.RequestError, ValueError, ValidationError) as error:
            raise M3UnavailableError() from error
        return ElegibilidadConductor.from_response(payload)

    async def aclose(self) -> None:
        await self._client.aclose()
