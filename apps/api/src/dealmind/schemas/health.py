from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


class ReadinessChecks(BaseModel):
    application: Literal["ok", "not_ready"]
    database: Literal["ok", "not_ready"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: ReadinessChecks
