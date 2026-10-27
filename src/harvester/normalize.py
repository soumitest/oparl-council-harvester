"""OParl Paper -> flat staging record.

Nothing is guessed: a missing or broken field stays NULL and is reported in
`Record.issues`, so the quality report can count it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from .filters import match_keywords
from .geo import InvalidCoordinate, wgs84_to_25832


@dataclass
class Record:
    source_system: str
    source_id: str
    object_type: str
    title: str | None
    source_url: str | None
    published_at: datetime | None
    matched_keywords: list[str]
    body_name: str | None
    body_ags: str | None
    location_text: str | None
    x: float | None
    y: float | None
    geom_status: str  # resolved | unresolved | invalid | none
    geom_note: str | None
    raw: dict[str, Any]
    issues: list[str] = field(default_factory=list)


def _clean(value: Any) -> str | None:
    if isinstance(value, str):
        value = " ".join(value.split())  # also collapses newlines inside titles
        return value or None
    return None


def parse_datetime(value: Any) -> datetime | None:
    """Parse an OParl date / date-time. Naive values are taken as UTC.

    Raises ValueError for anything that is not a valid ISO 8601 date(-time).
    """
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"not a string: {value!r}")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        dt = datetime.combine(date.fromisoformat(text), datetime.min.time())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _location_text(loc: dict[str, Any]) -> str | None:
    street = _clean(loc.get("streetAddress"))
    town = " ".join(p for p in (_clean(loc.get("postalCode")), _clean(loc.get("locality"))) if p)
    parts = [
        _clean(loc.get("description")),
        street,
        town or None,
        _clean(loc.get("subLocality")),
        _clean(loc.get("room")),
    ]
    text = ", ".join(p for p in parts if p)
    return text or None


def _first_point(geometry: Any) -> tuple[list | None, str | None]:
    """Return (coordinates, problem) from a GeoJSON Feature / Collection / Geometry."""
    if not isinstance(geometry, dict):
        return None, "geometry is not a GeoJSON object"
    gtype = geometry.get("type")
    if gtype == "FeatureCollection":
        feats = geometry.get("features") or []
        if len(feats) != 1:
            return None, f"FeatureCollection with {len(feats)} features (expected 1)"
        return _first_point(feats[0])
    if gtype == "Feature":
        return _first_point(geometry.get("geometry"))
    if gtype == "Point":
        coords = geometry.get("coordinates")
        if isinstance(coords, list) and len(coords) >= 2:
            return coords, None
        return None, "Point without usable coordinates"
    return None, f"non-point geometry '{gtype}' (not converted)"


def extract_location(paper: dict[str, Any]) -> tuple[str | None, float | None, float | None, str, str | None]:
    """-> (location_text, x, y, geom_status, geom_note). Coordinates are EPSG:25832."""
    loc = paper.get("location")
    if loc in (None, "", {}):
        return None, None, None, "none", None
    if isinstance(loc, str):
        # An un-embedded reference. We do not fetch it (one extra request per paper).
        return None, None, None, "unresolved", "location is a URL reference, not embedded"
    if not isinstance(loc, dict):
        return None, None, None, "invalid", f"unexpected location type {type(loc).__name__}"

    text = _location_text(loc)
    geometry = loc.get("geometry") or loc.get("geojson")
    if geometry is None:
        note = "address only, no coordinates in source (no geocoder used)" if text else "location without address or coordinates"
        return text, None, None, "unresolved", note

    coords, problem = _first_point(geometry)
    if coords is None:
        return text, None, None, "unresolved", problem
    try:
        pt = wgs84_to_25832(lon=coords[0], lat=coords[1])
    except InvalidCoordinate as exc:
        return text, None, None, "invalid", str(exc)
    return text, pt.x, pt.y, "resolved", None


def normalize_paper(
    paper: dict[str, Any],
    system_url: str,
    body: dict[str, Any],
) -> Record:
    issues: list[str] = []

    title = _clean(paper.get("name")) or _clean(paper.get("reference"))
    if title is None:
        issues.append("missing_title")

    source_url = _clean(paper.get("web"))
    if source_url is None:
        issues.append("missing_web_url")

    published = None
    raw_date = paper.get("date")
    if raw_date in (None, ""):
        raw_date = paper.get("created")  # fallback, clearly weaker than Paper.date
        if raw_date in (None, ""):
            issues.append("missing_date")
    try:
        published = parse_datetime(raw_date)
    except ValueError:
        issues.append("invalid_date")

    loc_text, x, y, status, note = extract_location(paper)
    if status in ("unresolved", "invalid"):
        issues.append(f"location_{status}")

    keyword_field = paper.get("keyword")
    keyword_text = " ".join(keyword_field) if isinstance(keyword_field, list) else None
    matched = match_keywords(title, _clean(paper.get("reference")), keyword_text, loc_text)

    return Record(
        source_system=system_url,
        source_id=str(paper["id"]),
        object_type="Paper",
        title=title,
        source_url=source_url,
        published_at=published,
        matched_keywords=matched,
        body_name=_clean(body.get("name")),
        body_ags=_clean(str(body.get("ags"))) if body.get("ags") is not None else None,
        location_text=loc_text,
        x=x,
        y=y,
        geom_status=status,
        geom_note=note,
        raw=paper,
        issues=issues,
    )
