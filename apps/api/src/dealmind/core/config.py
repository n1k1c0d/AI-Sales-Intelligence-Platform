import re
from typing import Annotated, Literal

from pydantic import AfterValidator, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


def _origin(value: str) -> str:
    # Accept only an origin's scheme and authority, before URL normalization.
    if not re.fullmatch(r"https?://[^/?#@*%\\\s\x00-\x1f\x7f]+", value, flags=re.IGNORECASE):
        raise ValueError("Expected an HTTP(S) origin with only a host and optional port")
    return str(HttpUrl(value)).removesuffix("/")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=None, extra="ignore", frozen=True, hide_input_in_errors=True
    )

    env: Literal["local", "test", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_origins: tuple[Annotated[str, AfterValidator(_origin)], ...] = ()
