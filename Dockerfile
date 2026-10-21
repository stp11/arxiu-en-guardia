FROM python:3.11

ARG BUILD_ENVIRONMENT=prod
ENV BUILD_ENVIRONMENT=$BUILD_ENVIRONMENT \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /usr/local/bin/uv

# The venv lives outside /app, which docker-compose mounts over.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY ./backend/pyproject.toml ./backend/uv.lock ./backend/.python-version ./

RUN if [ "$BUILD_ENVIRONMENT" = "local" ]; then \
        echo ">>> Installing development requirements" && \
        uv sync --locked --no-cache; \
    else \
        echo ">>> Installing production requirements" && \
        uv sync --locked --no-cache --no-dev; \
    fi

COPY ./backend .

RUN chmod +x /app/entrypoints/*.sh

ENTRYPOINT ["/app/entrypoints/start.sh"]
