# Deployment Strategy & Operational Runbooks — CampusFix

| Document Version | 1.2.0 |
| :--- | :--- |
| **Status** | Approved Baseline (Phase 5: Deployment Engineering & Staging Plan) |
| **Maintainer** | DevOps Lead & Systems Architect |
| **Last Updated** | 2026-11-03 (UTC) |

---

## 1. Hosting Architecture & Infrastructure Topology

CampusFix is engineered for cloud-native deployment with zero complex infrastructure requirements (no Kubernetes, Redis, or microservices needed for MVP).

```mermaid
graph LR
    subgraph Users ["End Users"]
        Browser["Desktop & Mobile Browsers"]
    end

    subgraph CDN_Edge ["Edge Delivery"]
        VercelEdge["Vercel Edge CDN (Static Assets)"]
    end

    subgraph Compute ["Application Compute (PaaS / Docker)"]
        FastAPI_App["FastAPI Service (Uvicorn / Gunicorn)"]
    end

    subgraph Database_Managed ["Managed Persistence"]
        PostgreSQL["Managed PostgreSQL 15+ (SSL Enforced)"]
    end

    Browser -->|Static HTML/JS/CSS| VercelEdge
    Browser -->|REST API / HTTPS| FastAPI_App
    FastAPI_App -->|Async SQLAlchemy (SSL)| PostgreSQL
```

| Tier | Target Platform | Deployment Artifact | Scaling Characteristics |
| :--- | :--- | :--- | :--- |
| **Frontend** | Vercel / Netlify / Cloudflare Pages / Docker Nginx | Static single-page assets (`frontend/dist`) | Globally distributed edge CDN or unprivileged Nginx container. |
| **Backend** | Render / Railway / Fly.io / Container PaaS | OCI Docker Image / Python 3.11 virtualenv | Stateless web instances running Uvicorn workers behind Gunicorn. |
| **Database** | Managed PostgreSQL (Neon, Render, Supabase, AWS RDS) | Relational SQL database with point-in-time backups | Minimum 1 vCPU, 1GB RAM, automated daily snapshots. |

---

## 2. Environment Configuration Specifications

### 2.1 Backend Environment Variables (`backend/.env`)

| Variable | Type | Default / Example | Purpose |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | String | `development` / `production` | Controls logging verbosity, Swagger docs, and cookie security flags. |
| `DATABASE_URL` | String | `postgresql+asyncpg://user:pass@localhost:5432/campusfix` | Async SQLAlchemy database connection string. |
| `SECRET_KEY` | String | *(64-character random hex string)* | Secret key for signing JWT access and refresh tokens. |
| `ALGORITHM` | String | `HS256` | JWT signing algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Integer | `15` | Expiry duration for short-lived access tokens. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Integer | `7` | Expiry duration for refresh token cookie. |
| `ALLOWED_ORIGINS` | String | `http://localhost:5173,https://campusfix.vercel.app` | Comma-separated CORS allowed origins. |
| `LOG_LEVEL` | String | `INFO` | Application log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

### 2.2 Frontend Environment Variables (`frontend/.env`)

| Variable | Type | Default / Example | Purpose |
| :--- | :--- | :--- | :--- |
| `VITE_API_BASE_URL` | String | `http://localhost:8000/api/v1` | Base URL for REST API requests. |

---

## 3. Database Migration Deployment Protocol

Under no circumstances should the backend application attempt to generate or alter production database tables on startup.

### Pre-Deployment Migration Runbook:
1. **Migration Verification**: In CI, verify that all migration scripts apply cleanly against an ephemeral PostgreSQL database:
   ```bash
   alembic upgrade head
   alembic downgrade -1
   alembic upgrade head
   ```
2. **Release Phase Execution**: In PaaS environments (such as Render or Railway), migrations are executed as a dedicated release command prior to routing traffic to new application instances:
   ```bash
   alembic upgrade head
   ```
