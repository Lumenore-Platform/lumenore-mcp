# Lumenore Analytics MCP Server

[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-Code%20of%20Conduct-ff69b4.svg)](CODE_OF_CONDUCT.md)

A Model Context Protocol (MCP) server that gives AI assistants (Claude, ChatGPT and other MCP clients) access to Lumenore's analytics, natural language query and file upload capabilities. Built with FastMCP and Python 3.13.

## What's New

- **OAuth 2.0 for MCP clients**: the server publishes OAuth protected-resource metadata and returns `401` with a `WWW-Authenticate` challenge, so Claude, ChatGPT and other OAuth-capable clients can sign users in through the Lumenore identity provider. The user's bearer token is forwarded to Lumenore on every call.
- **Multi-tenant authentication**: each request can carry its own credentials (bearer token or Lumenore client ID/secret headers). Server-level credentials are now optional.
- **File upload tools**: upload files into Lumenore file storage, inline for small files, through a browser upload page for large files, from an HTTPS URL, or in chunks.
- **Browser upload page**: a built-in `/upload` page uploads large files straight from the user's browser to a signed URL, so file bytes never pass through the model.
- **New tools**: `get_metadata_info` (column-level schema details) and `health_check`.
- **Deployment**: `BASE_PATH` routing for gateways/ingress, health probes (`/health`, `/ready`, `/live`), and a `run.sh` startup script.

## Quick Start

```bash
git clone <repository-url>
cd lumenore-mcp-engine
pip install -r requirements.txt
cp .env.example .env        # then edit the values
python main.py              # or ./run.sh
```

Connect your MCP client to `http://localhost:8080/mcp` using **Streamable HTTP**.

