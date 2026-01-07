# Copyright © Lumenore Inc. All rights reserved.

import requests

from exceptions.exceptions import AuthenticationError
from typing import Optional

from config import config
from utils.logger import get_logger

logger = get_logger()


class LumenoreAuthClient:
    """
    Authentication client for Lumenore API.

    Handles cookie-based JWT authentication with automatic token refresh.
    Thread-safe for single-user scenarios (self-hosted mode).
    """

    def __init__(self, client_id: str, secret: str, base_url: str):
        """
        Initialize authentication client.

        Args:
            client_id: Lumenore client ID
            secret: Lumenore client secret
            base_url: Base URL for Lumenore API (e.g., https://preview.lumenore.com)
        """
        self.client_id = client_id
        self.secret = secret
        self.base_url = base_url

        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "lumenore-mcp-server/1.0.0", "Accept": "application/json"}
        )

        self.access_token: Optional[str] = None
        self.token_expiry: Optional[float] = None
        self.tokenmd5: Optional[str] = None

        logger.info(f"Initialized LumenoreAuthClient for {self.base_url}")

    def authenticate(self) -> bool:
        """
        Authenticate with Lumenore API and obtain access token.

        Returns:
            True if authentication successful

        Raises:
            AuthenticationError: If authentication fails
        """
        url = f"{self.base_url}/api/secure/client/user-login"
        payload = {"data": {"clientId": self.client_id, "secret": self.secret}}

        logger.info(f"{url = } {payload = }")

        try:
            logger.debug(f"Authenticating to {url}")
            response = self.session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            logger.info(response.status_code)
            logger.info(response.cookies)

            if response.status_code == 200:
                self.access_token = "Bearer " + response.cookies.get("access_token")

                if self.access_token:
                    logger.info("Authentication successful")
                    return self.access_token
                else:
                    raise AuthenticationError("No access_token in response cookies")

            else:
                error_msg = f"Authentication failed with status {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg += f": {error_data}"
                except:
                    error_msg += f": {response.text}"

                raise AuthenticationError(error_msg)

        except requests.RequestException as e:
            raise AuthenticationError(f"Network error during authentication: {e}")
