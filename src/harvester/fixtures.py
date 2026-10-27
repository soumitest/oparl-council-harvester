"""Serve recorded / synthetic OParl JSON from disk, so the pipeline runs offline.

`fixtures/oparl/index.json` maps a URL to a JSON file in the same directory.
Unknown URLs answer 404, exactly like a real endpoint that moved.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx


def fixture_client(directory: str | Path) -> httpx.Client:
    directory = Path(directory)
    index: dict[str, str] = json.loads((directory / "index.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        name = index.get(url) or index.get(url.split("?", 1)[0])  # ignore e.g. modified_since
        if name is None:
            return httpx.Response(404, json={"error": "not in fixtures"})
        return httpx.Response(200, content=(directory / name).read_bytes(), headers={"content-type": "application/json"})

    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
