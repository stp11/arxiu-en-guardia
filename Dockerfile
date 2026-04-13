FROM python:3.11

ARG BUILD_ENVIRONMENT=prod
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv

WORKDIR /app

COPY ./backend/requirements ./requirements

RUN if [ "$BUILD_ENVIRONMENT" = "local" ]; then \
        echo ">>> Installing development requirements" && \
        uv pip install --system --no-cache -r requirements/local.txt; \
    else \
        echo ">>> Installing production requirements" && \
        uv pip install --system --no-cache -r requirements/prod.txt; \
    fi

COPY ./backend .

RUN chmod +x /app/entrypoints/*.sh

ENTRYPOINT ["/app/entrypoints/start.sh"]
