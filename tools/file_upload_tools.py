"""MCP tools for direct and chunked publish-api file uploads."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import math
import re
import shlex
import socket
import tempfile
from typing import Optional
from urllib.parse import urlsplit, urlencode

import httpx

from mcp_instance import mcp
from core.file_upload_client import (
    FileUploadClient,
    ToolError,
    bearer_for_request,
    decode_content,
    sanitize_file_name,
    sha256_hex,
)
from core.request_context import get_request_headers
from config import config


async def _client() -> FileUploadClient:
    return FileUploadClient(await bearer_for_request(get_request_headers()))


_DEFAULT_CONTENT_TYPE = "application/octet-stream"
_CONTENT_TYPE = re.compile(r"[\w.+-]+/[\w.+-]+", re.ASCII)


def _clean_content_type(content_type: Optional[str]) -> str:
    """Return a bare ``type/subtype`` or raise.

    content_type is model-controlled and ends up in shell commands and the
    upload page, so only the plain media type is accepted (parameters such as
    ``; charset=utf-8`` are dropped).
    """
    if content_type is None or not str(content_type).strip():
        return _DEFAULT_CONTENT_TYPE
    value = str(content_type).split(";", 1)[0].strip()
    if len(value) > 127 or not _CONTENT_TYPE.fullmatch(value):
        raise ToolError("content_type must be a media type such as text/csv")
    return value


# In-flight upload_file_from_url downloads (single event loop, so a plain counter).
_url_uploads_active = 0


def _check_total(size: int):
    if size <= 0:
        raise ToolError("total_size must be greater than zero")
    if size > config.MAX_TOTAL_BYTES:
        raise ToolError(f"total_size exceeds MAX_TOTAL_BYTES ({config.MAX_TOTAL_BYTES} bytes)")


def _check_upload_id(upload_id: str):
    if not isinstance(upload_id, str) or not upload_id.strip():
        raise ToolError("upload_id must be a non-empty string")


def _resolve_destination(destination: Optional[str]) -> str:
    value = (destination or config.DEFAULT_UPLOAD_DESTINATION or "").strip()
    if not value:
        value = "Lumenore"
    if len(value) > 200 or any(ord(char) < 32 for char in value):
        raise ToolError("destination must be a printable value of at most 200 characters")
    return value


def _using_proxy() -> bool:
    import os
    return any(os.getenv(name) for name in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"))


def _upload_page_base() -> str:
    if config.UPLOAD_PAGE_BASE_URL:
        return config.UPLOAD_PAGE_BASE_URL.rstrip("/")
    resource = config.MCP_RESOURCE_URL.rstrip("/")
    base = resource[:-4] if resource.endswith("/mcp") else resource
    return f"{base}/upload"


def _host_allowed(host: str, allowed: set[str]) -> bool:
    host = host.lower().rstrip(".")
    return any(host == item or host.endswith("." + item) for item in allowed)


def _is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


async def _validate_source_url(source_url: str) -> str:
    """Allow only public HTTPS download URLs for server-side relay uploads.

    Blocks loopback, private, link-local (cloud metadata) and other
    non-public addresses so the tool cannot be used for SSRF against the
    server's internal network. ALLOWED_SOURCE_URL_HOSTS narrows it further.
    """
    if not isinstance(source_url, str) or not source_url.strip():
        raise ToolError("source_url must be a non-empty URL")
    source_url = source_url.strip()
    parsed = urlsplit(source_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ToolError("source_url must be an HTTPS URL without embedded credentials")
    try:
        port = parsed.port or 443
    except ValueError:
        raise ToolError("source_url has an invalid port") from None
    host = parsed.hostname
    allowed = config.allowed_source_url_hosts
    if allowed and not _host_allowed(host, allowed):
        raise ToolError("source_url host is not allowed")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            host, port, type=socket.SOCK_STREAM
        )
    except socket.gaierror:
        raise ToolError("source_url host could not be resolved") from None
    addresses = {info[4][0] for info in infos}
    if not addresses or not all(_is_public_ip(addr) for addr in addresses):
        raise ToolError("source_url must point to a public internet address")
    return source_url


def _check_connected_peer(response) -> None:
    """Re-check the connected address to defeat DNS rebinding (direct connections only)."""
    stream = response.extensions.get("network_stream")
    if stream is None:
        return
    try:
        peer = stream.get_extra_info("server_addr")
    except Exception:
        return
    if peer and not _is_public_ip(str(peer[0])):
        raise ToolError("source_url must point to a public internet address")


async def _upload_spooled_file(client: FileUploadClient, file_obj, file_name: str,
                               total_size: int, content_type: str,
                               destination: str, digest: str):
    """Create a publish session and stream a server-side file object in chunks."""
    total_chunks = math.ceil(total_size / config.MAX_CHUNK_BYTES)
    session = await client.create_session({
        "fileName": file_name,
        "size": total_size,
        "mode": "CHUNKED",
        "totalChunks": total_chunks,
        "contentType": content_type,
        "sha256": digest,
    })
    upload_id = session.get("uploadId")
    template = session.get("uploadUrlTemplate")
    if not upload_id or not template:
        raise ToolError("publish-api did not return uploadId and uploadUrlTemplate for CHUNKED mode")
    from core.file_upload_client import _url_cache, _token_key
    _url_cache.put(upload_id, template, _token_key(client.bearer))

    try:
        file_obj.seek(0)
        for chunk_number in range(total_chunks):
            data = file_obj.read(config.MAX_CHUNK_BYTES)
            if not data:
                raise ToolError("source file ended before the declared upload size")
            await client.upload_bytes(upload_id, data, chunk_number + config.CHUNK_NUMBER_START)
        completed = await client.complete(upload_id)
    except Exception:
        try:
            await client.abort(upload_id)
        except Exception:
            pass
        raise
    return {
        "file_name": file_name,
        "unique_file_name": completed.get("uniqueFileName"),
        "destination": destination,
        "size": total_size,
        "sha256": digest,
        "upload_id": upload_id,
        "total_chunks": total_chunks,
    }


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "title": "Upload File"})
async def upload_file(file_name: str, content: str, encoding: str = "text",
                      content_type: Optional[str] = None, destination: Optional[str] = None):
    """Upload a small file to the requested Lumenore destination.

    A missing destination means the standard Lumenore file storage.
    """
    resolved_destination = _resolve_destination(destination)
    data = decode_content(content, encoding)
    if len(data) > config.MAX_INLINE_BYTES:
        raise ToolError(
            f"Inline content is {len(data)} bytes, above MAX_INLINE_BYTES={config.MAX_INLINE_BYTES}. "
            "Use start_chunked_upload and upload_chunk instead."
        )
    safe_name = sanitize_file_name(file_name)
    resolved_type = _clean_content_type(content_type)
    digest = sha256_hex(data)
    async with await _client() as client:
        session = await client.create_session({
            "fileName": safe_name,
            "size": len(data),
            "mode": "DIRECT",
            "contentType": resolved_type,
            "sha256": digest,
        })
        upload_id = session.get("uploadId")
        upload_url = session.get("uploadUrl")
        if not upload_id or not upload_url:
            raise ToolError("publish-api did not return uploadId and uploadUrl for DIRECT mode")
        # Seed the cache with the session URL; signed PUT has no bearer header.
        from core.file_upload_client import _url_cache, _token_key
        _url_cache.put(upload_id, upload_url, _token_key(client.bearer))
        await client.upload_bytes(upload_id, data)
        completed = await client.complete(upload_id)
    return {"file_name": safe_name, "unique_file_name": completed.get("uniqueFileName"),
            "destination": resolved_destination, "size": len(data), "sha256": digest,
            "upload_id": upload_id}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False,
                        "title": "Create Upload Link"})
async def create_upload_link(file_name: str, total_size: int,
                             content_type: Optional[str] = None,
                             sha256: Optional[str] = None,
                             destination: Optional[str] = None,
                             max_size_bytes: Optional[int] = None):
    """Create a short-lived browser upload page for the original file.

    The returned upload_page_url lets the user upload directly from their
    browser, so file bytes do not pass through the MCP client or model.
    """
    resolved_destination = _resolve_destination(destination)
    _check_total(total_size)
    if max_size_bytes is not None and (max_size_bytes <= 0 or total_size > max_size_bytes):
        raise ToolError("file size exceeds max_size_bytes")
    safe_name = sanitize_file_name(file_name)
    resolved_type = _clean_content_type(content_type)
    async with await _client() as client:
        session = await client.create_session({
            "fileName": safe_name,
            "size": total_size,
            "mode": "DIRECT",
            "contentType": resolved_type,
            **({"sha256": sha256} if sha256 else {}),
        })
        upload_id = session.get("uploadId")
        upload_url = session.get("uploadUrl")
        if not upload_id or not upload_url:
            raise ToolError("publish-api did not return a direct upload URL")
        complete_url = session.get("completeUrl")
        if not complete_url:
            raise ToolError("publish-api did not return a signed completion URL")
        allowed = config.upload_page_allowed_hosts
        for signed_url in (upload_url, complete_url):
            parts = urlsplit(signed_url)
            if parts.scheme != "https" or not _host_allowed(parts.hostname or "", allowed):
                raise ToolError(
                    "publish-api returned an upload URL on a host that is not in "
                    "UPLOAD_PAGE_ALLOWED_HOSTS"
                )
    page_query = urlencode({
        "put": upload_url,
        "complete": complete_url,
        "name": safe_name,
        "type": resolved_type,
        "size": str(total_size),
    })
    return {
        "upload_id": upload_id,
        # Signed URLs travel in the fragment: browsers never send it to a server,
        # so it stays out of access logs, proxies and Referer headers.
        "upload_page_url": f"{_upload_page_base()}#{page_query}",
        "upload_url": upload_url,
        "complete_url": complete_url,
        "expires_at": session.get("expiresAt"),
        "file_name": safe_name,
        "size": total_size,
        "curl_command": (
            "curl --fail-with-body --request PUT "
            "--header " + shlex.quote("Content-Type: " + resolved_type) + " "
            "--upload-file '/path/to/FILE' " + shlex.quote(upload_url)
        ),
        "next_step": "Open upload_page_url and choose the original file. The page uploads and completes it automatically. The curl command is an optional technical fallback.",
        "destination": resolved_destination,
    }


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False,
                        "title": "Upload File From URL"})
async def upload_file_from_url(source_url: str, file_name: str,
                               content_type: Optional[str] = None,
                               destination: Optional[str] = None):
    """Download a file on the MCP server and upload it to Lumenore.

    This is intended for clients that can provide a temporary HTTPS download URL
    for an attachment. File bytes never pass through the model or MCP JSON.
    """
    global _url_uploads_active
    # Cheap local validation first; nothing below touches the network.
    if not isinstance(source_url, str) or not source_url.strip():
        raise ToolError("source_url must be a non-empty URL")
    resolved_destination = _resolve_destination(destination)
    safe_name = sanitize_file_name(file_name)
    requested_type = _clean_content_type(content_type) if content_type else None

    async with await _client() as client:
        # Prove the caller's token to publish-api before the server resolves
        # or fetches anything on their behalf.
        await client.verify_bearer()
        if _url_uploads_active >= config.UPLOAD_FROM_URL_MAX_CONCURRENCY:
            raise ToolError(
                "Too many URL uploads are in progress on this server. Retry shortly."
            )
        _url_uploads_active += 1
        try:
            with tempfile.SpooledTemporaryFile(max_size=config.MAX_INLINE_BYTES,
                                                mode="w+b") as file_obj:
                deadline = config.UPLOAD_FROM_URL_TIMEOUT_SECONDS
                try:
                    total_size, digest, response_type = await asyncio.wait_for(
                        _download_source(source_url, file_obj), timeout=deadline
                    )
                except asyncio.TimeoutError:
                    raise ToolError(
                        f"source download did not finish within {deadline} seconds"
                    ) from None
                except ToolError:
                    raise
                except Exception as exc:
                    raise ToolError(f"source download failed ({type(exc).__name__})") from None
                if requested_type:
                    resolved_type = requested_type
                else:
                    try:
                        resolved_type = _clean_content_type(response_type)
                    except ToolError:
                        resolved_type = _DEFAULT_CONTENT_TYPE
                return await _upload_spooled_file(
                    client, file_obj, safe_name, total_size, resolved_type,
                    resolved_destination, digest,
                )
        finally:
            _url_uploads_active -= 1


async def _download_source(source_url: str, file_obj):
    """Validate and download source_url into file_obj; returns (size, sha256, content type)."""
    source_url = await _validate_source_url(source_url)
    max_bytes = config.MAX_TOTAL_BYTES
    # A separate client that never forwards credentials or follows redirects.
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0),
                                 follow_redirects=False) as downloader, \
            downloader.stream("GET", source_url) as response:
        if not _using_proxy():
            _check_connected_peer(response)
        if response.status_code < 200 or response.status_code >= 300:
            raise ToolError(f"source download failed with HTTP {response.status_code}")
        declared_size = response.headers.get("content-length")
        if declared_size and declared_size.isdigit() and int(declared_size) > max_bytes:
            raise ToolError(f"source file exceeds MAX_TOTAL_BYTES ({max_bytes} bytes)")
        response_type = response.headers.get("content-type", "")
        digest = hashlib.sha256()
        total_size = 0
        async for data in response.aiter_bytes(config.MAX_CHUNK_BYTES):
            total_size += len(data)
            if total_size > max_bytes:
                raise ToolError(f"source file exceeds MAX_TOTAL_BYTES ({max_bytes} bytes)")
            digest.update(data)
            file_obj.write(data)
        if total_size == 0:
            raise ToolError("source URL returned an empty file")
        return total_size, digest.hexdigest(), response_type


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "title": "Start Chunked Upload"})
async def start_chunked_upload(file_name: str, total_size: int, total_chunks: int,
                               content_type: str, sha256: Optional[str] = None,
                               destination: Optional[str] = None):
    """Create a chunked session for standard Lumenore file storage."""
    resolved_destination = _resolve_destination(destination)
    _check_total(total_size)
    if total_chunks < 1:
        raise ToolError("total_chunks must be at least 1")
    if total_size > total_chunks * config.MAX_CHUNK_BYTES:
        raise ToolError(
            f"total_chunks is too small for MAX_CHUNK_BYTES={config.MAX_CHUNK_BYTES}; "
            f"use at least {math.ceil(total_size / config.MAX_CHUNK_BYTES)} chunks"
        )
    safe_name = sanitize_file_name(file_name)
    resolved_type = _clean_content_type(content_type)
    async with await _client() as client:
        session = await client.create_session({
            "fileName": safe_name, "size": total_size, "mode": "CHUNKED",
            "totalChunks": total_chunks, "contentType": resolved_type,
            **({"sha256": sha256} if sha256 else {}),
        })
        upload_id = session.get("uploadId")
        template = session.get("uploadUrlTemplate")
        if not upload_id or not template:
            raise ToolError("publish-api did not return uploadId and uploadUrlTemplate for CHUNKED mode")
        from core.file_upload_client import _url_cache, _token_key
        _url_cache.put(upload_id, template, _token_key(client.bearer))
    return {"upload_id": upload_id, "max_chunk_bytes": config.MAX_CHUNK_BYTES,
            "total_chunks": total_chunks, "chunk_number_start": config.CHUNK_NUMBER_START,
            "destination": resolved_destination}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "title": "Upload File Chunk"})
async def upload_chunk(upload_id: str, chunk_number: int, data_base64: str):
    """Upload one strict-base64 chunk; repeating the same chunk is safe."""
    _check_upload_id(upload_id)
    if chunk_number < config.CHUNK_NUMBER_START:
        raise ToolError(f"chunk_number must be >= {config.CHUNK_NUMBER_START}")
    data = decode_content(data_base64, "base64")
    if len(data) > config.MAX_CHUNK_BYTES:
        raise ToolError(f"Chunk is too large; maximum raw chunk size is {config.MAX_CHUNK_BYTES} bytes")
    async with await _client() as client:
        progress = await client.upload_bytes(upload_id, data, chunk_number)
    return {"upload_id": upload_id, "chunk_number": chunk_number,
            "received_chunks": progress.get("receivedChunks"),
            "total_chunks": progress.get("totalChunks"),
            "ready_to_complete": progress.get("readyToComplete")}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "title": "Get Upload Status"})
async def get_upload_status(upload_id: str):
    """Get progress and ownership-checked status for an upload session."""
    _check_upload_id(upload_id)
    async with await _client() as client:
        return await client.status(upload_id)


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "title": "Complete Upload"})
async def complete_upload(upload_id: str):
    """Complete a direct upload or merge a chunked upload."""
    _check_upload_id(upload_id)
    async with await _client() as client:
        return await client.complete(upload_id)


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "title": "Abort Upload"})
async def abort_upload(upload_id: str):
    """Abort an upload session and invalidate its cached signed URL."""
    _check_upload_id(upload_id)
    async with await _client() as client:
        return await client.abort(upload_id)


if config.ENABLE_HANDOFF_TOOLS:
    @mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "title": "Create Direct Upload Handoff"})
    async def create_direct_upload_session(file_name: str, total_size: int, content_type: str,
                                           sha256: Optional[str] = None,
                                           destination: Optional[str] = None):
        """Create a direct session for clients that upload bytes outside MCP."""
        resolved_destination = _resolve_destination(destination)
        _check_total(total_size)
        safe_name = sanitize_file_name(file_name)
        resolved_type = _clean_content_type(content_type)
        async with await _client() as client:
            session = await client.create_session({"fileName": safe_name, "size": total_size,
                "mode": "DIRECT", "contentType": resolved_type, **({"sha256": sha256} if sha256 else {})})
        url = session.get("uploadUrl")
        if not session.get("uploadId") or not isinstance(url, str) or not url:
            raise ToolError("publish-api did not return a direct upload handoff")
        return {"upload_id": session.get("uploadId"), "upload_url": url,
                "destination": resolved_destination,
                "curl": ("curl --fail-with-body -X PUT -H 'Content-Type: application/octet-stream' "
                         "--data-binary @FILE " + shlex.quote(url))}

    @mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "title": "Create Chunked Upload Handoff"})
    async def create_chunked_upload_session(file_name: str, total_size: int, total_chunks: int,
                                            content_type: str, sha256: Optional[str] = None,
                                            destination: Optional[str] = None):
        """Create a chunked session and return a shell-loop handoff."""
        resolved_destination = _resolve_destination(destination)
        _check_total(total_size)
        safe_name = sanitize_file_name(file_name)
        resolved_type = _clean_content_type(content_type)
        async with await _client() as client:
            session = await client.create_session({"fileName": safe_name, "size": total_size,
                "mode": "CHUNKED", "totalChunks": total_chunks, "contentType": resolved_type,
                **({"sha256": sha256} if sha256 else {})})
        template = session.get("uploadUrlTemplate")
        if not session.get("uploadId") or not isinstance(template, str) or not template:
            raise ToolError("publish-api did not return a chunk upload handoff")
        # Quote the URL pieces literally and leave only "$n" for the shell to expand.
        shell_url = '"$n"'.join(shlex.quote(part) if part else ""
                                for part in template.split("{chunkNumber}"))
        return {"upload_id": session["uploadId"], "upload_url_template": template,
                "destination": resolved_destination,
                "max_chunk_bytes": config.MAX_CHUNK_BYTES,
                "shell_example": (
                    "for n in $(seq " + str(config.CHUNK_NUMBER_START) + " $((TOTAL_CHUNKS-1))); do "
                    "curl --fail-with-body -X PUT -H 'Content-Type: application/octet-stream' "
                    "--data-binary \"@chunk-$n\" " + shell_url + "; done"
                )}

    @mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "title": "Refresh Upload URL"})
    async def refresh_upload_url(upload_id: str):
        """Refresh and return the signed upload URL or URL template."""
        _check_upload_id(upload_id)
        async with await _client() as client:
            url = await client.presign(upload_id)
        return {"upload_id": upload_id, "upload_url": url}

