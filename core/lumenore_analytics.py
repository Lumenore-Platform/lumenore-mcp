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

    def __init__(self, headers: Optional[Dict[str, str]] = None):
        """
        Initialize the LumenoreAnalytics client.

        Args:
            headers: Optional custom headers to override default configuration
        """
        self._headers = headers or config.headers
        self.base_url = config.SERVER_URL
        self._session = None
        self._connector = None
        self.access_token = None

        if not self.base_url:
            raise ValueError("SERVER_URL is not configured")

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

    def has_valid_authorization(self) -> bool:
        """
        Check if there's valid authorization available.

        Returns:
            True if either headers or config has authorization
        """
        # Check headers case-insensitively
        if any(k.lower() == "authorization" for k in self._headers.keys()):
            return True

        if hasattr(config, "TOKEN") and config.TOKEN:
            return True

        return False

    def get_authorization_token(self) -> Optional[str]:
        """
        Get the authorization token from available sources.

        Returns:
            Authorization token string or None if not available
        """
        # Check headers case-insensitively
        for key, value in self._headers.items():
            if key.lower() == "authorization":
                return value

        if hasattr(config, "TOKEN") and config.TOKEN:
            # Token from config should already be properly formatted
            return config.TOKEN

        return None

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
            self._get_auth_client()
            if not self.access_token:
                raise AuthorizationError(
                    "No valid authorization found. Please provide "
                    "LUMENORE_CLIENT_ID and LUMENORE_SECRET"
                )

        url = self._build_url(endpoint_name)

        request_headers = dict(self.headers)
        request_headers["Authorization"] = self.access_token

        try:
            # Use persistent session for connection reuse
            session = self._get_session()

            # Prepare request kwargs
            request_kwargs = {
                "headers": request_headers,
                "params": query_params
            }

            # Add payload for methods that support body
            if method.upper() in ["POST", "PUT", "PATCH"] and payload is not None:
                request_kwargs["json"] = payload

            # Make request based on method
            logger.info(f"API call {method.upper()}, {url}, {request_kwargs}")
            async with session.request(method.upper(), url, **request_kwargs) as resp:
                if stream:
                    result = ""
                    async for line in resp.content:
                        result += line.decode()

                    return result

                resp.raise_for_status()
                result = await resp.json()

                logger.info(f"{url = } response: {result}")

                return result

        except asyncio.TimeoutError as e:            
            raise APIRequestTimeout(f"Request to {url} timed out") from e

        except aiohttp.ClientError as e:            
            raise APIRequestError(f"API request failed: {str(e)}") from e

        except Exception as e:            
            raise UnexpectedAPIError(f"Request failed: {str(e)}") from e

    def _get_auth_client(self):
        """
        Get or create the cookie-based authentication client.
        Lazy-loaded to support both bearer token and cookie-based auth.
        """
        if (hasattr(config, 'CLIENT_ID') and hasattr(config, 'SECRET')):
            if config.TOKEN:
                self.access_token = config.TOKEN
                return

            from core.lumenore_client import LumenoreAuthClient
            self.auth_client = LumenoreAuthClient(
                client_id=config.CLIENT_ID,
                secret=config.SECRET,
                base_url=config.SERVER_URL
            )
            try:
                self.access_token = self.auth_client.authenticate()
                logger.info(f"Cookie-based authentication initialized successfully {self.access_token}")
            except Exception as e:
                logger.error(f"Failed to initialize cookie-based authentication: {e}")
                raise

        if config.TOKEN:
            self.access_token = config.TOKEN

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

        return await self.make_request(
            endpoint_name=endpoint_name,
            method=method,
            payload=payload,
            query_params=query_params,
            stream=stream
        )

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


_lumenore_client = None


def get_lumenore_client(headers: Optional[Dict[str, str]] = None) -> LumenoreAnalytics:
    """
    Get or create a global LumenoreAnalytics client instance.

    Args:
        headers: Optional custom headers

    Returns:
        LumenoreAnalytics client instance
    """
    global _lumenore_client
    if _lumenore_client is None:
        _lumenore_client = LumenoreAnalytics(headers=headers)
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