3. **Rollback Protocol**: If a migration fails, the deployment halts before traffic cutover. If a rollback is necessary:
   ```bash
   alembic downgrade <target_revision>
   ```

---

## 4. Health Probes & Monitoring

The backend exposes two standard operational health probes in `backend/app/main.py`:

1. **Liveness Probe (`GET /healthz`)**:
   - **Purpose**: Kubernetes / PaaS container liveness checking. Confirms the Python/FastAPI process is responsive and event loop is running.
   - **Dependency**: Zero external dependencies (does not depend on database or cache availability).
   - **Response**: HTTP 200 OK:
     ```json
     { "status": "healthy" }
     ```
   - **Failure Behavior**: If the process hangs, crashes, or is deadlocked, container orchestrators fail the liveness check and restart the container.

2. **Readiness Probe (`GET /readyz`)**:
   - **Purpose**: Kubernetes / PaaS traffic-routing readiness checking. Confirms the application can successfully query the operational PostgreSQL database.
   - **Implementation**: Executes a lightweight `SELECT 1` query via the existing asynchronous SQLAlchemy session provider (`get_db`), ensuring connection pool re-use without spawning redundant engines.
   - **Success Response**: HTTP 200 OK:
     ```json
     { "status": "ready", "database": "connected" }
     ```
   - **Failure Response**: HTTP 503 Service Unavailable:
     ```json
     { "status": "unhealthy", "database": "unreachable" }
     ```
   - **Security & Data Sanitization**: If database connectivity fails (timeout, authentication failure, network partition, pool exhaustion), internal exception messages, database URLs, credentials, hostnames, and SQL tracebacks are strictly suppressed. Only the sanitized HTTP 503 JSON payload is returned.
   - **Test Verification**: Verified by unit test suite in `backend/tests/unit/test_health_probes.py` (5 tests covering 200 OK, DB failure 503, liveness DB-independence, and zero credential leakage).

---

## 5. Production Docker Containerization & Orchestration

Hardened, multi-stage, rootless OCI container configurations are implemented for backend, frontend, and local integration orchestration.

### 5.1 Backend Container Architecture (`backend/Dockerfile`)
- **Base Image**: `python:3.11-slim` (official minimal Debian-slim image).
- **Stage 1 (Builder)**: Installs build prerequisites (`build-essential`, `libpq-dev`), provisions an isolated virtual environment at `/opt/venv`, and pre-compiles wheels for production dependencies defined in `backend/pyproject.toml`.
- **Stage 2 (Runtime)**: Copies `/opt/venv` into a clean runtime layer. Does not retain compilers, package caches, or dev dependencies.
- **Unprivileged User**: Runs as non-root system user `campusfix` (UID `10001`, GID `10001`).
- **Execution Settings**: `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, `PYTHONFAULTHANDLER=1`.
- **Exposed Port**: `8000`.
- **Server**: Exec form `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]` guaranteeing direct `SIGTERM` signal reception for graceful shutdown (draining connection pools).
- **No Automatic Migrations**: Container startup exclusively launches the ASGI application. Migrations must be run via release phase command or explicit container task.
- **Liveness Healthcheck**: Native standard library probe `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"` (zero external dependencies).

