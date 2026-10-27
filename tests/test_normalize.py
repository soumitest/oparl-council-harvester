from datetime import timezone

import pytest

from harvester.normalize import normalize_paper, parse_datetime

BODY = {"name": "Frankfurt am Main", "ags": "06412000"}
SYS = "https://ris.example.org/oparl/system"


def paper(**kw):
    base = {"id": "https://ris.example.org/oparl/paper/1", "name": "Rechenzentrum Osthafen",
            "date": "2026-03-12", "web": "https://ris.example.org/v/1"}
    base.update(kw)
    return base


def point(lon, lat):
    return {"geometry": {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}}}


def test_full_record_with_valid_point():
    r = normalize_paper(paper(location=point(8.7266, 50.1135)), SYS, BODY)
    assert r.geom_status == "resolved" and 470_000 < r.x < 490_000
    assert r.published_at.tzinfo is timezone.utc and r.published_at.date().isoformat() == "2026-03-12"
    assert r.body_ags == "06412000" and r.issues == []


def test_swapped_coordinates_are_invalid_not_accepted():
    r = normalize_paper(paper(location=point(50.11, 8.72)), SYS, BODY)
    assert r.geom_status == "invalid" and r.x is None and "location_invalid" in r.issues


def test_address_only_is_unresolved_with_note():
    r = normalize_paper(paper(location={"streetAddress": "Musterweg 5", "locality": "Frankfurt"}), SYS, BODY)
    assert r.geom_status == "unresolved" and "no geocoder" in r.geom_note
    assert r.location_text == "Musterweg 5, Frankfurt"


def test_location_reference_url_is_unresolved():
    r = normalize_paper(paper(location="https://ris.example.org/oparl/location/1"), SYS, BODY)
    assert r.geom_status == "unresolved"


def test_non_point_geometry_is_unresolved():
    loc = {"geometry": {"type": "Polygon", "coordinates": []}}
    assert normalize_paper(paper(location=loc), SYS, BODY).geom_status == "unresolved"


def test_missing_fields_are_reported_not_invented():
    r = normalize_paper({"id": "x", "name": "Umspannwerk"}, SYS, {"name": "Kleinstadt"})
    assert r.published_at is None and r.source_url is None and r.body_ags is None
    assert {"missing_date", "missing_web_url"} <= set(r.issues)


def test_invalid_date_is_null_and_flagged():
    r = normalize_paper(paper(date="kein-datum"), SYS, BODY)
    assert r.published_at is None and "invalid_date" in r.issues


def test_created_is_fallback_for_missing_date():
    r = normalize_paper(paper(date=None, created="2026-07-15T09:30:00+02:00"), SYS, BODY)
    assert r.published_at is not None and "missing_date" not in r.issues


@pytest.mark.parametrize("value", ["2026-03-12", "2026-03-12T10:00:00", "2026-03-12T10:00:00Z", "2026-03-12T10:00:00+01:00"])
def test_parse_datetime_accepts_oparl_formats(value):
    assert parse_datetime(value).tzinfo is not None


def test_newlines_in_titles_are_collapsed():
    r = normalize_paper(paper(name="Umspannwerk Nord\nAntrag der Fraktion"), SYS, BODY)
    assert r.title == "Umspannwerk Nord Antrag der Fraktion"
