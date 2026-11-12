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


def _call_asgi(app, path, query=b"", method="GET", headers=None):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        sent.append(message)

    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {"type": "http", "method": method, "path": path, "query_string": query,
             "headers": raw_headers}
    asyncio.run(app(scope, receive, send))
    return sent


def _router(monkeypatch, reached):
    from config import config
    import main

    monkeypatch.setattr(config, "BASE_PATH", "")

    async def mcp_app(scope, receive, send):
        reached.append(scope["path"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    return main.create_smart_router(mcp_app)


def _no_server_credentials(monkeypatch):
    from config import config

    for name in ("TOKEN", "CLIENT_ID", "SECRET", "PUBLISH_API_TOKEN"):
        monkeypatch.setattr(config, name, None)


def test_upload_page_keeps_signed_urls_out_of_the_request(monkeypatch):
    from urllib.parse import urlencode
    from config import config
    import main

    monkeypatch.setattr(config, "PUBLISH_API_BASE_URL", "https://publish.example.com/api/publish")
    monkeypatch.setattr(config, "UPLOAD_PAGE_ALLOWED_HOSTS", "")
    reached = []
    app = _router(monkeypatch, reached)

    # Signed URLs in the query string (the old form, which lands in access logs) are refused.
    legacy = urlencode({"put": "https://publish.example.com/p?signature=S",
                        "complete": "https://publish.example.com/c?signature=S",
                        "name": "a.csv", "type": "text/csv", "size": "10"}).encode()
    assert _call_asgi(app, "/upload", legacy)[0]["status"] == 400

    start = _call_asgi(app, "/upload")[0]
    assert start["status"] == 200
    headers = dict(start["headers"])
    csp = headers[b"content-security-policy"].decode()
    assert "frame-ancestors 'none'" in csp
    # connect-src comes from the configured allowlist, not from the request.
    assert ("connect-src https://publish.example.com:* https://*.publish.example.com:*;"
            in csp)
    assert headers[b"referrer-policy"] == b"no-referrer"
    assert "location.hash" in main.UPLOAD_PAGE_SCRIPT
    assert "location.search" not in main.UPLOAD_PAGE_SCRIPT
    assert not reached


def test_router_rejects_non_bearer_authorization(monkeypatch):
    from config import config

    reached = []
    app = _router(monkeypatch, reached)
    _no_server_credentials(monkeypatch)

    def status(headers):
        return _call_asgi(app, "/mcp", method="POST", headers=headers)[0]["status"]

    assert status({}) == 401
    assert status({"Authorization": "Basic x"}) == 401
    assert status({"Authorization": "Bearer "}) == 401
    assert status({"Authorization": "Basic x", "Lumenore-Client-Id": "a",
                   "Lumenore-Client-Secret": "b"}) == 401
    assert status({"Lumenore-Client-Id": "a"}) == 401
    assert not reached
    assert status({"Authorization": "Bearer abc"}) == 200
    assert status({"Lumenore-Client-Id": "a", "Lumenore-Client-Secret": "b"}) == 200

    # PUBLISH_API_TOKEN is a server-level credential: it must not be reachable
    # through a junk Authorization header.
    monkeypatch.setattr(config, "PUBLISH_API_TOKEN", "SERVERPUBTOKEN")
    assert config.has_credentials()
    assert status({"Host": "localhost:8080", "Authorization": "Basic x"}) == 401
    assert status({"Host": "localhost:8080"}) == 200


def test_bearer_for_request_never_upgrades_bad_credentials(monkeypatch):
    from config import config
    from core.file_upload_client import bearer_for_request

    _no_server_credentials(monkeypatch)
    monkeypatch.setattr(config, "PUBLISH_API_TOKEN", "SERVERPUBTOKEN")

    assert asyncio.run(bearer_for_request({"authorization": "Bearer user"})) == "Bearer user"
    assert asyncio.run(bearer_for_request({})) == "Bearer SERVERPUBTOKEN"
    for headers in (
        {"authorization": "Basic x"},
        {"authorization": "Bearer "},
        {"authorization": "bearerx"},
        {"lumenore-client-id": "only-half"},
    ):
        with pytest.raises(Exception, match="401"):
            asyncio.run(bearer_for_request(headers))


def test_server_credential_mode_validates_host_and_origin(monkeypatch):
    from config import config

    reached = []
    app = _router(monkeypatch, reached)
    _no_server_credentials(monkeypatch)
    monkeypatch.setattr(config, "TOKEN", "server-token")
    monkeypatch.setattr(config, "MCP_RESOURCE_URL", "https://mcp.example.com/mcp")
    monkeypatch.setattr(config, "ALLOWED_HOSTS", "")
    monkeypatch.setattr(config, "ALLOWED_ORIGINS", "")

    def status(headers):
        return _call_asgi(app, "/mcp", method="POST", headers=headers)[0]["status"]

    assert status({"Host": "evil.example", "Origin": "https://evil.example"}) == 403
    assert status({"Host": "evil.example"}) == 403
    assert status({}) == 403
    assert status({"Host": "localhost:8080", "Origin": "https://evil.example"}) == 403
    assert status({"Host": "localhost:8080", "Origin": "null"}) == 403
    assert status({"Host": "mcp.example.com.evil.example"}) == 403
    assert not reached
    assert status({"Host": "localhost:8080"}) == 200
    assert status({"Host": "127.0.0.1:8080", "Origin": "http://localhost:6274"}) == 200
    assert status({"Host": "[::1]:8080"}) == 200
    assert status({"Host": "mcp.example.com"}) == 200

    monkeypatch.setattr(config, "ALLOWED_HOSTS", "mcp-engine.internal")
    monkeypatch.setattr(config, "ALLOWED_ORIGINS", "https://app.example.com")
    assert status({"Host": "mcp-engine.internal:8080", "Origin": "https://app.example.com"}) == 200
    assert status({"Host": "mcp-engine.internal:8080", "Origin": "https://other.example.com"}) == 403

    # Without server-level credentials every request must carry its own
    # credentials, so Host/Origin are not what protects /mcp.
    _no_server_credentials(monkeypatch)
    assert status({"Host": "evil.example", "Authorization": "Bearer abc"}) == 200


def test_content_type_is_validated_and_commands_are_shell_quoted(monkeypatch):
    import shlex
    from config import config
    from tools import file_upload_tools as tools_module

    clean = tools_module._clean_content_type
    assert clean(None) == "application/octet-stream"
    assert clean("text/csv; charset=utf-8") == "text/csv"
    assert clean("application/vnd.ms-excel") == "application/vnd.ms-excel"
    for bad in ("text/csv'; touch /tmp/PWNED; echo '", "text/csv\nX: y", "text", "a/b c",
                "$(id)/x", "text/`id`"):
        with pytest.raises(Exception):
            clean(bad)

    signed = "https://publish.example.com/p?expires=1&signature=a'b;touch /tmp/PWNED"

    class FakeClient:
        bearer = "Bearer t"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def create_session(self, payload):
            return {"uploadId": "u1", "uploadUrl": signed,
                    "completeUrl": "https://publish.example.com/c?signature=s"}

    async def fake_client():
        return FakeClient()

    monkeypatch.setattr(tools_module, "_client", fake_client)
    monkeypatch.setattr(config, "PUBLISH_API_BASE_URL", "https://publish.example.com/api/publish")
    monkeypatch.setattr(config, "UPLOAD_PAGE_ALLOWED_HOSTS", "")
    monkeypatch.setattr(config, "ALLOWED_EXTENSIONS", "")

    create = getattr(tools_module.create_upload_link, "fn", tools_module.create_upload_link)
    with pytest.raises(Exception):
        asyncio.run(create("a.csv", 10, content_type="text/csv'; touch /tmp/PWNED; echo '"))

    result = asyncio.run(create("a.csv", 10, content_type="text/csv"))
    assert shlex.split(result["curl_command"]) == [
        "curl", "--fail-with-body", "--request", "PUT", "--header",
        "Content-Type: text/csv", "--upload-file", "/path/to/FILE", signed,
    ]
    # The page link carries the signed URLs only in the fragment.
    page, _, fragment = result["upload_page_url"].partition("#")
    assert "?" not in page and "signature" not in page
    assert "signature" in fragment


def test_upload_from_url_authenticates_before_downloading(monkeypatch):
    from config import config
    from tools import file_upload_tools as tools_module

    events = []

    class FakeClient:
        bearer = "Bearer garbage"
        valid = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def verify_bearer(self):
            events.append("verify")
            if not self.valid:
                raise tools_module.ToolError("401 Unauthorized")

    async def fake_client():
        return FakeClient()

    async def fake_download(source_url, file_obj):
        events.append("download")
        await asyncio.sleep(3600)

    monkeypatch.setattr(tools_module, "_client", fake_client)
    monkeypatch.setattr(tools_module, "_download_source", fake_download)
    monkeypatch.setattr(config, "ALLOWED_EXTENSIONS", "")
    upload = getattr(tools_module.upload_file_from_url, "fn", tools_module.upload_file_from_url)

    with pytest.raises(Exception, match="401"):
        asyncio.run(upload("https://files.example.org/big.bin", "big.bin"))
    assert events == ["verify"]  # nothing was resolved or fetched

    # Valid token: the download is bounded by a total deadline ...
    FakeClient.valid = True
    monkeypatch.setattr(config, "UPLOAD_FROM_URL_TIMEOUT_SECONDS", 0.05)
    with pytest.raises(Exception, match="did not finish"):
        asyncio.run(upload("https://files.example.org/big.bin", "big.bin"))
    assert tools_module._url_uploads_active == 0

    # ... and by a concurrency cap.
    monkeypatch.setattr(config, "UPLOAD_FROM_URL_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(config, "UPLOAD_FROM_URL_MAX_CONCURRENCY", 2)

    async def burst():
        return await asyncio.gather(
            *(upload("https://files.example.org/big.bin", "big.bin") for _ in range(5)),
            return_exceptions=True,
        )

    messages = [str(item) for item in asyncio.run(burst())]
    assert sum("Too many URL uploads" in m for m in messages) == 3
    assert sum("did not finish" in m for m in messages) == 2
    assert tools_module._url_uploads_active == 0


def test_client_credential_login_does_not_block_the_event_loop(monkeypatch):
    import time
    from core import lumenore_client
    from core.file_upload_client import bearer_for_request

    def slow_login(self):
        time.sleep(0.5)
        return "Bearer from-login"

    monkeypatch.setattr(lumenore_client.LumenoreAuthClient, "authenticate", slow_login)

    async def run():
        worst = 0.0

        async def ticker():
            nonlocal worst
            while True:
                before = time.perf_counter()
                await asyncio.sleep(0.01)
                worst = max(worst, time.perf_counter() - before)

        task = asyncio.create_task(ticker())
        bearer = await bearer_for_request(
            {"lumenore-client-id": "id", "lumenore-client-secret": "secret"}
        )
        task.cancel()
        return bearer, worst

    bearer, worst = asyncio.run(run())
    assert bearer == "Bearer from-login"
    assert worst < 0.25, f"event loop stalled for {worst:.2f}s during login"


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
