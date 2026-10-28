import json
import math
from dataclasses import dataclass
from typing import TypeAlias

from app.core.errors import DependencyUnavailableError, DomainError
from app.schemas.schemas import PuntoGeografico

Position: TypeAlias = tuple[float, float]
Ring: TypeAlias = tuple[Position, ...]
Polygon: TypeAlias = tuple[Ring, ...]


@dataclass(frozen=True)
class CoverageArea:
    polygons: tuple[Polygon, ...]

    @classmethod
    def from_geojson(cls, document: str) -> "CoverageArea":
        try:
            data = json.loads(document)
            geometry = data.get("geometry", data)
            if geometry.get("type") == "Feature":
                geometry = geometry.get("geometry")
            geometry_type = geometry["type"]
            coordinates = geometry["coordinates"]
            if geometry_type == "Polygon":
                raw_polygons = [coordinates]
            elif geometry_type == "MultiPolygon":
                raw_polygons = coordinates
            else:
                raise ValueError("Solo se admiten Polygon y MultiPolygon.")
            polygons = tuple(
                tuple(cls._parse_ring(ring) for ring in polygon)
                for polygon in raw_polygons
            )
            if not polygons or any(not polygon for polygon in polygons):
                raise ValueError("La geometría no contiene anillos.")
        except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("COVERAGE_GEOJSON no contiene una geometría válida.") from error
        return cls(polygons=polygons)

    @staticmethod
    def _parse_ring(value: object) -> Ring:
        if not isinstance(value, list) or len(value) < 4:
            raise ValueError("Cada anillo requiere al menos cuatro posiciones.")
        positions: list[Position] = []
        for coordinate in value:
            if (
                not isinstance(coordinate, list)
                or len(coordinate) < 2
                or isinstance(coordinate[0], bool)
                or isinstance(coordinate[1], bool)
                or not isinstance(coordinate[0], (float, int))
                or not isinstance(coordinate[1], (float, int))
            ):
                raise ValueError("La posición GeoJSON debe ser [longitud, latitud].")
            longitude = float(coordinate[0])
            latitude = float(coordinate[1])
            if (
                not math.isfinite(longitude)
                or not math.isfinite(latitude)
                or not -180 <= longitude <= 180
                or not -90 <= latitude <= 90
            ):
                raise ValueError("La posición GeoJSON está fuera de WGS 84.")
            positions.append((longitude, latitude))
        if positions[0] != positions[-1]:
            raise ValueError("Los anillos GeoJSON deben estar cerrados.")
        return tuple(positions)

    @staticmethod
    def _ring_relation(point: Position, ring: Ring) -> bool | None:
        longitude, latitude = point
        inside = False
        for start, end in zip(ring, ring[1:]):
            x1, y1 = start
            x2, y2 = end
            cross = (longitude - x1) * (y2 - y1) - (latitude - y1) * (x2 - x1)
            if (
                abs(cross) <= 1e-12
                and min(x1, x2) - 1e-12 <= longitude <= max(x1, x2) + 1e-12
                and min(y1, y2) - 1e-12 <= latitude <= max(y1, y2) + 1e-12
            ):
                return None
            if (y1 > latitude) != (y2 > latitude):
                intersection = x1 + (latitude - y1) * (x2 - x1) / (y2 - y1)
                if longitude < intersection:
                    inside = not inside
        return inside

    def covers(self, point: PuntoGeografico) -> bool:
        position = (point.longitud, point.latitud)
        for polygon in self.polygons:
            shell_relation = self._ring_relation(position, polygon[0])
            if shell_relation is False:
                continue
            hole_relations = (
                self._ring_relation(position, hole) for hole in polygon[1:]
            )
            if not any(relation is True for relation in hole_relations):
                return True
        return False


def require_coverage(
    coverage: CoverageArea | None, point: PuntoGeografico
) -> None:
    if coverage is None:
        raise DependencyUnavailableError(
            "La geometría aprobada de cobertura no está configurada."
        )
    if not coverage.covers(point):
        raise DomainError(
            status_code=422,
            code="LOCATION_OUTSIDE_COVERAGE",
            title="Ubicación fuera de cobertura",
            detail="El punto se encuentra fuera de la zona geográfica habilitada.",
        )
