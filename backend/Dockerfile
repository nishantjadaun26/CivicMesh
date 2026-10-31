FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app
RUN useradd --uid 10001 --create-home civicmesh
USER civicmesh
CMD ["sh", "-c", ".venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
