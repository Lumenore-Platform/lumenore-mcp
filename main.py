import warnings
import sys
import logging
import json
import base64
import hashlib
from urllib.parse import parse_qs, urlsplit

import tools
import asyncio
from mcp_instance import mcp
from utils.logger import get_logger
from config import config

# Suppress all deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

__title__ = "FastMCP and Python3.13 for building massively scalable Lumenore MCP tools"

# Get centralized logger
logger = get_logger()


class HealthCheckFilter(logging.Filter):
    """Filter out health check requests from access logs."""
    def filter(self, record):
        msg = record.getMessage()
        return not any(x in msg for x in ['/health', '/ready', '/live', '/healthz', '/readiness', '/liveness'])


async def cleanup():
    """Cleanup resources on shutdown."""
    logger.info("Cleaning up resources...")
    try:
        from core.lumenore_analytics import cleanup_lumenore_client

        await cleanup_lumenore_client()
        logger.info("HTTP client session closed successfully")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


HEALTH_ENDPOINTS = ['/health', '/healthz', '/ready', '/readiness', '/live', '/liveness']

UPLOAD_PAGE_STYLE = r'''
body{font:16px system-ui,-apple-system,sans-serif;background:#eef1f6;color:#172033;margin:0;padding:32px;display:grid;place-items:center;min-height:100vh}
main{background:#fff;border-radius:14px;padding:28px;max-width:560px;width:100%;box-shadow:0 8px 30px #17203318}h1{margin-top:0;font-size:1.5rem}
#drop{border:2px dashed #c9d0dd;border-radius:12px;padding:48px 20px;text-align:center;cursor:pointer}#drop.drag{border-color:#2c4fd6;background:#dbe3ff}
button{border:0;border-radius:8px;padding:10px 16px;background:#2c4fd6;color:white;font-size:1rem;cursor:pointer;margin-top:16px}button:disabled{opacity:.5}
progress{width:100%;margin-top:20px}#status{margin-top:14px;white-space:pre-wrap}.ok{color:#17794f}.err{color:#b42a22}small{color:#5a6478}
'''

UPLOAD_PAGE_SCRIPT = r'''
(()=>{const q=new URLSearchParams(location.search), put=q.get('put'), complete=q.get('complete'), name=q.get('name'), type=q.get('type')||'application/octet-stream', expected=Number(q.get('size')||0), picker=document.getElementById('picker'), drop=document.getElementById('drop'), button=document.getElementById('upload'), progress=document.getElementById('progress'), status=document.getElementById('status');
document.getElementById('details').textContent=`Choose ${name||'the file'} (${expected.toLocaleString()} bytes).`;
const choose=()=>picker.click(); drop.onclick=choose; drop.onkeydown=e=>{if(e.key==='Enter'||e.key===' ')choose()}; drop.ondragover=e=>{e.preventDefault();drop.classList.add('drag')}; drop.ondragleave=()=>drop.classList.remove('drag'); drop.ondrop=e=>{e.preventDefault();drop.classList.remove('drag');picker.files=e.dataTransfer.files;picker.dispatchEvent(new Event('change'))};
picker.onchange=()=>{const f=picker.files[0]; const valid=f&&(!expected||f.size===expected); button.disabled=!valid; status.className=valid?'':'err'; status.textContent=f&&!valid?`Choose a file with the expected size (${expected.toLocaleString()} bytes). Selected file: ${f.size.toLocaleString()} bytes.`:''};
button.onclick=()=>{const f=picker.files[0];button.disabled=true;progress.hidden=false;status.className='';status.textContent='Uploading...';const xhr=new XMLHttpRequest();xhr.open('PUT',put);xhr.setRequestHeader('Content-Type',type);xhr.upload.onprogress=e=>{if(e.lengthComputable){progress.value=e.loaded/e.total*100;status.textContent=`Uploading ${Math.round(progress.value)}%`}};xhr.onerror=()=>{status.className='err';status.textContent='Upload failed. You can retry this page.';button.disabled=false};xhr.onload=async()=>{if(xhr.status<200||xhr.status>=300){status.className='err';status.textContent=`Upload failed (HTTP ${xhr.status}).`;button.disabled=false;return}status.textContent='File received. Finalizing in Lumenore...';try{const done=await fetch(complete,{method:'POST'});if(!done.ok)throw new Error(`HTTP ${done.status}`);status.className='ok';status.textContent='Upload complete. You can close this page.';progress.value=100}catch(e){status.className='err';status.textContent='File bytes uploaded, but completion failed: '+e.message+'. Return to Claude to retry completion.';button.disabled=false}};xhr.send(f)};
})();'''

