FROM public.ecr.aws/docker/library/python:3.14-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./

ENV UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

FROM public.ecr.aws/docker/library/python:3.14-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/src" \
    PATH="/app/.venv/bin:$PATH"

COPY --from=builder /app/.venv /app/.venv
COPY src /app/src

WORKDIR /app

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backplane.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