### 5.2 Frontend Container Architecture (`frontend/Dockerfile`)
- **Stage 1 (Builder)**: `node:20-alpine`. Executes deterministic dependency resolution (`npm ci` against `package-lock.json`), injects `ARG VITE_API_BASE_URL`, and compiles production distribution files to `/app/dist` (`tsc --noEmit && vite build`).
- **Stage 2 (Runtime)**: `nginx:1.27-alpine`. Lightweight static asset web server. Completely eliminates Node.js and devDependencies from the final container.
- **Configuration (`frontend/nginx.conf`)**:
  - Listens on unprivileged port `8080`.
  - Runs as unprivileged user `nginx` (UID `101`).
  - Hardened non-root write paths: Configures `pid /tmp/nginx.pid;` and temp paths under `/tmp/*_temp` for unprivileged write safety across restricted container runtimes.
  - SPA Fallback: `try_files $uri $uri/ /index.html;` ensures client-side routes (e.g. `/student/tickets`, `/tickets/:id`, `/admin/categories`) resolve cleanly.
  - Content Caching: Immutable 1-year cache (`Cache-Control: public, max-age=31536000, immutable`) for hashed `/assets/` files; `no-cache, no-store, must-revalidate` for `index.html`.
  - Security Headers: `X-Frame-Options "DENY"`, `X-Content-Type-Options "nosniff"`, `Referrer-Policy "strict-origin-when-cross-origin"`, `Permissions-Policy`.
  - Health Endpoint: `GET /health` returning HTTP 200 `healthy`.

### 5.3 Local Integration Orchestration (`docker-compose.yml`)
- **Services**:
  1. `postgres`: PostgreSQL 15 (`postgres:15-alpine`). Bound strictly to `127.0.0.1:${POSTGRES_PORT:-5432}:5432` and isolated on `campusfix-internal` bridge network. Healthcheck via `pg_isready`.
  2. `backend`: Built from `./backend/Dockerfile`. Depends on `postgres (service_healthy)`. Exposes `127.0.0.1:8000:8000`. Healthcheck via `/healthz`.
  3. `frontend`: Built from `./frontend/Dockerfile`. Depends on `backend (service_healthy)`. Exposes `127.0.0.1:8080:8080`. Healthcheck via `/health`.
- **Database Migrations Protocol**:
  Migrations are strictly manual. To apply schema migrations against the compose database:
  ```bash
  docker compose run --rm backend alembic upgrade head
  ```

### 5.4 Build & Execution Reference Runbook

#### A. Standalone Backend Container
```bash
# Build backend image
docker build -t campusfix-backend:latest ./backend

# Run backend container
docker run -d \
  --name campusfix-backend \
  -p 127.0.0.1:8000:8000 \
  -e ENVIRONMENT=development \
  -e DATABASE_URL=postgresql+asyncpg://campusfix_user:password@host.docker.internal:5432/campusfix \
  -e SECRET_KEY=$(openssl rand -hex 32) \
  campusfix-backend:latest
```

#### B. Standalone Frontend Container
```bash
# Build frontend image with customized API target
docker build \
  --build-arg VITE_API_BASE_URL=http://localhost:8000/api/v1 \
  -t campusfix-frontend:latest ./frontend

# Run frontend container
docker run -d \
  --name campusfix-frontend \
  -p 127.0.0.1:8080:8080 \
  campusfix-frontend:latest
```

#### C. Local Multi-Container Stack (Docker Compose)
```bash
# 1. Initialize environment template
cp .env.docker.example .env

# 2. Build and start services in background
docker compose up -d --build

# 3. Check service health status
docker compose ps

# 4. Apply initial database migrations
docker compose run --rm backend alembic upgrade head

# 5. Stop services and preserve persistent database volume
docker compose down
```


---

## 6. Same-Origin Reverse Proxy & Edge Routing Architecture

To eliminate cross-site cookie attenuation and ensure seamless refresh token rotation, CampusFix enforces a **Same-Origin Reverse Proxy Architecture**. Both the React Single Page Application and the FastAPI REST API operate under a single browser origin.

### 6.1 The Cross-Site Cookie Attenuation Problem
- The refresh token cookie is configured with `HttpOnly=True`, `Path=/api/v1/auth`, and `SameSite=Lax`.
- Under standard browser security models, if the frontend and backend reside on differing domains (e.g., `campusfix.vercel.app` and `api.onrender.com`), browsers treat fetch requests as third-party cross-site requests.
- Browsers do **not** send `SameSite=Lax` cookies on cross-site `POST` requests (such as silent renewal calls to `POST /api/v1/auth/refresh`).
- Forcing `SameSite=None` weakens CSRF posture and requires third-party cookie permissions, which modern browsers (Safari ITP, Chrome Privacy Sandbox, Firefox ETP) block by default.

