import re
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, Field, HttpUrl, SecretStr, StringConstraints, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _origin(value: str) -> str:
    # Accept only an origin's scheme and authority, before URL normalization.
    if not re.fullmatch(r"https?://[^/?#@*%\\\s\x00-\x1f\x7f]+", value, flags=re.IGNORECASE):
        raise ValueError("Expected an HTTP(S) origin with only a host and optional port")
    return str(HttpUrl(value)).removesuffix("/")


DatabaseName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PositiveSeconds = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=None, extra="ignore", frozen=True, hide_input_in_errors=True
    )

    env: Literal["local", "test", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_origins: tuple[Annotated[str, AfterValidator(_origin)], ...] = ()
    db_host: DatabaseName = "127.0.0.1"
    db_port: int = Field(default=5433, ge=1, le=65535)
    db_name: DatabaseName = "dealmind"
    db_user: DatabaseName = "dealmind"
    db_password: SecretStr | None = Field(default=None, min_length=1, repr=False)
    db_pool_size: int = Field(default=5, gt=0)
    db_max_overflow: int = Field(default=5, ge=0)
    db_pool_timeout: PositiveSeconds = 5
    db_connect_timeout: int = Field(default=3, gt=0)
    db_health_timeout: PositiveSeconds = 5

    @model_validator(mode="after")
    def validate_production_database(self) -> Self:
        required = {"db_host", "db_port", "db_name", "db_user", "db_password"}
        if self.env == "production" and (
            self.db_password is None or not required.issubset(self.model_fields_set)
        ):
            raise ValueError(
                "Production requires explicit APP_DB_HOST, PORT, NAME, USER and PASSWORD"
            )
        return self
