# ==============================================================================
# CampusFix — Production Backend Multi-Stage Dockerfile
# ==============================================================================
# Multi-stage build producing a hardened, non-root Python 3.11 container.
#
# Stage 1 (Builder):
#   - Installs build tools and compilers.
#   - Creates an isolated virtual environment in /opt/venv.
#   - Installs bounded production dependencies without dev dependencies.
#
# Stage 2 (Runtime):
#   - Lean python:3.11-slim base image (zero build toolchain, minimal attack surface).
#   - Copies pre-compiled virtual environment from builder.
#   - Runs as an unprivileged, non-root user (UID 10001: campusfix).
#   - Does NOT run database migrations automatically on startup.
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build virtual environment and wheels
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install minimal build prerequisites for native C extensions (e.g. asyncpg, argon2-cffi)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy packaging configuration and package source for dependency installation
COPY pyproject.toml .
COPY app/ app/

# Install application dependencies into the isolated virtual environment
RUN /opt/venv/bin/pip install --no-cache-dir .

# ------------------------------------------------------------------------------
# Stage 2: Hardened, Non-Root Production Runtime
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Set operational environment variables for predictable Python execution
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app"

WORKDIR /app

# Create dedicated non-root system group and user, ensuring working directory ownership
RUN groupadd -g 10001 campusfix && \
    useradd -u 10001 -g campusfix -s /bin/sh -d /app -M campusfix && \
    chown -R campusfix:campusfix /app

# Copy virtual environment from builder stage
COPY --from=builder --chown=campusfix:campusfix /opt/venv /opt/venv

# Copy application code, Alembic configuration, and migrations
COPY --chown=campusfix:campusfix app/ /app/app/
COPY --chown=campusfix:campusfix alembic/ /app/alembic/
COPY --chown=campusfix:campusfix alembic.ini /app/alembic.ini
COPY --chown=campusfix:campusfix pyproject.toml /app/pyproject.toml

# Switch to unprivileged runtime user
USER campusfix

# Expose FastAPI application port
EXPOSE 8000

# Container liveness probe via native standard library (does not require external curl)
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"]

# Execute ASGI server with signal propagation for graceful shutdown
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
