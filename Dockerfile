# syntax=docker/dockerfile:1

# =============================================================================
# Nexus Django Application Dockerfile
# Multi-stage build for production deployment
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies
# -----------------------------------------------------------------------------
FROM python:3.14-slim-bookworm AS builder

# Install uv (fast Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set build environment
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

WORKDIR /app

# Install dependencies first (better caching)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Copy application source
COPY . .

# Install project (now with deps already installed)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# -----------------------------------------------------------------------------
# Stage 2: Runtime - Final production image
# -----------------------------------------------------------------------------
FROM python:3.14-slim-bookworm AS runtime

# Security: Run as non-root user
RUN groupadd --gid 1000 nexus && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home nexus

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=nexus:nexus /app/.venv /app/.venv

# Copy application code
COPY --chown=nexus:nexus . .

# Create necessary directories
RUN mkdir -p /app/logs /app/staticfiles /app/media && \
    chown -R nexus:nexus /app/logs /app/staticfiles /app/media

# Switch to non-root user
USER nexus

# Collect static files (if needed in build)
# RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/schema/ || exit 1

# Default command: Run with Granian (Rust-based high-performance server)
CMD ["granian", "config.wsgi:application", \
     "--interface", "wsgi", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--blocking-threads", "4", \
     "--access-log"]