UPLOAD_PAGE_HTML = (r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Upload to Lumenore</title>
<style>''' + UPLOAD_PAGE_STYLE + r'''</style></head><body><main><h1>Upload a file to Lumenore</h1><p id="details"></p>
<div id="drop" tabindex="0">Drop the file here or click to choose it<input id="picker" type="file" hidden></div>
<button id="upload" disabled>Upload file</button><progress id="progress" max="100" value="0" hidden></progress><div id="status" role="status"></div><small id="expiry"></small></main>
<script>''' + UPLOAD_PAGE_SCRIPT + r'''</script></body></html>''')

def _csp_hash(source):
    digest = hashlib.sha256(source.encode("utf-8")).digest()
    return "'sha256-" + base64.b64encode(digest).decode("ascii") + "'"


def _upload_page_headers(connect_origins):
    """Strict headers: inline code pinned by hash, no framing, no referrer (signed URLs are in the query)."""
    csp = (
        "default-src 'none'; "
        f"script-src {_csp_hash(UPLOAD_PAGE_SCRIPT)}; "
        f"style-src {_csp_hash(UPLOAD_PAGE_STYLE)}; "
        f"connect-src {' '.join(sorted(connect_origins))}; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )
    return [
        (b"content-security-policy", csp.encode("latin-1")),
        (b"referrer-policy", b"no-referrer"),
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"cross-origin-opener-policy", b"same-origin"),
    ]


def _signed_url_allowed(url):
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().rstrip(".")
    if parts.scheme != "https" or not host or parts.username or parts.password:
        return False
    return any(host == item or host.endswith("." + item) for item in config.upload_page_allowed_hosts)



def _asgi_json_response(status_code, payload, headers=None):
    """Build a small ASGI response without adding another web framework."""
    body = json.dumps(payload).encode("utf-8")
    response_headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    if headers:
        response_headers.extend(
            (name.lower().encode("latin-1"), value.encode("latin-1"))
            for name, value in headers.items()
        )
    return status_code, response_headers, body


def _metadata_url():
    """Return the metadata URL next to the configured /mcp resource path."""
    resource_url = config.MCP_RESOURCE_URL.rstrip("/")
    if resource_url.endswith("/mcp"):
        resource_url = resource_url[:-len("/mcp")]
    return f"{resource_url}/.well-known/oauth-protected-resource/mcp"


def create_smart_router(mcp_app):
    """
    Build the ASGI app that routes health probes and (optionally) strips BASE_PATH
    before delegating to the FastMCP app.

    Extracted from the __main__ block so the routing logic is importable/testable.
    """
    from health_endpoint import health, readiness, liveness

    async def _dispatch_health(sub_path):
        if sub_path in ['/health', '/healthz']:
            return await health(None)
        if sub_path in ['/ready', '/readiness']:
            return await readiness(None)
        return await liveness(None)

    async def smart_router(scope, receive, send):
        """Route requests based on BASE_PATH configuration."""
        if scope["type"] == "http":
            path = scope["path"]
            base_path = config.BASE_PATH or ""
            sub_path = path

            if base_path:
                # BASE_PATH configured: ONLY accept paths WITH prefix.
                # Match on segment boundary so e.g. /bridge/lumenore-mcp-evil
                # does not match BASE_PATH=/bridge/lumenore-mcp.
                if path == base_path or path.startswith(base_path + "/"):
                    sub_path = path[len(base_path):] or "/"

                    if sub_path in HEALTH_ENDPOINTS:
                        response = await _dispatch_health(sub_path)
                        return await response(scope, receive, send)

                    # MCP endpoints - strip prefix
                    scope["path"] = sub_path
            else:
                # No BASE_PATH: respond to root paths only
                if path in HEALTH_ENDPOINTS:
                    response = await _dispatch_health(path)
                    return await response(scope, receive, send)

            if sub_path == "/upload" and scope["method"] == "GET":
                query = parse_qs(scope.get("query_string", b"").decode("utf-8"), keep_blank_values=False)
                required = ("put", "complete", "name", "type", "size")
                put_url = query.get("put", [""])[0]
                complete_url = query.get("complete", [""])[0]
                size = query.get("size", [""])[0]
                if (any(not query.get(key, [""])[0] for key in required)
                        or not _signed_url_allowed(put_url)
                        or not _signed_url_allowed(complete_url)
                        or not size.isdigit() or int(size) <= 0
                        or int(size) > config.MAX_TOTAL_BYTES):
                    status, response_headers, response_body = _asgi_json_response(
                        400, {"error": "upload page requires a valid signed upload session"}
                    )
                    await send({"type": "http.response.start", "status": status, "headers": response_headers})
                    await send({"type": "http.response.body", "body": response_body})
                    return
                body = UPLOAD_PAGE_HTML.encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (b"content-type", b"text/html; charset=utf-8"),
                        (b"content-length", str(len(body)).encode("ascii")),
                        (b"cache-control", b"no-store"),
                        *_upload_page_headers({
                            f"https://{urlsplit(put_url).netloc}",
                            f"https://{urlsplit(complete_url).netloc}",
                        }),
                    ],
                })
                await send({"type": "http.response.body", "body": body})
                return

            # MCP clients discover the authorization server from protected
            # resource metadata before starting OAuth.
            if scope["method"] == "GET" and sub_path in (
                "/.well-known/oauth-protected-resource",
                "/.well-known/oauth-protected-resource/mcp",
            ):
                status, response_headers, body = _asgi_json_response(
                    200,
                    {
                        "resource": config.MCP_RESOURCE_URL,
                        "authorization_servers": [config.AUTHORIZATION_SERVER_ISSUER],
                        "scopes_supported": config.mcp_scopes,
                        "bearer_methods_supported": ["header"],
                    },
                )
                await send({
                    "type": "http.response.start",
                    "status": status,
                    "headers": response_headers,
                })
                await send({"type": "http.response.body", "body": body})
                return

            # Keep the existing server-level credential mode working, but
            # require a bearer token for externally authenticated requests.
            # The gateway exchanges the MCP token and forwards that bearer.
            if sub_path == "/mcp" or sub_path.startswith("/mcp/"):
                headers = {
                    key.decode("latin-1").lower(): value.decode("latin-1")
                    for key, value in scope.get("headers", [])
                }
                if not headers.get("authorization") and not config.has_credentials():
                    metadata_url = _metadata_url()
                    status, response_headers, body = _asgi_json_response(
                        401,
                        {"error": "unauthorized", "error_description": "Bearer token required"},
                        {"WWW-Authenticate": f'Bearer resource_metadata="{metadata_url}"'},
                    )
                    await send({
                        "type": "http.response.start",
                        "status": status,
                        "headers": response_headers,
                    })
                    await send({"type": "http.response.body", "body": body})
                    return

        return await mcp_app(scope, receive, send)

    return smart_router


if __name__ == "__main__":
    # uvicorn installs its own SIGINT/SIGTERM handlers; cleanup runs after it exits.
    logger.info("Starting Lumenore Analytics MCP Server...")
    logger.info(f"Server configuration: transport=streamable-http, host=0.0.0.0, port=8080")

    try:
        import uvicorn
        from utils.timeout_config import TimeoutConfig

        # Get server timeout settings
        timeout_settings = TimeoutConfig.get_timeout_settings()

        # Log current configuration
        TimeoutConfig.log_settings(logger)

        logger.info(f"Starting MCP server with {timeout_settings['total_timeout']}s timeout")

        # Get FastMCP's ASGI app, wrapped in the BASE_PATH-aware router
        mcp_app = mcp.http_app()
        app = create_smart_router(mcp_app)
        
        # Log endpoints
        if config.BASE_PATH:
            logger.info(f"BASE_PATH routing: {config.BASE_PATH}")
            logger.info(f"Endpoints: {config.BASE_PATH}/health, {config.BASE_PATH}/mcp")
        else:
            logger.info("Root path routing (no BASE_PATH)")
            logger.info("Endpoints: /health, /ready, /live, /mcp")
        
        # Apply health check filter to access logs
        logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())
        
        # Run the server
        uvicorn.run(app, host="0.0.0.0", port=8080)
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        try:
            # uvicorn.run() has returned, so no event loop is running here.
            asyncio.run(cleanup())
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        logger.info("Server shutdown complete")
