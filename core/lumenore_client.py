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

        logger.debug("[OAuth] Initialized LumenoreAuthClient: base_url=%s", self.base_url)

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


        try:
            response = self.session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            logger.debug("[OAuth] Login response received: status=%s", response.status_code)

            if response.status_code == 200:
                access_token = response.cookies.get("access_token")
                self.access_token = f"Bearer {access_token}" if access_token else None

                if self.access_token:
                    logger.debug("[OAuth] Authentication successful")
                    return self.access_token
                else:
                    logger.error(
                        "[OAuth] Authentication response did not include an access_token cookie"
                    )
                    raise AuthenticationError("No access_token in response cookies")

            else:
                # Do not echo the response body: it may contain sensitive details.
                error_msg = f"Authentication failed with status {response.status_code}"
                logger.error("[OAuth] %s", error_msg)
                raise AuthenticationError(error_msg)

        except requests.RequestException as e:
            logger.error("[OAuth] Network error during authentication: %s", type(e).__name__)
            raise AuthenticationError("Network error during authentication") from None
