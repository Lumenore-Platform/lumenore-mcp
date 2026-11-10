import logging
import sys
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings

load_dotenv()

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("config")


class ConfigModel(BaseSettings):
    SERVER_URL: str = Field(default="https://preview.lumenore.com", alias="SERVER_URL")
    BASE_PATH: str = Field(default="", alias="BASE_PATH")  # Optional path prefix for deployment (e.g., /bridge/lumenore-mcp)

    # OAuth protected-resource metadata. These are public URLs; do not use
    # localhost values when the MCP server is accessed by an external client.
    AUTHORIZATION_SERVER_ISSUER: str = Field(
        default="http://localhost:8081", alias="AUTHORIZATION_SERVER_ISSUER"
    )
    MCP_RESOURCE_URL: str = Field(
        default="http://localhost:8080/mcp", alias="MCP_RESOURCE_URL"
    )
    UPLOAD_PAGE_BASE_URL: Optional[str] = Field(default=None, alias="UPLOAD_PAGE_BASE_URL")
    MCP_SCOPES: str = Field(
        default="mcp.tools,lumenore", alias="MCP_SCOPES"
    )

    TOKEN: Optional[str] = Field(default=None, alias="LUMENORE_API_KEY")
    CLIENT_ID: Optional[str] = Field(default=None, alias="LUMENORE_CLIENT_ID")
    SECRET: Optional[str] = Field(default=None, alias="LUMENORE_SECRET")

    # Session-management calls use this base URL. Raw bytes use the dynamic
    # signed URL returned by publish-api, which may have another hostname.
    PUBLISH_API_BASE_URL: Optional[str] = Field(
        default=None, alias="PUBLISH_API_BASE_URL"
    )  # defaults to {SERVER_URL}/api/publish
    PUBLISH_API_TOKEN: Optional[str] = Field(default=None, alias="PUBLISH_API_TOKEN")
    PUBLISH_API_SESSIONS_PATH: str = Field(
        default="/signed/sessions", alias="PUBLISH_API_SESSIONS_PATH"
    )
    MAX_INLINE_BYTES: int = Field(default=102400, alias="MAX_INLINE_BYTES", gt=0)
    MAX_CHUNK_BYTES: int = Field(default=30000, alias="MAX_CHUNK_BYTES", gt=0)
    MAX_TOTAL_BYTES: int = Field(default=104857600, alias="MAX_TOTAL_BYTES", gt=0)
    UPLOAD_URL_CACHE_TTL_SECONDS: int = Field(
        default=600, alias="UPLOAD_URL_CACHE_TTL_SECONDS", gt=0
    )
    CHUNK_NUMBER_START: int = Field(default=0, alias="CHUNK_NUMBER_START", ge=0)
    ENABLE_HANDOFF_TOOLS: bool = Field(default=False, alias="ENABLE_HANDOFF_TOOLS")
    ALLOWED_EXTENSIONS: str = Field(default="", alias="ALLOWED_EXTENSIONS")
    DEFAULT_UPLOAD_DESTINATION: Optional[str] = Field(
        default="Lumenore", alias="DEFAULT_UPLOAD_DESTINATION"
    )
    # Hosts the browser upload page may send file bytes to (comma-separated;
    # subdomains match). Defaults to the PUBLISH_API_BASE_URL host.
    UPLOAD_PAGE_ALLOWED_HOSTS: str = Field(default="", alias="UPLOAD_PAGE_ALLOWED_HOSTS")
    # Optional allowlist for upload_file_from_url source hosts (comma-separated;
    # subdomains match). Empty allows any public HTTPS host.
    ALLOWED_SOURCE_URL_HOSTS: str = Field(default="", alias="ALLOWED_SOURCE_URL_HOSTS")

    DEBUG: bool = Field(default=False, alias="DEBUG")

    def has_credentials(self) -> bool:
        """Check if server-level credentials are configured."""
        token_provided = self.TOKEN and self.TOKEN.strip()
        client_credentials_provided = (
            self.CLIENT_ID
            and self.SECRET
            and self.CLIENT_ID.strip()
            and self.SECRET.strip()
        )
        return bool(token_provided or client_credentials_provided)

    @property
    def mcp_scopes(self):
        """Scopes advertised for MCP authorization metadata."""
        return [scope.strip() for scope in self.MCP_SCOPES.split(",") if scope.strip()]

    @property
    def headers(self):
        if self.TOKEN:
            return {"Authorization": f"Bearer {self.TOKEN}"}
        return {}

    @property
    def upload_base_url(self) -> str:
        if self.PUBLISH_API_BASE_URL:
            return self.PUBLISH_API_BASE_URL.rstrip("/")
        return f"{self.SERVER_URL.rstrip('/')}/api/publish"

    @staticmethod
    def _host_list(value: str):
        return {
            item.strip().lower().rstrip(".")
            for item in value.split(",")
            if item.strip()
        }

    @property
    def upload_page_allowed_hosts(self):
        hosts = self._host_list(self.UPLOAD_PAGE_ALLOWED_HOSTS)
        if not hosts:
            from urllib.parse import urlsplit

            default_host = urlsplit(self.upload_base_url).hostname
            if default_host:
                hosts.add(default_host.lower())
        return hosts

    @property
    def allowed_source_url_hosts(self):
        return self._host_list(self.ALLOWED_SOURCE_URL_HOSTS)

    @property
    def allowed_extensions(self):
        return {
            item.strip().lower().lstrip(".")
            for item in self.ALLOWED_EXTENSIONS.split(",")
            if item.strip()
        }


try:
    config = ConfigModel()
    if config.has_credentials():
        logger.warning(
            "Server-level credentials are configured. Requests without their own "
            "credentials will run as this account, and /mcp will not require "
            "OAuth. Do not use server-level credentials on a publicly reachable "
            "deployment."
        )
    else:
        logger.info(
            "No server-level credentials configured. "
            "Users must provide credentials via request headers "
            "(Authorization or Lumenore-Client-Id/Lumenore-Client-Secret; "
            "X- prefixed variants also accepted)."
        )
except ValidationError as e:
    error = e.errors()
    logger.error(f"Startup Failed: {error[0]['msg']}")
    sys.exit(1)
except Exception as e:
    logger.error("Startup Failed: %s", e)
    sys.exit(1)
