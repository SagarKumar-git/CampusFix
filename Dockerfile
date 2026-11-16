# ==============================================================================
# CampusFix — Unified Production Multi-Stage Dockerfile (Render Free Tier)
# ==============================================================================
# Single-container architecture combining:
#   - React SPA (Nginx static asset delivery & reverse proxy gateway)
#   - FastAPI REST API (Uvicorn ASGI server binding strictly to 127.0.0.1:8000)
#
# Process Management:
#   - Nginx listens on dynamic $PORT (default: 8080) and proxies /api/ to loopback.
#   - Both processes execute as unprivileged non-root user (UID 10001: campusfix).
#   - Managed by entrypoint supervisor with fail-fast process monitoring & SIGTERM handling.
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build Frontend Vite Assets
# ------------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder

WORKDIR /build/frontend

# Install dependencies using clean package-lock.json installation
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy frontend source files and build configurations
COPY frontend/tsconfig.json frontend/vite.config.ts frontend/tailwind.config.js frontend/postcss.config.js frontend/index.html ./
COPY frontend/src/ src/

# Build argument for API base URL (inlined into Vite bundle at compile time)
# Default is /api/v1 for same-origin proxying through Nginx
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Run TypeScript compilation and build production assets
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Build Backend Virtual Environment & Wheels
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS backend-builder

WORKDIR /build/backend

# Install build prerequisites for native C extensions (asyncpg, argon2-cffi)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Create virtual environment and upgrade packaging tools
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy packaging configuration and package source
COPY backend/pyproject.toml .
COPY backend/app/ app/

# Install application dependencies into isolated venv
RUN /opt/venv/bin/pip install --no-cache-dir .

# ------------------------------------------------------------------------------
# Stage 3: Unified Production Runtime (Hardened, Non-Root)
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Install Nginx, curl, and procps (process management tools)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        nginx \
        curl \
        procps && \
    rm -rf /var/lib/apt/lists/*

# Set operational environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/backend" \
    PORT=8080

WORKDIR /app/backend

# Create dedicated non-root user and group
RUN groupadd -g 10001 campusfix && \
    useradd -u 10001 -g campusfix -s /bin/sh -d /app -M campusfix

# Setup directory structure and permissions for unprivileged execution
RUN rm -rf /etc/nginx/conf.d/* /etc/nginx/sites-enabled/* /var/www/html/* /usr/share/nginx/html/* && \
    mkdir -p /app/backend /usr/share/nginx/html /var/log/nginx /var/lib/nginx \
             /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp && \
    ln -sf /dev/stdout /var/log/nginx/access.log && \
    ln -sf /dev/stderr /var/log/nginx/error.log && \
    chown -R campusfix:campusfix /app /usr/share/nginx/html /var/log/nginx /var/lib/nginx /tmp

# Copy compiled virtual environment from backend-builder
COPY --from=backend-builder --chown=campusfix:campusfix /opt/venv /opt/venv

# Copy compiled frontend assets from frontend-builder
COPY --from=frontend-builder --chown=campusfix:campusfix /build/frontend/dist /usr/share/nginx/html

# Copy backend application code, Alembic migrations, and configuration
COPY --chown=campusfix:campusfix backend/app/ /app/backend/app/
COPY --chown=campusfix:campusfix backend/alembic/ /app/backend/alembic/
COPY --chown=campusfix:campusfix backend/alembic.ini /app/backend/alembic.ini
COPY --chown=campusfix:campusfix backend/pyproject.toml /app/backend/pyproject.toml

# Copy Nginx template and supervisor entrypoint scripts
COPY --chown=campusfix:campusfix docker/nginx.conf.template /etc/nginx/nginx.conf.template
COPY --chown=campusfix:campusfix docker/entrypoint.py /app/entrypoint.py
COPY --chown=campusfix:campusfix docker/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.py /app/entrypoint.sh

# Switch to unprivileged runtime user
USER campusfix:campusfix

# Default dynamic port exposed (overridden at runtime by Render $PORT)
EXPOSE 8080

# Container healthcheck: tests Nginx and backend end-to-end via loopback
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, os; p=os.environ.get('PORT', '8080'); urllib.request.urlopen(f'http://127.0.0.1:{p}/healthz')" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