- With an OAuth-capable client (Claude, ChatGPT), the client discovers the authorization server and signs the user in. See [Authentication](#authentication).
- For local testing without OAuth, set `LUMENORE_API_KEY` (or `LUMENORE_CLIENT_ID` + `LUMENORE_SECRET`) in `.env`.

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Server](#running-the-server)
- [Authentication](#authentication)
- [Connecting Your AI Assistant](#connecting-your-ai-assistant)
- [Available Tools](#available-tools)
- [File Uploads](#file-uploads)
- [HTTP Endpoints](#http-endpoints)
- [Usage Examples](#usage-examples)
- [Security & Privacy](#security--privacy)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [Support](#support)
- [License](#license)

## Overview

- **Natural Language Queries**: turn questions into data
- **Advanced Analytics**: trends, predictions, correlations, outliers, changes, Pareto analysis
- **File Uploads**: send files to standard Lumenore file storage
- **OAuth & Multi-tenant**: each user authenticates with their own Lumenore identity
- **No Data Storage**: requests are processed in memory (large URL-relay uploads use a temporary file that is deleted when the upload ends); when the server forwards requests to Lumenore's backend, Lumenore's privacy policies apply

## Installation

### Prerequisites

- Python 3.13+
- A Lumenore account, reachable through OAuth, an API token, or client credentials
- Network access to your Lumenore instance (`SERVER_URL`) and publish-api (`PUBLISH_API_BASE_URL`)

### Setup

```bash
git clone <repository-url>
cd lumenore-mcp-engine
pip install -r requirements.txt
cp .env.example .env
```

Main dependencies (see `requirements.txt`): `fastmcp 3.4.4`, `mcp 1.28.1`, `uvicorn`, `starlette`, `httpx`, `aiohttp`, `requests`, `pydantic-settings`, `python-dotenv`.

## Configuration

Settings are read from environment variables or a `.env` file (Pydantic settings). `.env.example` contains a working UAT template.

### Server and routing

| Variable | Required | Default | Description |
|---|---|---|---|
| `SERVER_URL` | No | `https://preview.lumenore.com` | Lumenore backend base URL for analytics calls and client-credential login |
| `BASE_PATH` | No | `""` | Path prefix the app handles itself, e.g. `/bridge/lumenore-mcp`. Leave empty when the gateway strips the prefix |
| `DEBUG` | No | `false` | Debug-level logging (still never logs credentials, queries or responses) |
| `LOG_FILE` | No | – | Optional path for a rotating log file. Logs go to stderr only when unset |

### OAuth (MCP authorization)

| Variable | Required | Default | Description |
|---|---|---|---|
| `AUTHORIZATION_SERVER_ISSUER` | Yes, for OAuth clients | `http://localhost:8081` | Public issuer URL of the Lumenore identity provider, e.g. `https://your-lumenore-host.example.com/api/secure` |
| `MCP_RESOURCE_URL` | Yes, for OAuth clients | `http://localhost:8080/mcp` | Public URL of the MCP endpoint (the gateway URL when a gateway fronts `/mcp`), e.g. `https://your-lumenore-host.example.com/api/mcp-server/mcp` |
| `MCP_SCOPES` | No | `mcp.tools,lumenore` | Comma-separated scopes advertised in the metadata; must match scopes the IDP accepts |

> Use public URLs here. `localhost` defaults only work when the client runs on the same machine.

### Server-level credentials (optional fallback)

| Variable | Required | Default | Description |
|---|---|---|---|
| `LUMENORE_API_KEY` | No | – | Bearer token (JWT, without the `Bearer ` prefix) used when a request carries no credentials |
| `LUMENORE_CLIENT_ID` | No | – | Client ID for client-credential login (`POST {SERVER_URL}/api/secure/client/user-login`) |
| `LUMENORE_SECRET` | No | – | Client secret paired with `LUMENORE_CLIENT_ID` |

Leave these empty for multi-tenant deployments. Every request must then bring its own credentials, and unauthenticated `/mcp` calls get the OAuth `401` challenge.

`PUBLISH_API_TOKEN` (below) also counts as a server-level credential.

When any server-level credential is set, `/mcp` needs no token, so the server validates `Host` and `Origin` to block DNS rebinding from a browser:

| Variable | Default | Description |
|---|---|---|
| `ALLOWED_HOSTS` | – | Extra comma-separated hostnames accepted in the `Host` header (ports are ignored). `localhost`, `127.0.0.1`, `::1` and the `MCP_RESOURCE_URL` host are always accepted. `*` disables the check |
| `ALLOWED_ORIGINS` | – | Extra comma-separated origins (`https://app.example.com`) accepted in the `Origin` header. Origins whose host is an allowed host are always accepted, as are requests without `Origin`. `*` disables the check |

Other requests to `/mcp` get `403`. If the server runs behind a proxy or a container service name, add that hostname to `ALLOWED_HOSTS`.

### File uploads

| Variable | Default | Description |
|---|---|---|
| `PUBLISH_API_BASE_URL` | `{SERVER_URL}/api/publish` | Base URL for upload session management |
| `PUBLISH_API_SESSIONS_PATH` | `/signed/sessions` | Sessions path below `PUBLISH_API_BASE_URL` |
| `PUBLISH_API_TOKEN` | – | Optional server-level bearer for publish-api; used only when the request carries no credentials at all. Counts as a server-level credential |
| `UPLOAD_PAGE_BASE_URL` | derived | Public URL of the browser upload page, e.g. `https://your-lumenore-host.example.com/bridge/lumenore-mcp/upload`. Defaults to `MCP_RESOURCE_URL` with `/mcp` replaced by `/upload` |
| `UPLOAD_PAGE_ALLOWED_HOSTS` | `PUBLISH_API_BASE_URL` host | Comma-separated hosts (subdomains match) the browser upload page may send files to. Set it if publish-api returns signed URLs on another host |
| `ALLOWED_SOURCE_URL_HOSTS` | – | Optional comma-separated allowlist for `upload_file_from_url`. Empty allows any public HTTPS host |
| `UPLOAD_FROM_URL_MAX_CONCURRENCY` | `2` | Max simultaneous `upload_file_from_url` downloads; further calls are refused until one finishes |
| `UPLOAD_FROM_URL_TIMEOUT_SECONDS` | `300` | Total time one `upload_file_from_url` download may take |
| `MAX_INLINE_BYTES` | `102400` | Max size for `upload_file` (100 KiB) |
| `MAX_CHUNK_BYTES` | `30000` | Max raw bytes per chunk |
| `MAX_TOTAL_BYTES` | `104857600` | Max file size (100 MiB) |
| `UPLOAD_URL_CACHE_TTL_SECONDS` | `600` | How long signed upload URLs are cached per upload |
| `CHUNK_NUMBER_START` | `0` | First chunk number (zero-based) |
| `ALLOWED_EXTENSIONS` | – | Optional allowlist, e.g. `pdf,txt,csv`. Empty allows all |
| `DEFAULT_UPLOAD_DESTINATION` | `Lumenore` | Destination label (metadata only) |
| `ENABLE_HANDOFF_TOOLS` | `false` | Registers the extra handoff tools (see [File Uploads](#file-uploads)) |

### Timeouts (optional)

`REQUEST_TIMEOUT` (60s), `CONNECT_TIMEOUT` (10s), `TOTAL_TIMEOUT` (300s), `RETRY_ATTEMPTS` (1), `RETRY_DELAY` (1s), `POOL_CONNECTIONS` (10), `POOL_MAXSIZE` (20), `POOL_TIMEOUT` (30s), `SERVER_TIMEOUT` (300s), `KEEP_ALIVE_TIMEOUT` (60s).

### Example `.env`

```bash
SERVER_URL=https://your-lumenore-host.example.com

AUTHORIZATION_SERVER_ISSUER=https://your-lumenore-host.example.com/api/secure
MCP_RESOURCE_URL=https://your-lumenore-host.example.com/api/mcp-server/mcp
MCP_SCOPES=mcp.tools,lumenore
UPLOAD_PAGE_BASE_URL=https://your-lumenore-host.example.com/bridge/lumenore-mcp/upload

PUBLISH_API_BASE_URL=https://your-lumenore-host.example.com/api/publish
PUBLISH_API_SESSIONS_PATH=/signed/sessions
PUBLISH_API_TOKEN=
MAX_INLINE_BYTES=102400
MAX_CHUNK_BYTES=30000
MAX_TOTAL_BYTES=104857600
UPLOAD_URL_CACHE_TTL_SECONDS=600
CHUNK_NUMBER_START=0
ENABLE_HANDOFF_TOOLS=false
ALLOWED_EXTENSIONS=
DEFAULT_UPLOAD_DESTINATION=Lumenore

# Optional server-level fallback (leave empty for multi-tenant)
# LUMENORE_API_KEY=
# LUMENORE_CLIENT_ID=
# LUMENORE_SECRET=

# BASE_PATH=/bridge/lumenore-mcp
```

## Running the Server

```bash
python main.py
# or
./run.sh      # prints SERVER_URL / BASE_PATH / DEBUG, then starts main.py
```

The server listens on `0.0.0.0:8080` using the Streamable HTTP transport.

**Base path options**

| Setup | `BASE_PATH` | MCP URL |
|---|---|---|
| Direct, or gateway strips the prefix (recommended) | empty | `http://yourserver:8080/mcp` |
| Gateway forwards the full path | `/bridge/lumenore-mcp` | `http://yourserver:8080/bridge/lumenore-mcp/mcp` |

When `BASE_PATH` is set, only paths under that prefix are served, matched on segment boundaries. Health probes, `/upload` and the OAuth metadata are served under the prefix too.

## Authentication

### How the OAuth flow works

```
MCP client ──► POST /mcp (no token)
           ◄── 401  WWW-Authenticate: Bearer resource_metadata=".../.well-known/oauth-protected-resource/mcp"
MCP client ──► GET /.well-known/oauth-protected-resource/mcp
           ◄── { resource, authorization_servers: [AUTHORIZATION_SERVER_ISSUER], scopes_supported, bearer_methods_supported: ["header"] }
MCP client ──► Lumenore IDP (AUTHORIZATION_SERVER_ISSUER) — user signs in, client gets an access token
MCP client ──► POST /mcp  Authorization: Bearer <token>
MCP server ──► Lumenore APIs with the same Authorization header
```

- The server does not issue or validate tokens itself. It advertises the IDP, and the Lumenore backend validates the forwarded bearer.
- The gateway may exchange the MCP token and forward an IDP-issued bearer. The engine uses whatever `Authorization` header reaches it.
- The `401` challenge is returned when the request has no `Authorization: Bearer` header, no client-credential headers, and no server-level credentials are configured.
- An `Authorization` header that is not `Bearer <token>` is always rejected with `401`. It never falls back to client-credential headers or server-level credentials.

### Credential sources (priority order)

1. `Authorization: Bearer <token>` request header (OAuth or a user-supplied token)
2. `Lumenore-Client-Id` + `Lumenore-Client-Secret` request headers (`X-Lumenore-Client-Id` / `X-Lumenore-Client-Secret` also accepted). The server logs in at `{SERVER_URL}/api/secure/client/user-login` and uses the returned `access_token` cookie.
3. `LUMENORE_API_KEY` from the environment
4. `LUMENORE_CLIENT_ID` + `LUMENORE_SECRET` from the environment

Tokens obtained through client-credential login are refreshed once automatically on a `401` from the backend. Tool calls with no usable credentials fail with `401 Unauthorized: No credentials provided`.

For uploads, publish-api requires a bearer: the request bearer is used first, then client-credential headers (exchanged for a bearer). Only when the request carries no credentials at all is `PUBLISH_API_TOKEN` used, then `LUMENORE_API_KEY`.

### Security best practices

- ✅ Store secrets in environment variables or a secrets vault
- ✅ Rotate tokens regularly and use separate credentials per environment
- ❌ Don't commit `.env` or tokens to version control
- ❌ Don't share or log tokens

## Connecting Your AI Assistant

### Claude / ChatGPT (OAuth)

Add a custom connector with the public MCP URL (`MCP_RESOURCE_URL`), for example `https://your-lumenore-host.example.com/api/mcp-server/mcp`. The client discovers the IDP and asks the user to sign in.

### Clients with static headers

```json
{
  "mcpServers": {
    "lumenore": {
      "type": "streamable-http",
      "url": "https://your-lumenore-host.example.com/api/mcp-server/mcp",
      "headers": {
        "Authorization": "Bearer <token>"
      }
    }
  }
}
```

Alternatively send `Lumenore-Client-Id` and `Lumenore-Client-Secret` headers instead of `Authorization`.

### Programmatic access (Python)

```python
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

transport = StreamableHttpTransport(
    "http://localhost:8080/mcp",
    headers={"Authorization": "Bearer <token>"},
)
async with Client(transport) as client:
    tools = await client.list_tools()
    result = await client.call_tool("nlq_to_data", {
        "userQuery": "Top 5 sales regions last month",
        "schemaId": 123,
    })
```

**Connection details**: Streamable HTTP, port 8080, MCP protocol 2024-11-05+, auth via OAuth bearer, client-credential headers, or server-level credentials.

## Available Tools

### Datasets

| Tool | Description |
|---|---|
| `get_dataset_metadata` | Lists available datasets with schema IDs, names and timestamps |
| `get_metadata_info` | Column-level metadata for a schema (`schemaId`): names, aliases, descriptions, data types, date formats, units |

### Natural language queries

| Tool | Description |
|---|---|
| `nlq_to_data` | Converts a question into structured data (`userQuery`, `schemaId`) |

### Advanced analytics

All take `userQuery` and `schemaId`.

| Tool | Description |
|---|---|
| `get_trend_data` | Temporal patterns and trends |
| `get_prediction_data` | Forecasts and predictions |
| `get_outlier_data` | Anomalies and unusual patterns |
| `get_correlation_data` | Relationships between variables |
| `get_change_data` | Pattern shifts and transitions |
| `get_pareto_data` | 80/20 impact analysis |

### File uploads

| Tool | Description |
|---|---|
| `upload_file` | Uploads a small file (≤ `MAX_INLINE_BYTES`) sent inline as text or base64 |
| `create_upload_link` | Creates a short-lived browser upload page (`upload_page_url`) for large files |
| `upload_file_from_url` | Server downloads a public HTTPS URL and uploads it to Lumenore |
| `start_chunked_upload` | Starts a chunked upload session |
| `upload_chunk` | Uploads one base64 chunk (safe to retry) |
| `get_upload_status` | Progress and status of an upload session |
| `complete_upload` | Completes a direct upload or merges chunks |
| `abort_upload` | Aborts an upload session |

With `ENABLE_HANDOFF_TOOLS=true`, three more are registered: `create_direct_upload_session`, `create_chunked_upload_session` (with a shell loop for uploading chunks) and `refresh_upload_url`.

### Diagnostics

| Tool | Description |
|---|---|
| `health_check` | Server status, auth mode, tool list and Lumenore API connectivity (requires credentials) |

### Response format

- **Success**: `{"data": {...}, "status": "success"}`
- **Validation error**: `{"error": "...", "status": "validation_error"}`
- **Service error**: `{"error": "...", "status": "error"}`

Upload tools raise MCP tool errors with an actionable message instead.

### Performance

- Analytics responses usually take 1–7 seconds; request timeout is 60 seconds
- Multiple simultaneous requests are supported

## File Uploads

The default target is standard **Lumenore file storage**. No folder, workspace or dataset is needed. `destination` is metadata only. On completion, publish-api returns `uniqueFileName`.

### Which tool to use

| Situation | Tool |
|---|---|
| File ≤ 100 KiB | `upload_file` |
| Larger file attached in chat | `create_upload_link`, then give the user `upload_page_url` |
| Client has a temporary HTTPS URL for the file | `upload_file_from_url` |
| Script or agent that can send bytes itself | `start_chunked_upload` → `upload_chunk` × N → `complete_upload` |

The server's MCP instructions tell assistants to upload the **complete** file (no trimming or cleaning unless asked), to use the browser page for large attachments, and to confirm the uploaded file name.

### Browser upload page

`create_upload_link` creates a DIRECT session and returns `upload_page_url`, which points at `{UPLOAD_PAGE_BASE_URL}#put=…&complete=…&name=…&type=…&size=…`. The signed URLs are in the URL fragment, which browsers never send to a server, so they do not appear in access logs, gateway logs or `Referer` headers; the page also removes the fragment from the address bar once it has read it. The page:

- can only connect to HTTPS hosts in `UPLOAD_PAGE_ALLOWED_HOSTS` (enforced by the browser through `connect-src`), so it cannot be used to send files to another site. `create_upload_link` also refuses signed URLs on other hosts. Requests that put the signed URLs in the query string get `400`
- lets the user pick or drop the file and checks that its size matches (the file name may differ)
- `PUT`s the bytes to the signed URL with progress, then `POST`s the signed completion URL
- is served with a strict Content-Security-Policy (inline code pinned by hash, `connect-src` built from `UPLOAD_PAGE_ALLOWED_HOSTS`, no framing), `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store` and `noindex`

A `curl` command is also returned as a technical fallback. `content_type` must be a plain media type (`type/subtype`) and every value in the command is shell-quoted.

### Protocol details

- Session create/status/presign/complete/abort calls go to `PUBLISH_API_BASE_URL` + `/signed/sessions[/{id}][/presign|/complete]` with the request's bearer.
- Raw byte `PUT`s go only to the HMAC-signed `uploadUrl` / `uploadUrlTemplate` returned by publish-api (the hostname may differ) with `Content-Type: application/octet-stream`, **never** the bearer token.
- `{chunkNumber}` in the template is replaced with the URL-quoted, zero-based chunk number.
- SHA-256 is sent as lowercase hex; callers may supply it for chunked sessions.
- Retries on `429/500/502/503/504`. Expired signed URLs (`401/403/404/410`) are refreshed once, then the upload fails with a clear error.
- `upload_file_from_url` first verifies the caller's bearer with publish-api, and only then resolves or downloads anything. Downloads are limited by `UPLOAD_FROM_URL_MAX_CONCURRENCY` and `UPLOAD_FROM_URL_TIMEOUT_SECONDS`. It accepts only HTTPS URLs without embedded credentials that resolve to public internet addresses (loopback, private, link-local/cloud-metadata and other internal ranges are rejected, and the connected address is re-checked). It sends no credentials to the source, does not follow redirects, streams in `MAX_CHUNK_BYTES` pieces, and enforces `MAX_TOTAL_BYTES`. Use `ALLOWED_SOURCE_URL_HOSTS` to restrict it further.
- File names are sanitized to a safe basename and checked against `ALLOWED_EXTENSIONS`.

Expected publish-api responses: session create `201`; direct PUT `202` with `data.status=UPLOADED`; chunk PUT `200` (duplicate) or `202`; complete `200`/`201` with `data.uniqueFileName`.

## HTTP Endpoints

All paths are relative to `BASE_PATH` when it is set.

| Path | Method | Auth | Purpose |
|---|---|---|---|
| `/mcp` | POST/GET | Bearer, client headers or server creds | MCP Streamable HTTP endpoint |
| `/.well-known/oauth-protected-resource` and `/.well-known/oauth-protected-resource/mcp` | GET | None | OAuth protected-resource metadata |
| `/upload` | GET | Signed query parameters | Browser upload page |
| `/health`, `/healthz` | GET | None | Status, configuration and tool list |
| `/ready`, `/readiness` | GET | None | Readiness (`503` if tools are unavailable) |
| `/live`, `/liveness` | GET | None | Liveness (`OK`) |

Health probe requests are filtered out of access logs.

## Usage Examples

### Sales performance

```python
metadata = await client.call_tool("get_dataset_metadata", {})
columns  = await client.call_tool("get_metadata_info", {"schemaId": 35403})
sales    = await client.call_tool("nlq_to_data", {
    "userQuery": "Total sales by region for Q4 2024, highest first", "schemaId": 35403})
trend    = await client.call_tool("get_trend_data", {
    "userQuery": "Monthly sales trends for Q4 2024", "schemaId": 35403})
pareto   = await client.call_tool("get_pareto_data", {
    "userQuery": "Which products contribute to 80% of our sales?", "schemaId": 35403})
```

### Customer behaviour

```python
outliers = await client.call_tool("get_outlier_data", {
    "userQuery": "Customers with unusually high order values or frequency", "schemaId": 35404})
drivers  = await client.call_tool("get_correlation_data", {
    "userQuery": "What factors correlate with customer lifetime value?", "schemaId": 35404})
```

### Inventory forecasting

```python
forecast = await client.call_tool("get_prediction_data", {
    "userQuery": "Predict demand for the next 3 months by product category", "schemaId": 35405})
changes  = await client.call_tool("get_change_data", {
    "userQuery": "Any significant recent changes in demand patterns?", "schemaId": 35405})
```

### Uploading a file

```python
# Small file
await client.call_tool("upload_file", {
    "file_name": "notes.csv", "content": "a,b\n1,2\n", "encoding": "text"})

# Large file: give the user the browser page
link = await client.call_tool("create_upload_link", {
    "file_name": "sales_2025.xlsx", "total_size": 4_812_331,
    "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})
# -> link["upload_page_url"]
```

### Example prompts

- "Use the Lumenore tools to analyze our Q4 sales: regional breakdown, top products and monthly trends."
- "Find unusual purchasing patterns and the factors that drive customer value."
- "Forecast demand for next quarter and flag any recent changes in demand."
- "Upload this file to Lumenore."

**Best practices**: start with `get_dataset_metadata` (and `get_metadata_info`) to find schema IDs and columns, keep queries specific, and check `status` in every response.

## Security & Privacy

### Data protection

- **In-memory processing**: queries and results are not stored by the MCP server
- **HTTPS**: backend and publish-api calls use HTTPS
- **Signed uploads**: file bytes go to short-lived HMAC-signed URLs. The bearer token is never attached to them, and signed URLs are cached only for `UPLOAD_URL_CACHE_TTL_SECONDS`, scoped to the token that created them
- **Header isolation**: request headers are kept in a per-request (per-task) context and cleared after each tool call, so concurrent users never share credentials
- **Logging**: credentials, request headers, queries, payloads and response bodies are never logged. Logs go to stderr only unless `LOG_FILE` is set
- **Error messages**: errors returned to clients name the failing operation and status code, without backend URLs or response bodies
- **SSRF protection**: `upload_file_from_url` only fetches public HTTPS addresses
- **Upload page protection**: the `/upload` page only sends files to allowlisted publish-api hosts and cannot be framed

### Authentication security

- **OAuth 2.0**: users sign in with the Lumenore IDP; the MCP endpoint requires a bearer unless server-level credentials are configured
- **Backend validation**: Lumenore validates every forwarded token
- **Per-user credentials**: multi-tenant deployments need no shared server credentials

### Privacy

See the [Privacy Policy](PRIVACY.md).

```
User query → MCP Server → Lumenore Backend → Results → User
             (no storage)  (Lumenore's privacy policy applies)
```

- The server acts as a proxy between AI assistants and Lumenore; Lumenore's backend policies apply to your data
- Users are responsible for making sure their queries and uploads comply with applicable data protection laws
- Data residency and private-cloud/on-premise options: contact the Lumenore team

### Production checklist

- Set `AUTHORIZATION_SERVER_ISSUER`, `MCP_RESOURCE_URL` and `UPLOAD_PAGE_BASE_URL` to public HTTPS URLs
- **Never set server-level credentials (`LUMENORE_API_KEY`, `LUMENORE_CLIENT_ID`/`LUMENORE_SECRET`, `PUBLISH_API_TOKEN`) on a publicly reachable deployment.** With them set, `/mcp` does not require OAuth and anyone who can reach the server acts as that account. The server logs a warning at startup when they are set
- Set `ALLOWED_EXTENSIONS` and `MAX_TOTAL_BYTES` to match your policy
- Restrict `.env` permissions (`chmod 600 .env`)
- Keep `DEBUG=false`
- Set `UPLOAD_PAGE_ALLOWED_HOSTS` to exactly the publish-api hosts you use
- Keep dependencies patched (`pip-audit -r requirements.txt`)

### Reporting security issues

Email [askme@lumenore.com](mailto:askme@lumenore.com) with details and reproduction steps. We acknowledge within 24 hours; please allow us to fix the issue before public disclosure.

## Troubleshooting

### Quick checks

1. Server is up: `curl http://localhost:8080/live` → `OK`
2. Config and tools: `curl http://localhost:8080/health`
3. OAuth metadata: `curl http://localhost:8080/.well-known/oauth-protected-resource/mcp`
4. Backend reachable: `curl -I $SERVER_URL`
5. Client uses the **Streamable HTTP** transport

(Add `BASE_PATH` to each path when it is set.)

### Common issues

| Symptom | Fix |
|---|---|
| Client never shows a sign-in prompt | `AUTHORIZATION_SERVER_ISSUER` and `MCP_RESOURCE_URL` must be public URLs reachable by the client; the metadata endpoint must be reachable through the gateway |
| `401 Bearer token required` on `/mcp` | Expected without credentials; complete OAuth, or send `Authorization` / client-credential headers |
| `401 Unauthorized: No credentials provided` from a tool | The request reached the tool with no credentials; check that the gateway forwards `Authorization` |
| `No bearer token is available for publish-api` | Reconnect the client (OAuth) or set `PUBLISH_API_TOKEN` |
| `publish-api returned an upload URL on a host that is not in UPLOAD_PAGE_ALLOWED_HOSTS` | Add the signed-URL host to `UPLOAD_PAGE_ALLOWED_HOSTS` |
| `source_url must point to a public internet address` | `upload_file_from_url` cannot fetch internal or private addresses |
| Upload page returns `400` | The link is incomplete or expired; create a new one with `create_upload_link` |
| Upload page says the size doesn't match | Choose the original file; its size must equal the size given to `create_upload_link` |
| `File extension is not allowed` | Adjust `ALLOWED_EXTENSIONS` |
| `404` behind a gateway | Check `BASE_PATH`: empty if the gateway strips the prefix, the prefix if it forwards it |

### Debug logging

```bash
DEBUG=true python main.py
```

Check startup logs for the configured endpoints and the credential-mode message. With `DEBUG=true`, `[Middleware]` / `[Auth]` lines show which credential source was used (never the credential itself).

### Running tests

```bash
python -m pytest
```

## Project Structure

```
main.py                     ASGI router: BASE_PATH, health, OAuth metadata, 401 challenge, /upload page
mcp_instance.py             FastMCP instance and assistant instructions
config.py                   Settings (env / .env)
run.sh                      Startup script
health_endpoint.py          /health, /ready, /live
core/
  middleware.py             Per-request credential checks for tool calls
  request_context.py        Per-request header storage (ContextVar)
  lumenore_analytics.py     Analytics API client and credential resolution
  lumenore_client.py        Client-credential login
  file_upload_client.py     publish-api client: sessions, signed PUTs, retries
tools/
  dataset_tools.py          get_dataset_metadata, get_metadata_info
  nlq_tools.py              nlq_to_data
  advance_analytics_tools.py  trend, prediction, outlier, correlation, change, pareto
  file_upload_tools.py      upload tools
  health_check.py           health_check tool
tests/                      pytest tests
```

## Contributing

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

1. Fork the repository
2. Create a branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Push and open a Pull Request

Report bugs and request features through GitHub Issues with steps to reproduce, expected vs actual behaviour, and environment details (Python version, OS).

## License

MIT. See [LICENSE](LICENSE).

## Support

- **Email**: askme@lumenore.com
- **Website**: [lumenore.com](https://lumenore.com/)
- **Docs**: [Lumenore Ask Me knowledge base](https://help.lumenore.com/knowledge-base/lumenore_ask_me/)
- **MCP spec**: [modelcontextprotocol.io](https://modelcontextprotocol.io/)
- **FastMCP**: [github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp)

When reporting a problem, include the server and Python versions, error messages and logs, and steps to reproduce.

---

**Version**: 1.0.0
**Last Updated**: November 2026
**Python**: 3.13+
**MCP Protocol**: 2024-11-05+