### 6.2 The Same-Origin Solution
By routing all traffic through an edge reverse proxy or unified gateway:
- **Browser-facing origin**: `https://campusfix.university.edu` (or `http://localhost:8080` in local Docker).
- **Static Assets & SPA**: Routed to compiled Vite React files with client-side fallback (`/` -> `index.html`).
- **REST API Operations**: Routed directly to FastAPI backend (`/api/*` -> `http://backend:8000/api/*`).
- **Operational Probes**: Routed to FastAPI liveness and readiness probes (`/healthz`, `/readyz`).
- **Cookie Mechanics**: Because all API calls target `/api/v1/*` on the *same origin*, the browser treats `Set-Cookie` and subsequent requests as first-party requests. `SameSite=Lax` cookies are attached automatically to `POST /api/v1/auth/refresh`.

```mermaid
graph TD
    Browser["End-User Browser<br/>Origin: https://campusfix.university.edu"]

    subgraph Edge_Gateway ["Same-Origin Reverse Proxy (Nginx / Edge CDN)"]
        Router{"Route Matcher"}
        SPA["Static Asset Handler<br/>(React SPA Dist)"]
        API_Proxy["Reverse Proxy Pass<br/>(Header & Cookie Forwarding)"]
    end

    subgraph Internal_Network ["Internal Private Network (No Public Ingress)"]
        FastAPI["FastAPI Backend<br/>(Uvicorn on Port 8000)"]
        PostgreSQL["PostgreSQL 15 Database"]
    end

    Browser -->|Request| Router
    Router -->|/, /assets/*, /student/*, /tickets/*| SPA
    Router -->|/api/*, /healthz, /readyz| API_Proxy
    API_Proxy -->|Internal HTTP/1.1 Keepalive| FastAPI
    FastAPI -->|Async SQLAlchemy (SELECT 1)| PostgreSQL
```

### 6.3 Architectural Comparison & Trade-Offs

| Evaluation Criterion | Option A: Containerized Nginx Gateway (Recommended) | Option B: Vercel Edge Rewrites |
| :--- | :--- | :--- |
| **Origin Topology** | 100% same-origin at protocol, host, and port. | Virtual same-origin managed by Vercel edge edge workers. |
| **Backend Ingress** | Backend container is **completely private** inside Docker network; zero public exposure required. | Backend API must be publicly reachable on the open internet for Vercel edge to proxy. |
| **Timeout Limits** | Fully configurable in Nginx (`proxy_read_timeout 60s`). | Strict 10s–30s timeout on Vercel hobby/pro plans; risks terminating long operations. |
| **Latency Profile** | Single internal hop (< 1ms container network latency). | Double-hop over public internet: Client -> Vercel Edge -> Cloud PaaS -> Edge -> Client. |
| **Vendor Independence** | Cloud-agnostic: runs identically on AWS ECS, GCP Cloud Run, Docker Compose, Kubernetes, VMs. | Tied to Vercel platform and deployment routing syntax. |

### 6.4 Implementation Configurations

#### A. Containerized Nginx Reverse Proxy (`frontend/nginx.conf`)
- Mounted in frontend container listening on unprivileged port `8080`.
- Defines `upstream backend_api { server backend:8000; keepalive 32; }`.
- Proxies `/api/` with preserved `$request_uri` paths, forwarding `Host`, `X-Real-IP`, `X-Forwarded-For`, and `X-Forwarded-Proto`.
- Preserves `Set-Cookie` response headers without modification.
- Health probes `/healthz` and `/readyz` routed to FastAPI backend.

