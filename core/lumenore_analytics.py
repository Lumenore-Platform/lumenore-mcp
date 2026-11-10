import aiohttp
import asyncio
from typing import Dict, Any, Optional, Union
from enum import Enum
from exceptions import (
    AuthorizationError,
    UnexpectedAPIError,
    APIRequestError,
    APIRequestTimeout,
)
from config import config
from utils.timeout_config import TimeoutConfig

from utils.logger import get_logger
logger = get_logger()

class LumenoreAnalytics:
    """
    Core analytics class providing centralized API management and validation.

    This class handles all common functionality including request validation,
    authorization management, and API communication for the Lumenore platform.
    """

    class ServicePaths(Enum):
        """Enum for service paths mapping."""
        ASKME_MANAGER = "api/askme-manager"
        AI_ENGINE = "api/ai-engine/mcp"

    class UnsafeHeaderKeys(Enum):
        """Enum for unsafe header keys that should be removed."""
        ACCEPT = "accept"
        HOST = "host"
        CONNECTION = "connection"
        SEC_FETCH_MODE = "sec-fetch-mode"
        ACCEPT_ENCODING = "accept-encoding"
        ACCEPT_LANGUAGE = "accept-language"
        CONTENT_LENGTH = "content-length"

    class EndpointsByService(Enum):
        """Enum for endpoints grouped by service."""
        ASKME_MANAGER = {"get-domain", "metadata/get"}
        AI_ENGINE = {
            "get-outlier-data",
            "get-trend-data",
            "get-prediction-data",
            "get-correlation-data",
            "get-change-data",
            "get-pareto-data",
            "nlq-to-data",
        }

    def __init__(
        self,
        headers: Optional[Dict[str, str]] = None,
        token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        """
        Initialize the LumenoreAnalytics client.

        Args:
            headers: Optional custom headers to override default configuration
            token: Optional bearer token (runtime credential, takes priority over config)
            client_id: Optional client ID (runtime credential, takes priority over config)
            client_secret: Optional client secret (runtime credential, takes priority over config)
        """
        self._headers = headers or config.headers
        self.base_url = config.SERVER_URL
        self._session = None
        self._connector = None
        self.access_token = None
        # Set only when the token was obtained via client-credential login,
        # which is what makes the token refreshable on a 401.
        self.auth_client = None
        # Marks per-request clients so callers can close them after use.
        self._ephemeral = False

        # Store runtime credentials (take priority over config)
        self._runtime_token = token
        self._runtime_client_id = client_id
        self._runtime_client_secret = client_secret

        if not self.base_url:
            raise ValueError("SERVER_URL is not configured")

        logger.debug(
            "[LumenoreAnalytics] Client initialized: base_url=%s, runtime_token=%s, runtime_client_credentials=%s",
            self.base_url,
            bool(self._runtime_token),
            bool(self._runtime_client_id and self._runtime_client_secret),
        )

    def _get_session(self) -> aiohttp.ClientSession:
        """
        Get or create a persistent aiohttp ClientSession with proper timeout and connection pooling.
        
        Returns:
            Configured aiohttp.ClientSession instance
        """
        if self._session is None or self._session.closed:
            # Configure timeout settings
            timeout_settings = TimeoutConfig.get_timeout_settings()
            timeout = aiohttp.ClientTimeout(
                total=timeout_settings['total_timeout'],
                connect=timeout_settings['connect_timeout'],
                sock_read=timeout_settings['request_timeout']
            )

            # Configure connection pooling for better performance with multiple requests
            self._connector = aiohttp.TCPConnector(
                limit=timeout_settings['pool_maxsize'],
                limit_per_host=timeout_settings['pool_connections'],
                ttl_dns_cache=300,
                force_close=False,  # Keep connections alive
                enable_cleanup_closed=True
            )

            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=self._connector
            )

        return self._session

    async def close(self):
        """
        Close the persistent session and connector.
        Should be called when done with the client to clean up resources.
        """
        if self._session and not self._session.closed:
            await self._session.close()
        if self._connector:
            await self._connector.close()

    async def __aenter__(self):
        """Support async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting context."""
        await self.close()

    @property
    def headers(self) -> Dict[str, Any]:
        """
        Return a sanitized copy of headers.
        Removes unwanted keys and ensures a proper 'accept' header.
        NOTE: Keys are kept as-is (not lowercased) to preserve HTTP header capitalization.
        """
        clean = {k: v for k, v in self._headers.items()}

        for bad_key in self.UnsafeHeaderKeys:
            clean.pop(bad_key.value, None)

        clean.setdefault("accept", "application/json")

        return clean

    @headers.setter
    def headers(self, value: Dict[str, Any]):
        """Allow updating the underlying headers safely."""
        self._headers = value

    def _get_service_for_endpoint(self, endpoint_name: str) -> str:
        """
        Maps endpoint name to service name.
        Supports dynamic path segments (e.g., "metadata/get/123" matches "metadata/get").

        Args:
            endpoint_name: Name of the API endpoint (may include dynamic segments)

        Returns:
            Service name that handles the endpoint

        Raises:
            ValueError: If endpoint is not recognized
        """
        # First try exact match
        for service in self.EndpointsByService:
            if endpoint_name in service.value:
                return service.name.lower().replace("_", "-")


        for service in self.EndpointsByService:
            for endpoint_pattern in service.value:
                if endpoint_name.startswith(endpoint_pattern + "/"):
                    return service.name.lower().replace("_", "-")

        raise ValueError(f"Unknown endpoint name: {endpoint_name}")

    def validate_request(self, schema_id: int, query: str) -> None:
        """
        Validates a request before processing.

        Args:
            schema_id: Schema identifier to validate
            query: Query string to validate

        Raises:
            ValueError: If validation fails
        """
        if not isinstance(schema_id, int) or schema_id <= 0:
            raise ValueError("Schema ID must be a positive integer")

        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        if len(query.strip()) > 5000:
            raise ValueError("Query too long (max 5000 characters)")

    def _build_url(self, endpoint_name: str) -> str:
        """
        Build the full URL for an endpoint.

        Args:
            endpoint_name: Name of the API endpoint

        Returns:
            Complete URL for the endpoint
        """
        service = self._get_service_for_endpoint(endpoint_name)
        service_key = service.upper().replace("-", "_")
        try:
            base_path = self.ServicePaths[service_key].value
        except KeyError:
            raise ValueError(f"Unknown service: {service}")
        return f"{self.base_url}/{base_path}/{endpoint_name}"

    async def make_request(
        self,
        endpoint_name: str,
        method: str = "POST",
        payload: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> Union[Dict[str, Any], str]:
        """
        Make an API request to the backend.

        Args:
            endpoint_name: Name of the API endpoint
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            payload: Request payload data for POST/PUT requests
            query_params: URL query parameters for any request
            stream: Whether to stream the response

        Returns:
            API response data (dict for non-stream, string for stream)

        Raises:
            Exception: If authorization is missing or request fails
        """
        if not self.access_token:
            # Auth uses a synchronous `requests` client; run it off the event loop.
            await asyncio.to_thread(self._get_auth_client)
            if not self.access_token:
                raise AuthorizationError(
                    "No valid authorization found. Please provide either "
                    "LUMENORE_API_KEY or both LUMENORE_CLIENT_ID and LUMENORE_SECRET"
                )

        url = self._build_url(endpoint_name)

        try:
            status, body = await self._perform_request(
                url, method, payload, query_params, stream
            )

            # A client-credential token can expire; refresh once and retry.
            if status == 401 and self._can_refresh_token():
                logger.info(
                    "[Auth] Received 401 from %s; refreshing client-credential token and retrying once",
                    url,
                )
                self.access_token = None
                self.auth_client = None
                await asyncio.to_thread(self._get_auth_client)
                if not self.access_token:
                    raise AuthorizationError(
                        "Re-authentication after 401 did not yield an access token"
                    )
                status, body = await self._perform_request(
                    url, method, payload, query_params, stream
                )

            if status >= 400:
                # Keep backend details in server logs only; callers get a short message.
                logger.warning(
                    "[Backend API] %s %s failed with status %s",
                    method.upper(), endpoint_name, status,
                )
                raise APIRequestError(
                    f"Lumenore API request '{endpoint_name}' failed with status {status}"
                )

            return body

        except asyncio.TimeoutError as e:
            raise APIRequestTimeout(f"Lumenore API request '{endpoint_name}' timed out") from e

        except aiohttp.ClientError as e:
            logger.warning("[Backend API] %s network error: %s", endpoint_name, type(e).__name__)
            raise APIRequestError(f"Lumenore API request '{endpoint_name}' failed: network error") from e

        except (
            AuthorizationError,
            APIRequestError,
            APIRequestTimeout,
            UnexpectedAPIError,
        ):
            raise

        except Exception as e:
            logger.error("[Backend API] %s unexpected error: %s", endpoint_name, type(e).__name__)
            raise UnexpectedAPIError(f"Lumenore API request '{endpoint_name}' failed unexpectedly") from e

    async def _perform_request(
        self,
        url: str,
        method: str,
        payload: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, Any]],
        stream: bool,
    ) -> tuple:
        """
        Execute a single HTTP round-trip and return (status_code, body).

        For successful responses, body is the parsed JSON (non-stream) or the
        concatenated text (stream). For error responses (status >= 400), body is
        the raw response text. Auth headers are rebuilt on each call so retries
        after a token refresh use the new token.

        Returns:
            Tuple of (status_code, body)
        """
        session = self._get_session()

        request_headers = dict(self.headers)
        request_headers["Authorization"] = self.access_token

        request_kwargs = {
            "headers": request_headers,
            "params": query_params,
        }

        if method.upper() in ["POST", "PUT", "PATCH"] and payload is not None:
            request_kwargs["json"] = payload

        # Never log headers, payloads or response bodies: they contain
        # credentials, user queries and customer data.
        logger.debug("[Backend API] Request: method=%s url=%s", method.upper(), url)
        async with session.request(method.upper(), url, **request_kwargs) as resp:
            logger.debug("[Backend API] Response: status=%s url=%s", resp.status, url)

            if resp.status >= 400:
                error_body = await resp.text()
                return resp.status, error_body

            if stream:
                result = ""
                async for line in resp.content:
                    result += line.decode()
                return resp.status, result

            result = await resp.json()
            return resp.status, result

    def _can_refresh_token(self) -> bool:
        """
        Whether the current token can be refreshed via client-credential login.

        Mirrors the priority order in `_get_auth_client`: a bearer token (runtime
        or config) is static and cannot be refreshed, while client credentials can.
        """
        if self._runtime_token:
            return False
        if self._runtime_client_id and self._runtime_client_secret:
            return True
        if config.TOKEN:
            return False
        return bool(config.CLIENT_ID and config.SECRET)

    def _get_auth_client(self):
        """
        Get or create the authentication client.
        Supports both bearer token and OAuth2.0 client credentials.

        Priority order:
        1. Runtime token (from request headers)
        2. Runtime client credentials (from request headers)
        3. Config token (from environment)
        4. Config client credentials (from environment)
        """
        # Priority 1: Runtime bearer token
        if self._runtime_token:
            token = self._runtime_token
            if not token.lower().startswith("bearer "):
                token = f"Bearer {token}"
            self.access_token = token
            logger.debug("[Auth] Using runtime bearer token")
            return

        # Priority 2: Runtime client credentials
        if self._runtime_client_id and self._runtime_client_secret:
            logger.debug("[Auth] Using runtime client credentials")
            from core.lumenore_client import LumenoreAuthClient
            self.auth_client = LumenoreAuthClient(
                client_id=self._runtime_client_id,
                secret=self._runtime_client_secret,
                base_url=self.base_url
            )
            try:
                self.access_token = self.auth_client.authenticate()
                logger.debug("[Auth] Runtime client credentials authentication successful")
            except Exception:
                logger.error("[Auth] Runtime client credentials authentication failed")
                raise
            return

        # Priority 3: Config bearer token
        if config.TOKEN:
            token = config.TOKEN
            if not token.lower().startswith("bearer "):
                token = f"Bearer {token}"
            self.access_token = token
            logger.debug("[Auth] Using config bearer token")
            return

        # Priority 4: Config client credentials
        if config.CLIENT_ID and config.SECRET:
            logger.debug("[Auth] Using config client credentials")
            from core.lumenore_client import LumenoreAuthClient
            self.auth_client = LumenoreAuthClient(
                client_id=config.CLIENT_ID,
                secret=config.SECRET,
                base_url=config.SERVER_URL
            )
            try:
                self.access_token = self.auth_client.authenticate()
                logger.debug("[Auth] Config client credentials authentication successful")
            except Exception:
                logger.error("[Auth] Config client credentials authentication failed")
                raise
            return

        raise AuthorizationError(
            "No credentials available. Provide Authorization header, "
            "Lumenore-Client-Id/Lumenore-Client-Secret headers "
            "(X- prefixed variants also accepted), "
            "or configure environment variables."
        )

    async def call_endpoint(
        self,
        endpoint_name: str,
        method: str = "POST",
        stream: bool = False,
        **kwargs
    ) -> Union[Dict[str, Any], str]:
        """
        Complete endpoint call with dynamic parameter handling.

        This method supports both body parameters and query parameters dynamically.
        For POST/PUT/PATCH requests, parameters are sent as JSON payload.
        For GET/DELETE requests, parameters are sent as query parameters.

        Args:
            endpoint_name: Name of the API endpoint
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            stream: Whether to stream the response
            **kwargs: Dynamic parameters (e.g., userQuery, schemaId, or any other params)
                     - For POST/PUT/PATCH: sent as JSON body
                     - For GET/DELETE: sent as query parameters

        Returns:
            API response data

        Examples:
            # POST request with body
            await client.call_endpoint("get-trend-data", userQuery="sales", schemaId=123)
            
            # GET request with query params
            await client.call_endpoint("get-domain", method="GET")
            
            # Custom parameters
            await client.call_endpoint("custom-endpoint", param1="value1", param2="value2")
        """
        # Validate common parameters if present
        if "schemaId" in kwargs and "userQuery" in kwargs:
            self.validate_request(kwargs["schemaId"], kwargs["userQuery"])

        # Determine if parameters should be in body or query
        if method.upper() in ["POST", "PUT", "PATCH"]:
            # Send parameters as JSON body
            payload = kwargs if kwargs else None
            query_params = None
        else:
            # Send parameters as query string (GET, DELETE, etc.)
            payload = None
            query_params = kwargs if kwargs else None

        try:
            return await self.make_request(
                endpoint_name=endpoint_name,
                method=method,
                payload=payload,
                query_params=query_params,
                stream=stream
            )
        finally:
            # Per-request clients own a dedicated session/connector that would
            # otherwise leak; close them once the call is complete.
            if self._ephemeral:
                await self.close()

    def get_supported_endpoints(self) -> Dict[str, list]:
        """
        Get all supported endpoints grouped by service.

        Returns:
            Dictionary mapping services to their endpoints
        """
        return {
            "askme-manager": list(self.EndpointsByService.ASKME_MANAGER.value),
            "ai-engine": list(self.EndpointsByService.AI_ENGINE.value)
        }

    def is_endpoint_supported(self, endpoint_name: str) -> bool:
        """
        Check if an endpoint is supported.

        Args:
            endpoint_name: Name of the endpoint

        Returns:
            True if endpoint is supported
        """
        for service in self.EndpointsByService:
            if endpoint_name in service.value:
                return True
        return False


