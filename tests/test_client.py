import httpx
import pytest
import respx

from harvester.client import (
    OParlClient,
    OParlHTTPError,
    OParlMalformedResponse,
    OParlServerError,
    PageStats,
)

BASE = "https://ris.example.de/oparl"


@pytest.fixture
def client():
    with OParlClient(max_retries=3, backoff=0) as c:
        yield c


def page(items, next_url=None):
    body = {"data": items}
    if next_url:
        body["links"] = {"next": next_url}
    return body


@respx.mock
def test_follows_pagination_until_no_next(client):
    # most specific route first: respx matches routes in registration order
    respx.get(f"{BASE}/paper", params={"page": "2"}).respond(200, json=page([{"id": "p3"}]))
    respx.get(f"{BASE}/paper").respond(200, json=page([{"id": "p1"}, {"id": "p2"}], f"{BASE}/paper?page=2"))
    stats = PageStats()
    ids = [o["id"] for o in client.iter_objects(f"{BASE}/paper", stats=stats)]
    assert ids == ["p1", "p2", "p3"]
    assert stats.pages == 2 and stats.items == 3


@respx.mock
def test_empty_response_yields_nothing(client):
    respx.get(f"{BASE}/paper").respond(200, json={"data": []})
    assert list(client.iter_objects(f"{BASE}/paper")) == []


@respx.mock
def test_missing_data_key_is_treated_as_empty(client):
    respx.get(f"{BASE}/paper").respond(200, json={})
    assert list(client.iter_objects(f"{BASE}/paper")) == []


@respx.mock
def test_malformed_items_are_skipped_and_counted(client):
    respx.get(f"{BASE}/paper").respond(200, json=page([{"id": "p1"}, "garbage", {"title": "no id"}]))
    stats = PageStats()
    ids = [o["id"] for o in client.iter_objects(f"{BASE}/paper", stats=stats)]
    assert ids == ["p1"]
    assert stats.malformed_items == 2


@respx.mock
def test_retries_on_503_then_succeeds(client):
    route = respx.get(f"{BASE}/paper")
    route.side_effect = [httpx.Response(503), httpx.Response(200, json=page([{"id": "p1"}]))]
    assert [o["id"] for o in client.iter_objects(f"{BASE}/paper")] == ["p1"]
    assert route.call_count == 2


@respx.mock
def test_retries_on_network_error_then_gives_up(client):
    route = respx.get(f"{BASE}/paper")
    route.side_effect = httpx.ConnectError("boom")
    with pytest.raises(OParlHTTPError):
        list(client.iter_objects(f"{BASE}/paper"))
    assert route.call_count == 3


@respx.mock
def test_404_is_not_retried(client):
    route = respx.get(f"{BASE}/paper").respond(404)
    with pytest.raises(OParlHTTPError):
        list(client.iter_objects(f"{BASE}/paper"))
    assert route.call_count == 1


@respx.mock
def test_invalid_json_raises_malformed(client):
    respx.get(f"{BASE}/paper").respond(200, content=b"<html>not json</html>")
    with pytest.raises(OParlMalformedResponse):
        list(client.iter_objects(f"{BASE}/paper"))


@respx.mock
def test_oparl_error_object_with_http_200(client):
    respx.get(f"{BASE}/system").respond(
        200, json={"type": "https://schema.oparl.org/1.1/Error", "message": "OParl is not active."}
    )
    with pytest.raises(OParlServerError):
        client.get_system(f"{BASE}/system")


@respx.mock
def test_pagination_loop_is_detected(client):
    respx.get(f"{BASE}/paper").respond(200, json=page([{"id": "p1"}], f"{BASE}/paper"))
    stats = PageStats()
    list(client.iter_objects(f"{BASE}/paper", stats=stats))
    assert stats.stopped_reason == "loop"


@respx.mock
def test_modified_since_only_sent_on_first_request(client):
    first = respx.get(f"{BASE}/paper", params={"modified_since": "2026-10-01T00:00:00+00:00"}).respond(
        200, json=page([{"id": "p1"}], f"{BASE}/paper?cursor=abc")
    )
    second = respx.get(f"{BASE}/paper?cursor=abc").respond(200, json=page([{"id": "p2"}]))
    list(client.iter_objects(f"{BASE}/paper", params={"modified_since": "2026-10-01T00:00:00+00:00"}))
    assert first.called and second.called
    assert "modified_since" not in str(second.calls[0].request.url)
