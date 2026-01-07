import logging
import sys
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, ValidationError, model_validator
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

    TOKEN: Optional[bool] = Field(default=False, alias="LUMENORE_API_KEY")
    CLIENT_ID: Optional[str] = Field(default=None, alias="LUMENORE_CLIENT_ID")
    SECRET: Optional[str] = Field(default=None, alias="LUMENORE_SECRET")

    DEBUG: bool = Field(default=False, alias="DEBUG")

    @model_validator(mode="after")
    def validate_credentials(self):
        token_provided = self.TOKEN and self.TOKEN.strip()
        client_credentials_provided = (
            self.CLIENT_ID
            and self.SECRET
            and self.CLIENT_ID.strip()
            and self.SECRET.strip()
        )
        if not token_provided and not client_credentials_provided:
            raise ValueError("Either LUMENORE_API_KEY or both LUMENORE_CLIENT_ID and LUMENORE_SECRET must be provided")
        return self

    @property
    def headers(self):
        if self.TOKEN:
            return {"Authorization": f"Bearer {self.TOKEN}"}
        return {}


try:
    config = ConfigModel()
except ValidationError as e:
    error = e.errors()
    logger.error(f"Startup Failed: {error[0]['msg']}")
    sys.exit(1)
except Exception as e:
    logger.error("Startup Failed: %s", e)
    sys.exit(1)
