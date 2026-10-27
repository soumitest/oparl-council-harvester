import pytest
from harvester.geo import InvalidCoordinate, wgs84_to_25832


def test_frankfurt_roemer_is_in_expected_utm_range():
    p = wgs84_to_25832(lon=8.6821, lat=50.1109)
    assert 470_000 < p.x < 485_000
    assert 5_540_000 < p.y < 5_560_000


def test_swapped_lat_lon_is_rejected():
    with pytest.raises(InvalidCoordinate):
        wgs84_to_25832(lon=50.1109, lat=8.6821)


@pytest.mark.parametrize("lon,lat", [("abc", 50.1), (None, None), (float("nan"), 50.1), (200, 50.1)])
def test_malformed_values_are_rejected(lon, lat):
    with pytest.raises(InvalidCoordinate):
        wgs84_to_25832(lon, lat)


def test_far_away_point_is_rejected():
    with pytest.raises(InvalidCoordinate):
        wgs84_to_25832(lon=13.405, lat=52.52)  # Berlin
