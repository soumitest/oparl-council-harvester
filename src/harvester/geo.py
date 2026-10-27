"""Coordinate handling: WGS84 (lon/lat) -> EPSG:25832 with explicit validation."""
from dataclasses import dataclass
from pyproj import Transformer

# always_xy=True -> input order is (lon, lat), output (easting, northing)
_TO_25832 = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)

# Generous bounding box around Hesse / Rhine-Main, in WGS84 degrees.
RHINE_MAIN_BBOX = {"lon_min": 7.7, "lon_max": 10.3, "lat_min": 49.3, "lat_max": 50.9}


class InvalidCoordinate(ValueError):
    """Raised when coordinates are malformed or outside the expected area."""


@dataclass(frozen=True)
class Point25832:
    x: float  # easting, metres
    y: float  # northing, metres


def wgs84_to_25832(lon: float, lat: float, bbox: dict | None = None) -> Point25832:
    bbox = bbox or RHINE_MAIN_BBOX
    try:
        lon, lat = float(lon), float(lat)
    except (TypeError, ValueError) as exc:
        raise InvalidCoordinate(f"non-numeric coordinates: {lon!r}, {lat!r}") from exc
    if lon != lon or lat != lat:  # NaN
        raise InvalidCoordinate("NaN coordinates")
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise InvalidCoordinate(f"out of WGS84 range: lon={lon}, lat={lat}")
    if not (bbox["lon_min"] <= lon <= bbox["lon_max"] and bbox["lat_min"] <= lat <= bbox["lat_max"]):
        raise InvalidCoordinate(
            f"outside expected area (lon/lat swapped?): lon={lon}, lat={lat}"
        )
    x, y = _TO_25832.transform(lon, lat)
    return Point25832(x=x, y=y)