#### B. Vercel Serverless Edge Rewrites (`frontend/vercel.json`)
- For teams deploying the frontend on Vercel and the backend on a container PaaS.
- Configures explicit path rewrites:
  - `/api/(.*)` $\to$ `https://api.campusfix.university.edu/api/$1`
  - `/healthz` $\to$ `https://api.campusfix.university.edu/healthz`
  - `/readyz` $\to$ `https://api.campusfix.university.edu/readyz`
  - `/(.*)` $\to$ `/index.html` (SPA fallback)
- Inlines security headers (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`).


---

## 7. Production PostgreSQL Readiness, Provider Comparison & Administrator Bootstrapping Design

### 7.1 Managed PostgreSQL Provider Evaluation

| Dimension | Neon (Serverless PostgreSQL) | Render Managed PostgreSQL | AWS RDS PostgreSQL (`db.t4g.micro`) |
| :--- | :--- | :--- | :--- |
| **Pricing (Dev / Pilot)** | **Free Tier**: 0.5 GB storage, shared vCPU, $0/mo. | **Starter**: $7/mo (256 MB RAM, 1 GB storage). Free tier expires in 30 days. | **AWS Free Tier**: 750 hrs/mo `db.t4g.micro` + 20 GB gp3 free for 12 months. |
| **Pricing (Production)** | **Launch Tier**: $19/mo base + compute/storage on-demand. | **Standard**: $20/mo (1 GB RAM, 10 GB storage, daily backups). | **On-Demand**: ~$15/mo (compute + storage) for single-AZ; ~$30/mo Multi-AZ. |
| **Global Regions** | AWS us-east-1, us-east-2, eu-central-1, ap-southeast-1. | US Oregon, US Ohio, Frankfurt, Singapore. | 30+ AWS regions (e.g. us-east-1, ap-south-1 Mumbai, eu-west-1). |
| **PostgreSQL Compatibility** | PostgreSQL 15, 16, 17 supported. | PostgreSQL 15, 16 supported. | PostgreSQL 14, 15, 16, 17 supported. |
| **SSL/TLS Enforcement** | Strictly enforced (`?ssl=require`). Plaintext rejected. | Supported; SSL parameters provided in connection string. | Enforceable via Parameter Group (`rds.force_ssl=1`). |
| **Connection Limits & Pooling** | Up to 10,000 connections via built-in PgBouncer pooler (port 6543) or 100 direct (port 5432). | 97 max connections on Starter; optional pooler on paid plans. | ~100 max connections on `db.t4g.micro`. RDS Proxy available. |
| **Backups & PITR** | Continuous WAL archiving; 7-day PITR on free/launch tier. Zero-copy database branching. | Daily automated backups with 7-day retention on $20/mo plan. PITR requires $35/mo. | Automated continuous backups with 1–35 day retention. PITR to any 5-minute interval. |
| **Restore Speed** | Instant (< 5 seconds via zero-copy branch restore). | 5–15 minutes (restore from daily snapshot). | 5–15 minutes (restore to new RDS instance). |
| **Operational Recommendation** | **Primary Recommendation for Pilot & MVP**: Zero infrastructure overhead, instant branching for migration testing, $0 dev cost. | **Best if web service is on Render**: Colocated compute/DB eliminates egress and latency. | **Best for Institutional AWS Accounts**: Highest enterprise compliance and existing university credit utilization. |

### 7.2 Database Connection & Security Audit Findings
- **Driver Enforced**: Async SQLAlchemy requires `postgresql+asyncpg://`. Plain `postgresql://` is rejected at startup by `Settings.validate_async_db_url()`.
- **SSL Connection**: Cloud databases require SSL. Append `?ssl=require` to `DATABASE_URL`. Verified that `asyncpg` handshakes TLS and SQLAlchemy parses parameters cleanly.
- **Credential Masking**: All diagnostic logs use `Settings.masked_database_url`, which automatically redacts passwords (`***`).
- **Connection Pool Sizing**:
  - `DB_POOL_SIZE = 10`
  - `DB_MAX_OVERFLOW = 20`
  - `DB_POOL_TIMEOUT = 30.0s`
  - `DB_POOL_RECYCLE = 1800s` (30 min)
  - `DB_POOL_PRE_PING = True` (detects stale sockets from cloud idle disconnects)
  - Up to 30 connections per worker; safely within cloud limits (Neon 100+, Render 97, AWS 100).
- **Migration Engine**: `backend/alembic/env.py` uses `pool.NullPool`, preventing connections from lingering after release migrations.

### 7.3 Production Migration & Recovery Runbook

1. **Baseline Migration**: Revision `0c98aec98ce5` (`create_initial_schema`) creates 5 tables (`users`, `categories`, `tickets`, `ticket_status_history`, `refresh_tokens`), 10 indexes, and all check constraints.
2. **Pre-Migration Snapshot**:
   - Before applying any production migration:
     - Neon: `neon branches create pre-mig-$(date +%Y%m%d%H%M)`
     - AWS RDS: `aws rds create-db-snapshot --db-instance-identifier campusfix-prod --db-snapshot-identifier pre-mig-$(date +%Y%m%d%H%M)`
3. **Execution as Isolated Release Task**:
   - Run before routing traffic to new web instances:
     ```bash
     alembic upgrade head
     ```
   - Never execute auto-migrations inside application startup.
4. **Post-Migration Verification**:
   - Check current revision: `alembic current` (must report head `0c98aec98ce5`).
   - Query readiness probe: `GET /readyz` (must return HTTP 200 `{"status": "ready", "database": "connected"}`).
5. **Rollback & Disaster Recovery**:
   - `alembic downgrade` permanently drops tables and must **never** be executed on populated production databases.
   - If a migration corrupts data, immediately restore the database instance from the pre-migration snapshot or PITR timestamp.

### 7.4 Initial Administrator Provisioning CLI (`backend/app/scripts/bootstrap_admin.py`)

A clean production database contains zero initial accounts. Because the public registration endpoint (`POST /api/v1/auth/register`) strictly assigns the `STUDENT` role, initial administrative accounts must be provisioned out-of-band via the dedicated CLI tool.

#### CLI Command Specification
```bash
# Provisioning initial administrator (prompts for masked password with confirmation)
python -m app.scripts.bootstrap_admin --email "admin@university.edu" --full-name "Campus Facilities Lead"

# Promoting an existing student or staff member with explicit interactive confirmation
python -m app.scripts.bootstrap_admin --email "staff@university.edu" --full-name "Promoted Staff" --promote-existing
```

#### CLI Flags & Options:
- `--email <email>` *(Required)*: Institutional email address; validated against RFC 5322 format and normalized to lowercase.
- `--full-name <name>` *(Required)*: Display name for the administrator.
- `--promote-existing`: Explicitly permits promoting an existing `STUDENT` or `STAFF` account to `ADMINISTRATOR`. Refuses by default without this flag.

> [!IMPORTANT]
> Unapproved flags such as `--update-password`, `-y`, and `--yes` are strictly rejected by the CLI parser. Automated or non-interactive confirmation bypasses are prohibited.

#### Security Safeguards & Rules:
1. **Interactive Masked Password Entry Only**: The CLI prompts interactively via `getpass.getpass()` with double-entry confirmation. Plaintext passwords cannot be supplied via flags, environment variables (e.g. `ADMIN_INITIAL_PASSWORD` is ignored/unsupported), or configuration files.
2. **Zero Default Passwords**: Rejects empty inputs, common defaults (`admin12345!`, `password123!`, `campusfix123!`, `changeme`), and credentials shorter than 12 characters.
3. **Password Complexity**: Requires minimum 12 characters (max 128), at least 1 uppercase letter, 1 lowercase letter, 1 digit, and 1 special character.
4. **Argon2id Hashing**: Hashes passwords using standard RFC 9106 parameters (65,536 KiB memory cost, 3 iterations, 4 lanes). Never stores plaintext passwords.
5. **Credential Secrecy**: The CLI never echoes, prints, or logs passwords. Passwords never appear in stdout, stderr, logs, exception messages, or return structures.
6. **Existing Administrator Immutability**:
   - If user exists and is already an active `ADMINISTRATOR`, the script safely returns `ALREADY_ADMIN` (exit code 0) without modifying any user field, profile details, or password hash.
   - The CLI cannot be used to overwrite, reset, or alter an existing administrator's credentials.
7. **Strict Interactive Promotion**:
   - If user exists as `STUDENT` or `STAFF`, promotion is refused by default (`REFUSED`).
   - If `--promote-existing` is supplied, an interactive TTY confirmation is strictly required. The operator must type **exactly `yes`**.
   - Any other input (`y`, `YES`, `Yes`, empty string, EOF) immediately aborts the operation (`CANCELLED`, exit code 1).
   - Non-interactive execution (e.g., piped input or non-TTY) is blocked from promoting accounts.
   - During promotion, only the `role` field is modified to `ADMINISTRATOR`; all other profile fields (`full_name`, `hashed_password`, `is_active`) remain strictly untouched.
8. **Database Target Safety & Cleanup**:
   - Before executing any database transaction, the CLI prints the target environment and safely masked database URL (`Settings.masked_database_url`).
   - If `ENVIRONMENT=production` or if the database host is remote (not `localhost`, `127.0.0.1`, or `::1`), execution is immediately blocked. Targeting production or remote databases requires separate explicit project-owner approval; no bypass flag exists.
   - The database engine is explicitly disposed (`close_db_engine()`) in a `finally` block on all exit paths.
   - Operations run in an atomic transaction with automatic `db.rollback()` upon failure.

---

## 8. Phase 5.6 Staging Deployment Protocol & Operational Verification

For complete details regarding the sequential staging release runbook, environment selection, and test scenarios, see [PROJECT_STATUS.md §13](file:///c:/Sagar%20Project/CampusFix/docs/PROJECT_STATUS.md#13-phase-56-staging-deployment--release-verification-plan).

### 8.1 Staging Architecture & Cost Projections
- **Target Architecture**: Single-origin container stack (Nginx Gateway on port 8080 + FastAPI Backend on port 8000) deployed on Render Web Service or Railway, connected to Neon Serverless PostgreSQL (`campusfix_staging`) with SSL required (`?ssl=require`).
- **Estimated Operational Costs (Planning Estimates Only)**:
  - Neon Serverless PostgreSQL: $0.00 / month (Free tier).
  - Container Compute (Web Service): $7.00 / month (Render Starter) or $5.00 / month (Railway Hobby).
  - Ingress & TLS: $0.00 (Let's Encrypt automated TLS via PaaS Edge).
  - **Total Estimated Staging Cost**: ~$0.00 to $7.00 / month.

### 8.2 Execution Order & Rollback Protocol
1. **Snapshot**: Create zero-copy branch `neon branches create pre-staging-0c98aec98ce5`.
2. **Migration**: Run `alembic upgrade head` as an isolated pre-cutover release task. (No startup auto-migrations).
3. **Health Verification**: Verify `GET /readyz` returns HTTP 200 `{"status": "ready", "database": "connected"}`.
4. **Administrator Provisioning**: Execute `python -m app.scripts.bootstrap_admin --email "<staging_admin_email>" --full-name "<name>"` with interactive masked password.
5. **Rollback**: If migration fails, execute `neon branches restore pre-staging-0c98aec98ce5`. `alembic downgrade` is strictly prohibited on populated staging databases.

> [!CAUTION]
> **GOVERNANCE BOUNDARY**: Phase 5.6 execution is currently halted. Do not provision infrastructure, run migrations, or deploy containers without explicit Project Owner sign-off.
