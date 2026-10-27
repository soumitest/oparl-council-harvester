"""OParl HTTP client: retries, pagination, defensive parsing.

Handles: network failures, 429/5xx (retried with backoff), malformed JSON,
OParl 'Error' objects returned with HTTP 200, empty pages, pagination loops.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterator

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)

USER_AGENT = "oparl-council-harvester/0.1 (+technical assignment; contact via repo)"


class OParlError(Exception):
    """Base error for the client."""


class OParlHTTPError(OParlError):
    """Non-retryable HTTP error (e.g. 404, 403)."""


class OParlMalformedResponse(OParlError):
    """Response is not valid JSON or not the expected OParl shape."""


class OParlServerError(OParlError):
    """Server answered with an OParl Error object (often HTTP 200)."""


class _Retryable(Exception):
    pass


@dataclass
class PageStats:
    pages: int = 0
    items: int = 0
    malformed_items: int = 0
    stopped_reason: str = "end"  # end | loop | max_pages


class OParlClient:
    def __init__(
        self,
        timeout: float = 20.0,
        max_retries: int = 4,
        backoff: float = 1.0,
        http: httpx.Client | None = None,
    ):
        self.max_retries = max_retries
        self.backoff = backoff
        self._http = http or httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "OParlClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---------- low level ----------
    def get_json(self, url: str, params: dict | None = None) -> dict[str, Any]:
        retryer = Retrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=self.backoff, max=30),
            retry=retry_if_exception_type(_Retryable),
            reraise=True,
        )
        try:
            for attempt in retryer:
                with attempt:
                    return self._get_once(url, params)
        except _Retryable as exc:
            raise OParlHTTPError(f"giving up on {url}: {exc}") from exc
        raise AssertionError("unreachable")

    def _get_once(self, url: str, params: dict | None) -> dict[str, Any]:
        try:
            resp = self._http.get(url, params=params)
        except httpx.TransportError as exc:  # timeouts, DNS, connection reset...
            log.warning("network error on %s: %s", url, exc)
            raise _Retryable(str(exc)) from exc

        if resp.status_code == 429 or resp.status_code >= 500:
            log.warning("HTTP %s on %s (will retry)", resp.status_code, url)
            raise _Retryable(f"HTTP {resp.status_code}")
        if resp.status_code >= 400:
            raise OParlHTTPError(f"HTTP {resp.status_code} on {url}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise OParlMalformedResponse(f"invalid JSON from {url}") from exc
        if not isinstance(data, dict):
            raise OParlMalformedResponse(f"expected JSON object from {url}")

        # Some servers answer HTTP 200 + an OParl Error object ("OParl is not active").
        type_ = str(data.get("type", ""))
        if type_.endswith("/Error") or type_ == "Error":
            raise OParlServerError(f"{url}: {data.get('message') or data}")
        return data

    # ---------- OParl navigation ----------
    def get_system(self, system_url: str) -> dict[str, Any]:
        system = self.get_json(system_url)
        if "body" not in system:
            raise OParlMalformedResponse(f"System object without 'body': {system_url}")
        return system

    def iter_objects(
        self,
        list_url: str,
        params: dict | None = None,
        stats: PageStats | None = None,
        max_pages: int = 10_000,
    ) -> Iterator[dict[str, Any]]:
        """Yield objects of an OParl list, following links.next.

        `params` (e.g. {'modified_since': '...'}) are applied to the first request
        only: later pages are full URLs that already carry the cursor.
        """
        stats = stats if stats is not None else PageStats()
        seen: set[str] = set()
        url: str | None = list_url
        first = True
        while url:
            if url in seen:
                log.error("pagination loop detected at %s", url)
                stats.stopped_reason = "loop"
                return
            if stats.pages >= max_pages:
                stats.stopped_reason = "max_pages"
                return
            seen.add(url)

            page = self.get_json(url, params if first else None)
            first = False
            stats.pages += 1

            data = page.get("data")
            if data is None:
                data = []  # empty response: nothing to do, not an error
            if not isinstance(data, list):
                raise OParlMalformedResponse(f"'data' is not a list at {url}")
            for item in data:
                if isinstance(item, dict) and item.get("id"):
                    stats.items += 1
                    yield item
                else:
                    stats.malformed_items += 1
                    log.warning("skipping malformed item on %s: %r", url, item)

            links = page.get("links") or {}
            url = links.get("next") if isinstance(links, dict) else None
