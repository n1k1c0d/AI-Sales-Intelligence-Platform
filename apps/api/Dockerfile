FROM python:3.12.13-slim-trixie@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36 AS base
WORKDIR /app

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.0@sha256:e49fde5daf002023f0a2e2643861ce9ca8a8da5b73d0e6db83ef82ff99969baf /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
COPY .python-version pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY README.md ./
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-editable

FROM base AS runtime
ENV PATH="/app/.venv/bin:${PATH}" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --gid 10001 dealmind && useradd --uid 10001 --gid dealmind --no-create-home --shell /usr/sbin/nologin dealmind
COPY --from=builder /app/.venv /app/.venv
USER dealmind
EXPOSE 8000
CMD ["uvicorn", "dealmind.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
