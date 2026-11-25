from pydantic import BaseModel


class ValidationIssue(BaseModel):
    loc: list[str | int]
    message: str
    type: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[ValidationIssue] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
