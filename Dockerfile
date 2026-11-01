FROM ghcr.io/astral-sh/uv:0.8.15 AS uv
FROM python:3.11-slim
COPY --from=uv /uv /bin/uv
WORKDIR /app
ENV PYTHONUNBUFFERED=1 UV_LINK_MODE=copy PATH="/app/backend/.venv/bin:$PATH"
COPY backend /app/backend
RUN uv sync --project backend --frozen --no-dev && \
    useradd --create-home --uid 10001 civicmesh && \
    mkdir -p /app/.cache && chown civicmesh:civicmesh /app/.cache
USER civicmesh
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
