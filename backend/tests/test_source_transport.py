"""Source retrieval pins vetted addresses and validates every redirect target."""
import socket

import httpx
import pytest
from backend.app.core.errors import ValidationError
from backend.app.services.routing import official_sources as sources
from httpx import AsyncClient


async def test_fetch_pins_ip_and_preserves_host_and_tls_name(monkeypatch):
    calls = []
    def resolve(host, *args, **kwargs):
        calls.append(host)
        # A second lookup would resolve privately, but the transport must never perform it.
        address = "8.8.8.8" if len(calls) == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]
    monkeypatch.setattr(sources.socket, "getaddrinfo", resolve)
    def handle(request):
        assert request.url.host == "8.8.8.8"
        assert request.headers["host"] == "official.invalid"
        assert request.extensions["sni_hostname"] == "official.invalid"
        return httpx.Response(200, text="Official source content")
    monkeypatch.setattr(sources.httpx, "AsyncClient", lambda **kwargs: AsyncClient(transport=httpx.MockTransport(handle), **kwargs))
    assert await sources.SafeFetcher.fetch_page("https://official.invalid/document") == "Official source content"
    assert calls == ["official.invalid"]


async def test_redirect_to_private_address_is_rejected(monkeypatch):
    def resolve(host, *args, **kwargs):
        address = "127.0.0.1" if host == "private.invalid" else "8.8.8.8"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]
    monkeypatch.setattr(sources.socket, "getaddrinfo", resolve)
    seen = []
    def handle(request):
        seen.append(request.url.host)
        return httpx.Response(302, headers={"location": "https://private.invalid/admin"})
    monkeypatch.setattr(sources.httpx, "AsyncClient", lambda **kwargs: AsyncClient(transport=httpx.MockTransport(handle), **kwargs))
    with pytest.raises(ValidationError, match="restricted IP"):
        await sources.SafeFetcher.fetch_page("https://official.invalid/document")
    assert seen == ["8.8.8.8"]