def extract_credentials_from_headers(headers: Dict[str, str]) -> Dict[str, Optional[str]]:
    """
    Extract authentication credentials from HTTP request headers.

    Supports two authentication methods:
    1. Bearer token via 'Authorization' header
    2. Client credentials via 'Lumenore-Client-Id' and 'Lumenore-Client-Secret'
       headers (the 'X-' prefixed variants are also accepted)

    Args:
        headers: Dictionary of HTTP headers (case-insensitive keys)

    Returns:
        Dictionary with 'token', 'client_id', and 'client_secret' keys
    """
    # Normalize header keys to lowercase for case-insensitive lookup
    normalized = {k.lower(): v for k, v in headers.items()}

    credentials = {
        "token": normalized.get("authorization"),
        "client_id": normalized.get("lumenore-client-id")
        or normalized.get("x-lumenore-client-id"),
        "client_secret": normalized.get("lumenore-client-secret")
        or normalized.get("x-lumenore-client-secret"),
    }
    return credentials


_lumenore_client = None


def get_lumenore_client(
    headers: Optional[Dict[str, str]] = None,
    token: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None
) -> LumenoreAnalytics:
    """
    Get or create a LumenoreAnalytics client instance.

    When runtime credentials (token or client_id/client_secret) are provided,
    creates a new instance for that specific user. Otherwise, uses a shared
    singleton instance with server-level credentials.

    Args:
        headers: Optional custom headers
        token: Optional bearer token from request headers
        client_id: Optional client ID from request headers
        client_secret: Optional client secret from request headers

    Returns:
        LumenoreAnalytics client instance
    """
    # If runtime credentials are provided, create a new instance per-request
    # This enables multi-user support where each user has their own credentials
    if token or (client_id and client_secret):
        logger.debug("[Auth] Creating per-request Lumenore client")
        client = LumenoreAnalytics(
            headers=headers,
            token=token,
            client_id=client_id,
            client_secret=client_secret
        )
        # Per-request clients are not pooled; callers must close them after use.
        client._ephemeral = True
        return client

    # Otherwise, use singleton pattern for server-level credentials
    global _lumenore_client
    if _lumenore_client is None:
        logger.debug("[Auth] Creating singleton Lumenore client with server-level credentials")
        _lumenore_client = LumenoreAnalytics(headers=headers)
    else:
        logger.debug("[Auth] Reusing singleton Lumenore client")
    return _lumenore_client


async def cleanup_lumenore_client():
    """
    Cleanup the global LumenoreAnalytics client instance.
    Should be called during application shutdown to properly close connections.
    """
    global _lumenore_client
    if _lumenore_client is not None:
        await _lumenore_client.close()
        _lumenore_client = None
