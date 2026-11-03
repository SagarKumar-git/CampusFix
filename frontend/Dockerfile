# ==============================================================================
# CampusFix — Production Frontend Multi-Stage Dockerfile
# ==============================================================================
# Multi-stage build producing a hardened, non-root Nginx static file container.
#
# Stage 1 (Builder):
#   - Node.js LTS (Alpine) environment.
#   - Deterministic dependency installation via npm ci with package-lock.json.
#   - Compiles TypeScript and builds optimized production bundle via Vite.
#   - Configurable API Base URL via build argument VITE_API_BASE_URL.
#
# Stage 2 (Runtime):
#   - Lightweight Alpine Nginx image (zero Node.js or dev tooling).
#   - Custom unprivileged Nginx configuration with SPA fallback routing.
#   - Non-root runtime user (nginx, UID 101).
#   - Hardened security and cache headers.
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build Vite Production Assets
# ------------------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies using clean package-lock.json installation
COPY package.json package-lock.json ./
RUN npm ci

# Copy project source files and build configurations
COPY tsconfig.json vite.config.ts tailwind.config.js postcss.config.js index.html ./
COPY src/ src/

# Build argument for API base URL (inlined into Vite bundle at compile time)
# Defaults to relative /api/v1 for same-origin reverse proxy routing
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Run TypeScript compilation check and Vite production bundle build
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Hardened, Non-Root Nginx Runtime
# ------------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# Remove default boilerplate configurations and assets
RUN rm -rf /etc/nginx/conf.d/* /usr/share/nginx/html/*

# Copy custom unprivileged Nginx main configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy compiled static distribution files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Configure directory ownership and permissions for unprivileged execution
RUN touch /tmp/nginx.pid && \
    chown -R nginx:nginx /tmp/nginx.pid \
                         /var/log/nginx \
                         /usr/share/nginx/html

# Switch to unprivileged runtime user
USER nginx

# Expose unprivileged web server port
EXPOSE 8080

# Container liveness check using native busybox wget
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:8080/health || exit 1

# Start Nginx in foreground mode
CMD ["nginx", "-g", "daemon off;"]
