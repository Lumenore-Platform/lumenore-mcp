import asyncio
import logging

import pytest


def test_source_url_rejects_non_public_addresses():
    from tools.file_upload_tools import _validate_source_url

    for url in [
        "http://example.com/file.csv",            # not HTTPS
        "https://user:pass@example.com/a.csv",    # embedded credentials
        "https://127.0.0.1/a.csv",                # loopback
        "https://10.0.0.5/a.csv",                 # private
        "https://169.254.169.254/latest/meta-data",  # cloud metadata
        "https://[::1]/a.csv",                    # IPv6 loopback
        "https://[::ffff:10.0.0.1]/a.csv",        # IPv4-mapped private
        "https://localhost/a.csv",                # resolves to loopback
    ]:
        with pytest.raises(Exception):
            asyncio.run(_validate_source_url(url))


def test_source_url_allowlist(monkeypatch):
    from config import config
    from tools.file_upload_tools import _validate_source_url

    monkeypatch.setattr(config, "ALLOWED_SOURCE_URL_HOSTS", "files.example.org")
    with pytest.raises(Exception):
        asyncio.run(_validate_source_url("https://8.8.8.8/a.csv"))


def test_upload_page_only_accepts_allowed_hosts(monkeypatch):
    from config import config
    import main

    monkeypatch.setattr(config, "PUBLISH_API_BASE_URL", "https://publish.example.com/api/publish")
    monkeypatch.setattr(config, "UPLOAD_PAGE_ALLOWED_HOSTS", "")
    assert main._signed_url_allowed("https://publish.example.com/x?sig=1")
    assert not main._signed_url_allowed("https://attacker.example.net/x")
    assert not main._signed_url_allowed("http://publish.example.com/x")
    assert not main._signed_url_allowed("https://publish.example.com.attacker.net/x")


def _call_asgi(app, path, query=b""):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "GET", "path": path, "query_string": query, "headers": []}
    asyncio.run(app(scope, receive, send))
    return sent


def test_upload_page_rejects_foreign_put_url_and_sets_csp(monkeypatch):
    from urllib.parse import urlencode
    from config import config
    import main

    monkeypatch.setattr(config, "PUBLISH_API_BASE_URL", "https://publish.example.com/api/publish")
    monkeypatch.setattr(config, "BASE_PATH", "")

    async def mcp_app(scope, receive, send):  # pragma: no cover - must not be reached
        raise AssertionError("fell through to MCP app")

    app = main.create_smart_router(mcp_app)
    bad = urlencode({"put": "https://evil.example.net/p", "complete": "https://publish.example.com/c",
                     "name": "a.csv", "type": "text/csv", "size": "10"}).encode()
    assert _call_asgi(app, "/upload", bad)[0]["status"] == 400

    good = urlencode({"put": "https://publish.example.com/p", "complete": "https://publish.example.com/c",
                      "name": "a.csv", "type": "text/csv", "size": "10"}).encode()
    start = _call_asgi(app, "/upload", good)[0]
    assert start["status"] == 200
    headers = dict(start["headers"])
    csp = headers[b"content-security-policy"].decode()
    assert "frame-ancestors 'none'" in csp and "connect-src https://publish.example.com" in csp
    assert headers[b"referrer-policy"] == b"no-referrer"


def test_request_headers_are_isolated_between_tasks():
    from core.request_context import set_request_headers, get_request_headers

    async def worker(token):
        set_request_headers({"authorization": token})
        await asyncio.sleep(0)
        return get_request_headers()["authorization"]

    async def run():
        return await asyncio.gather(*(worker(f"Bearer {i}") for i in range(20)))

    assert asyncio.run(run()) == [f"Bearer {i}" for i in range(20)]

    async def fresh():
        return get_request_headers()

    assert asyncio.run(fresh()) == {}


def test_credentials_are_not_logged(caplog):
    from core.lumenore_analytics import get_lumenore_client, extract_credentials_from_headers

    caplog.set_level(logging.DEBUG)
    lumenore_logger = logging.getLogger("lumenore_analytics")
    lumenore_logger.addHandler(caplog.handler)
    try:
        creds = extract_credentials_from_headers({
            "Authorization": "Bearer SECRET-TOKEN-123",
            "Lumenore-Client-Id": "CLIENT-ID-456",
            "Lumenore-Client-Secret": "CLIENT-SECRET-789",
        })
        get_lumenore_client(**creds)
    finally:
        lumenore_logger.removeHandler(caplog.handler)
    for secret in ("SECRET-TOKEN-123", "CLIENT-ID-456", "CLIENT-SECRET-789"):
        assert secret not in caplog.text
