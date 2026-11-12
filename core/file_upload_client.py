"""Async client for publish-api's bearer + HMAC-presigned upload protocol."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

from config import config
from core.request_context import client_credentials, is_bearer
from utils.logger import get_logger

logger = get_logger("file_upload")

try:
    from mcp.server.fastmcp.exceptions import ToolError
except ImportError:  # fastmcp 3.x exposes the SDK under a different package.
    try:
        from fastmcp.exceptions import ToolError
    except ImportError:
        from fastmcp.exceptions import ValidationError as ToolError


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._() -]+")
_RETRYABLE = {429, 500, 502, 503, 504}
_EXPIRED_SIGNED_URL = {401, 403, 404, 410}


def sanitize_file_name(file_name: str) -> str:
    """Return a safe basename suitable for the upload session metadata."""
    if not isinstance(file_name, str):
        raise ToolError("file_name must be a string")
    name = file_name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    name = name.replace("..", "")
    name = "".join(ch for ch in name if ch.isprintable() and ch not in "\x00\r\n\t")
    name = _SAFE_NAME.sub("_", name).strip(" .")[:255]
    if not name:
        raise ToolError("file_name must contain a safe, non-empty file name")
    allowed = config.allowed_extensions
    if allowed and ("." not in name or name.rsplit(".", 1)[1].lower() not in allowed):
        raise ToolError(
            f"File extension is not allowed. Allowed extensions: {', '.join(sorted(allowed))}"
        )
    return name


def decode_content(content: str, encoding: str) -> bytes:
    if not isinstance(content, str) or not content:
        raise ToolError("content must be a non-empty text or base64 string")
    if encoding == "text":
        return content.encode("utf-8")
    if encoding != "base64":
        raise ToolError("encoding must be either 'text' or 'base64'")
    try:
        decoded = base64.b64decode(content, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ToolError(f"content is not valid base64: {exc}") from None
    if not decoded:
        raise ToolError("content must not decode to an empty file")
    return decoded


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict):
            for key in ("message", "error_description", "error", "status"):
                value = body.get(key)
                if value:
                    return str(value)[:500]
            data = body.get("data")
            if isinstance(data, dict) and data.get("message"):
                return str(data["message"])[:500]
        return response.text[:500]
    except Exception:
        return response.text[:500]


def _redacted_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


@dataclass
class _CachedUploadUrl:
    value: str
    token_key: str
    expires_at: float


class _UploadUrlCache:
    def __init__(self):
        self._values: dict[str, _CachedUploadUrl] = {}

    def get(self, upload_id: str, token_key: str) -> Optional[str]:
        item = self._values.get(upload_id)
        if item and item.token_key == token_key and item.expires_at > time.monotonic():
            return item.value
        return None

    def put(self, upload_id: str, value: str, token_key: str):
        self._values[upload_id] = _CachedUploadUrl(
            value=value,
            token_key=token_key,
            expires_at=time.monotonic() + config.UPLOAD_URL_CACHE_TTL_SECONDS,
        )

    def delete(self, upload_id: str):
        self._values.pop(upload_id, None)


_url_cache = _UploadUrlCache()


def _as_bearer(token: str) -> str:
    token = token.strip()
    return token if token.lower().startswith("bearer ") else f"Bearer {token}"


async def bearer_for_request(headers: dict[str, str]) -> str:
    """Resolve a bearer token for publish-api uploads.

    Order: the request's own Bearer token, then the request's Lumenore client
    credentials (exchanged for a bearer), then the server-level token.

    The server-level token is used only when the request carries no credentials
    at all. A request that presents credentials which are unusable (a non-Bearer
    Authorization header, or half a client-credential pair) is rejected instead
    of being silently upgraded to the server account.
    """
    headers = headers or {}
    auth = (headers.get("authorization") or "").strip()
    if auth:
        if is_bearer(auth):
            return auth
        raise ToolError("401 Unauthorized: the Authorization header must be a Bearer token.")

    client_id, client_secret = client_credentials(headers)
    if client_id or client_secret:
        if not (client_id and client_secret):
            raise ToolError(
                "401 Unauthorized: both Lumenore-Client-Id and "
                "Lumenore-Client-Secret headers are required."
            )
        from core.lumenore_client import LumenoreAuthClient

        auth_client = LumenoreAuthClient(
            client_id=client_id,
            secret=client_secret,
            base_url=config.SERVER_URL,
        )
        try:
            # authenticate() uses blocking `requests`; keep it off the event loop.
            return await asyncio.to_thread(auth_client.authenticate)
        except Exception as exc:
            raise ToolError(f"401 Unauthorized: Lumenore login failed ({exc})") from None

    if config.PUBLISH_API_TOKEN and config.PUBLISH_API_TOKEN.strip():
        return _as_bearer(config.PUBLISH_API_TOKEN)
    if config.TOKEN and config.TOKEN.strip():
        return _as_bearer(config.TOKEN)
    raise ToolError(
        "No bearer token is available for publish-api. Reconnect the MCP client "
        "or configure PUBLISH_API_TOKEN for a server-level integration."
    )


def _token_key(bearer: str) -> str:
    return hashlib.sha256(bearer.encode("utf-8")).hexdigest()


class FileUploadClient:
    def __init__(self, bearer: str):
        self.bearer = bearer
        self._token_key = _token_key(bearer)
        timeout = httpx.Timeout(60.0, connect=10.0)
        self._http = httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self._http.aclose()

    @property
    def _sessions_url(self) -> str:
        path = "/" + config.PUBLISH_API_SESSIONS_PATH.strip("/")
        return f"{config.upload_base_url}{path}"

    async def _api_request(self, method: str, url: str, *, json_body: Any = None,
                           retry: bool = False) -> dict[str, Any]:
        headers = {"Authorization": self.bearer}
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        attempts = 3 if retry else 1
        for attempt in range(attempts):
            try:
                response = await self._http.request(method, url, headers=headers, json=json_body)
            except httpx.HTTPError as exc:
                if attempt + 1 == attempts:
                    raise ToolError(f"publish-api network error: {exc}") from None
                await asyncio.sleep(0.25 * (2 ** attempt))
                continue
            if response.status_code in _RETRYABLE and attempt + 1 < attempts:
                await asyncio.sleep(0.25 * (2 ** attempt))
                continue
            if response.status_code < 200 or response.status_code >= 300:
                raise ToolError(
                    f"publish-api {method} {urlsplit(url).path} failed "
                    f"with HTTP {response.status_code}: {_error_message(response)}"
                )
            try:
                body = response.json()
            except json.JSONDecodeError:
                raise ToolError("publish-api returned a non-JSON response") from None
            if not isinstance(body, dict):
                raise ToolError("publish-api returned an invalid response envelope")
            return body
        raise ToolError("publish-api request failed after retries")

    @staticmethod
    def _data(body: dict[str, Any]) -> dict[str, Any]:
        data = body.get("data")
        if not isinstance(data, dict):
            raise ToolError("publish-api response did not contain a data object")
        return data

    async def verify_bearer(self) -> None:
        """Make one cheap authenticated call so costly work never starts for a bad token.

        publish-api authenticates before it looks the session up, so a random
        session id returns 404 for a valid bearer and 401 for an invalid one.
        Anything else fails closed.
        """
        url = f"{self._sessions_url}/{uuid.uuid4()}"
        try:
            response = await self._http.get(url, headers={"Authorization": self.bearer})
        except httpx.HTTPError as exc:
            raise ToolError(f"publish-api network error: {type(exc).__name__}") from None
        if response.status_code == 404 or 200 <= response.status_code < 300:
            return
        if response.status_code in (401, 403):
            raise ToolError("401 Unauthorized: publish-api rejected the bearer token.")
        raise ToolError(
            f"publish-api credential check failed with HTTP {response.status_code}"
        )

    async def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._data(await self._api_request("POST", self._sessions_url, json_body=payload))

    async def status(self, upload_id: str) -> dict[str, Any]:
        return self._data(await self._api_request("GET", f"{self._sessions_url}/{quote(upload_id, safe='')}" , retry=True))

    async def presign(self, upload_id: str) -> str:
        body = await self._api_request(
            "POST", f"{self._sessions_url}/{quote(upload_id, safe='')}/presign", retry=True
        )
        data = self._data(body)
        url = data.get("uploadUrl") or data.get("uploadUrlTemplate")
        if not isinstance(url, str) or not url:
            raise ToolError("publish-api presign response did not contain an upload URL")
        _url_cache.put(upload_id, url, self._token_key)
        return url

    async def signed_put(self, url: str, content: bytes) -> httpx.Response:
        attempts = 3
        for attempt in range(attempts):
            try:
                response = await self._http.put(
                    url,
                    content=content,
                    headers={"Content-Type": "application/octet-stream"},
                )
            except httpx.HTTPError as exc:
                if attempt + 1 == attempts:
                    raise ToolError(f"signed upload network error: {exc}") from None
                await asyncio.sleep(0.25 * (2 ** attempt))
                continue
            if response.status_code in _RETRYABLE and attempt + 1 < attempts:
                await asyncio.sleep(0.25 * (2 ** attempt))
                continue
            return response
        raise ToolError("signed upload failed after retries")

    async def upload_bytes(self, upload_id: str, content: bytes, chunk_number: Optional[int] = None):
        url = _url_cache.get(upload_id, self._token_key) or await self.presign(upload_id)
        if chunk_number is not None:
            if "{chunkNumber}" not in url:
                raise ToolError("publish-api did not return a chunk upload URL template")
            url = url.replace("{chunkNumber}", quote(str(chunk_number), safe=""))
        response = await self.signed_put(url, content)
        if response.status_code in _EXPIRED_SIGNED_URL:
            _url_cache.delete(upload_id)
            url = await self.presign(upload_id)
            if chunk_number is not None:
                url = url.replace("{chunkNumber}", quote(str(chunk_number), safe=""))
            response = await self.signed_put(url, content)
        if chunk_number is None:
            expected = {202}
        else:
            expected = {200, 202}
        if response.status_code not in expected:
            raise ToolError(
                f"signed upload failed with HTTP {response.status_code}: "
                f"{_error_message(response)}"
            )
        try:
            return response.json().get("data", {})
        except json.JSONDecodeError:
            return {}

    async def complete(self, upload_id: str) -> dict[str, Any]:
        body = await self._api_request(
            "POST", f"{self._sessions_url}/{quote(upload_id, safe='')}/complete"
        )
        return self._data(body)

    async def abort(self, upload_id: str) -> dict[str, Any]:
        body = await self._api_request(
            "DELETE", f"{self._sessions_url}/{quote(upload_id, safe='')}"
        )
        _url_cache.delete(upload_id)
        return self._data(body)


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
