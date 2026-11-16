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

### 8.1 Owner-Approved Staging Architecture & Free-Tier Planning Baseline

Following updated Project Owner review and direction, the staging hosting strategy has been aligned to a **Free-Tier Target ($0/month)** to deploy and validate CampusFix without recurring hosting costs:

* **Immediate Objective**: Deploy and test CampusFix staging end-to-end on zero-cost infrastructure tiers without an active monthly hosting subscription.
* **Compute Platform**: **Render Free Tier** (Web Services).
* **Managed Persistence**: **Neon Serverless PostgreSQL (Free Tier)** (isolated database `campusfix_staging`, SSL enforced via `?ssl=require`).
* **Ingress & Staging Domain**: **Default Render PaaS Domain** (e.g. `https://campusfix-staging.onrender.com`), utilizing Render's automated TLS certificate termination. No custom domain or institutional DNS CNAME records required.
* **Proposed Initial Staging Administrator**: `kumarsagar77283@gmail.com` (Display Name: "Campus Facilities Lead").
* **Monthly Hosting Budget**: **$0.00 / month target**.
  > [!IMPORTANT]
  > **Free-Tier Budget Disclaimer**: The $0.00/month target assumes operation entirely within provider free tiers (Render Free Web Services and Neon Free Serverless PostgreSQL). Actual charges may occur if usage exceeds free allocations (e.g., outbound bandwidth beyond Render's 5 GB/month allowance at $0.15/GB, build time over 500 minutes/month, or Neon storage exceeding 0.5 GB), or if provider terms, taxes, or pricing policies change. All quotas must be monitored during testing.
* **Future Upgrade Path**: The project retains the explicit option to upgrade the compute tier to **Render Starter ($7.00/month)** in the future when persistent 24/7 uptime, zero cold starts, and native internal private networking are required.

---

### 8.2 Render Free Tier Technical Evaluation & Architecture Alternatives

During pre-execution verification against Render's official infrastructure specifications, a key architectural restriction was identified:

> [!WARNING]
> **Render Free Tier Architectural Constraint**:
> 1. **Private Services Have No Free Tier**: Render Private Services (services without public internet access, communicating strictly via internal DNS) require a paid instance type starting at **Starter ($7/month)**.
> 2. **Free Web Services Cannot Receive Inbound Private Network Traffic**: On Render, Free Web Services can initiate outbound internal requests (e.g. to a database), but **cannot receive inbound traffic** over Render's private network from other services.

Because a free private backend service is unavailable on Render, the backend cannot simply be addressed as `campusfix-backend-staging:8000` on the private network at $0/month.

#### Evaluation of Safe Free-Tier Alternatives:

| Architecture Option | Description | Security & Cookie Posture | Limitations & Operational Trade-offs |
| :--- | :--- | :--- | :--- |
| **Option 2: Single Unified Staging Container on One Render Free Web Service** *(Selected Baseline — Implemented in Phase 5.6.1)* | Nginx and FastAPI combined in a single unprivileged container ([`Dockerfile`](file:///c:/Sagar%20Project/CampusFix/Dockerfile)) deployed as ONE Render Free Web Service. Nginx listens on public dynamic `$PORT` (default: 8080) and reverse-proxies to FastAPI listening strictly on loopback `127.0.0.1:8000`. | **Maximum Isolation**: Backend listens only on loopback `127.0.0.1:8000` inside the container; **zero public internet exposure**. 100% same-origin cookie delivery (`HttpOnly=True`, `SameSite=Lax`, `Secure=True` via HTTPS). | Uses native lightweight Python supervisor ([`docker/entrypoint.py`](file:///c:/Sagar%20Project/CampusFix/docker/entrypoint.py)). Single ~50s cold start instead of cascading multi-service wake-up. |
| **Option 1: Two Render Free Web Services with Gateway Ingress Protection** *(Alternative / Superseded Free-Tier Split)* | Frontend Nginx is a Free Web Service (`https://campusfix-staging.onrender.com`). Backend FastAPI is a Free Web Service (`https://campusfix-backend-staging.onrender.com`). Nginx proxies `/api/*` to the backend over HTTPS. | **Secure Same-Origin**: Browser communicates with Nginx origin, but backend is exposed to public internet requiring custom `X-Gateway-Secret` header validation and CORS filtering. | **Cascading Cold Starts**: Both services spin down after 15 min idle. Waking both can take 50–100s. Shared 750 free compute hours/month across the workspace. Superseded by Option 2. |
| **Option 3: Future Upgrade to Render Starter ($7/mo)** | Frontend Web Service + Backend Private Service on Render's internal private network (`campusfix-backend-staging:8000`). | **Gold Standard**: Backend has no public URL; zero external attack surface; no cold starts; persistent 24/7 uptime. | Incurs US$7.00/month hosting fee. Retained as seamless upgrade path. |

#### Selected Free-Tier Implementation Strategy (Option 2 — Unified Container):
For the zero-cost ($0/month) staging deployment, **Option 2 (Single Unified Staging Container)** is the selected and implemented architecture:
* **Packaging**: Single root [`Dockerfile`](file:///c:/Sagar%20Project/CampusFix/Dockerfile) utilizing multi-stage builds:
  - Stage 1 (`frontend-builder`, `node:20-alpine`): Compiles TypeScript and builds Vite SPA assets to `/build/frontend/dist`.
  - Stage 2 (`backend-builder`, `python:3.11-slim`): Installs minimal build tools to compile native wheels into isolated `/opt/venv`.
  - Stage 3 (`runtime`, `python:3.11-slim`): Hardened runtime with Nginx and Uvicorn. Excludes all compilers, Node.js, and dev dependencies.
* **Process Topology & Network Isolation**:
  - **Nginx Web Server**: Serves React SPA static assets from `/usr/share/nginx/html` with SPA fallback (`try_files $uri $uri/ /index.html;`) and reverse-proxies `/api/` directly to FastAPI.
  - **FastAPI ASGI Backend**: Runs via `uvicorn app.main:app --host 127.0.0.1 --port 8000`, bound **strictly to local loopback**. It has zero public internet exposure; all external ingress is funneled through Nginx.
  - **Dynamic Port Ingress**: Render dynamically assigns `$PORT` at container runtime. At startup, the supervisor renders [`docker/nginx.conf.template`](file:///c:/Sagar%20Project/CampusFix/docker/nginx.conf.template) to `/tmp/nginx.conf` replacing `${PORT}` with `os.environ.get("PORT", "8080")`, verifies syntax via `nginx -t`, and binds Nginx to the assigned port.
* **Non-Root Execution & Supervision**:
  - Container executes under dedicated non-root user `campusfix:campusfix` (UID `10001`, GID `10001`).
  - Temporary and cache paths (`/tmp/client_temp`, `/tmp/proxy_temp`, `/tmp/nginx.pid`) are writeable by UID 10001.
  - Managed by [`docker/entrypoint.py`](file:///c:/Sagar%20Project/CampusFix/docker/entrypoint.py) (invoked via [`docker/entrypoint.sh`](file:///c:/Sagar%20Project/CampusFix/docker/entrypoint.sh)), providing:
    1. Pre-flight health probe verification (`http://127.0.0.1:8000/healthz`) before starting Nginx.
    2. Bounded graceful shutdown handling `SIGTERM` and `SIGINT` (10-second drain window before `SIGKILL`).
    3. Fail-fast child monitoring: if either Uvicorn or Nginx crashes, the supervisor immediately terminates the surviving process and exits with the failure exit code to prevent zombie 502 states.
* **Cookie & Security Posture**:
  - Full first-party origin alignment under the single Render staging domain (`https://campusfix-staging.onrender.com`).
  - Refresh cookie enforces `HttpOnly=True`, `SameSite=Lax`, `Path=/api/v1/auth`, and `Secure=True` in staging and production (`settings.is_cookie_secure`).
* **Superseded Option 1 Reference**:
  - The split two-service architecture (separate Frontend Web Service + Backend Web Service with `X-Gateway-Secret`) remains documented above as an alternative/fallback, but is superseded by the unified container to eliminate dual cold starts and backend public IP exposure.

---

### 8.3 Detailed Free-Tier Constraints & Operational Limitations

Operating on Render and Neon free tiers introduces operational characteristics that must be accounted for during smoke testing:

1. **Service Idling & Cold Starts (Render Free Web Services)**:
   * Free Web Services automatically spin down ("sleep") after **15 minutes of inactivity**.
   * When an HTTP request arrives at a sleeping service, Render wakes it up, causing an initial request latency of **50 to 100 seconds**.
   * In a two-service topology (Frontend + Backend), an initial user visit triggers a cascading wake-up (frontend wakes, then backend wakes), requiring patience during the first test interaction.
2. **Compute & Memory Quotas (Render Free Tier)**:
   * Each free service is limited to **512 MB RAM** and **0.1 CPU core**.
   * Memory leaks or heavy concurrent operations that exceed 512 MB will trigger out-of-memory (OOM) container termination.
   * Total free compute allowance is **750 hours/month per workspace**. Because free services sleep when idle, intermittent staging test sessions consume only a fraction of this limit. Continuous 24/7 uptime is not supported on the free tier.
3. **Bandwidth & Build Quotas (Render Free Tier)**:
   * **Outbound Bandwidth**: 5 GB/month included free ($0.15/GB overage).
   * **Build Minutes**: 500 pipeline minutes/month included.
4. **Interactive Shell Restrictions**:
   * Render Free tier does **not support SSH or interactive shell access** (`render exec`). All commands must run as web services, release commands, or one-off tasks.
5. **Database Quotas (Neon Free Tier)**:
   * **Storage**: 0.5 GB maximum active data storage.
   * **Compute**: Shared vCPU with automatic idle suspension after 5 minutes of inactivity (resumes in <500ms on incoming queries).
   * **Connections**: Up to 100 direct connections (10,000 via PgBouncer).
   * **Backups**: Continuous WAL archiving with 7-day Point-in-Time Recovery (PITR) and instant zero-copy branching included free.

---

### 8.4 Review of Vercel Edge Rewrites vs. Selected Render Gateway

In [frontend/vercel.json](file:///c:/Sagar%20Project/CampusFix/frontend/vercel.json), serverless edge rewrites are defined:
```json
{
  "source": "/api/:path*",
  "destination": "https://api.campusfix.university.edu/api/:path*"
}
```

**Why Vercel is NOT the Selected Staging Ingress**:
1. **Hardcoded Destination**: The rewrite destination hardcodes `https://api.campusfix.university.edu`, which is the intended future production domain and cannot resolve a staging PaaS backend.
2. **Multi-Vendor Operational Overhead**: A hybrid Vercel (frontend) + Render (backend) topology splits staging across two independent vendor dashboards, requiring double credential management, disparate monitoring, and dual-billing tracking.
3. **Double-Hop Internet Latency & Timeouts**: Requests from the client must traverse the public internet to Vercel's edge, hop across the open internet again to the backend PaaS, and return. Serverless edge workers impose strict execution limits (10s–30s on standard tiers), risking early termination of operational requests.
4. **Public Exposure Requirement**: Under Vercel edge rewrites, the backend compute must expose a public internet URL for Vercel to proxy to, increasing the attack surface.
5. **Single-Origin Superiority of Render**: By selecting Render with an Nginx gateway, proxy timeouts are fully governed by Nginx (`proxy_read_timeout 60s`), and all assets and API routes share a single Render-managed domain (`https://campusfix-staging.onrender.com`).

---

### 8.5 Staging Administrator Provisioning Protocol (Safety Guard Reconciliation)

The existing CLI tool ([backend/app/scripts/bootstrap_admin.py](file:///c:/Sagar%20Project/CampusFix/backend/app/scripts/bootstrap_admin.py)) enforces a strict database target safety check (`check_database_target_safety()`, lines 87–118) that restricts execution strictly to local loopback hosts (`localhost`, `127.0.0.1`, `::1`).

**Security Constraints & Principles**:
* The safety check intentionally blocks remote hosts to prevent accidental execution against cloud environments.
* **No Weakening or Bypasses**: No backdoor flags (`--force`, `--skip-safety`, `--yes`) will be introduced.
* **No False Tunnel Assumptions**: An SSH or proxy tunnel binding a remote Neon host to `127.0.0.1` does *not* make a remote database safe—it simply spoofs the loopback check while leaving the remote database vulnerable to operator error or targeted mistakes.

**Secure, Explicit, Independently Verifiable Staging Bootstrap Procedure**:
When the staging database is provisioned and ready for initial administration:
1. **Explicit Owner Authorization Token / Sign-Off**: The Project Owner must issue an explicit, recorded approval for provisioning the staging admin against `campusfix_staging`.
2. **Interactive Isolated Runner**: The script must be executed via an interactive, authenticated staging runner where `sys.stdin.isatty()` is true for masked double-entry password input via `getpass.getpass()`.
3. **Verified Staging Environment Guard**:
   * Prior to Phase 5.6 execution, a controlled, auditable authorization protocol will be reviewed: execution against non-loopback hosts will be permitted **strictly and exclusively** when:
     1. `settings.is_production` is verified `False` (`ENVIRONMENT=staging`).
     2. The target database name extracted from `DATABASE_URL` matches **exactly `campusfix_staging`**.
     3. An explicit command-line confirmation flag (e.g. `--allow-staging-db`) is supplied AND the operator interactively confirms the displayed target database hostname and masked URL.
4. **Preserved Invariants**:
   * Zero plaintext passwords in environment variables, arguments, or logs.
   * Mandatory password complexity ($\ge 12$ chars, uppercase, lowercase, digit, symbol, not in blacklist).
   * Argon2id hashing with standard RFC 9106 parameters.
   * Target admin email: `kumarsagar77283@gmail.com`.
   * Complete immutability of existing administrator records (`ALREADY_ADMIN` idempotent exit).
   * Guaranteed database engine disposal in a `finally` block.

---

### 8.6 Future Staging Deployment & Execution Sequence

When Phase 5.6 deployment authorization is granted, execution will strictly follow this 7-step sequence:

```mermaid
sequenceDiagram
    autonumber
    actor Owner as Project Owner
    actor Operator as Staging Operator
    participant Neon as Neon PostgreSQL
    participant Render as Render Platform
    participant App as CampusFix Application

    Owner->>Operator: 1. Formal Deployment Authorization ($0 Target)
    Operator->>Neon: 2. Create isolated free database: campusfix_staging
    Operator->>Neon: 3. Create baseline safety branch: pre-staging-0c98aec98ce5
    Operator->>Render: 4. Execute Release Task: alembic upgrade head
    Render->>Neon: Apply revision 0c98aec98ce5 (5 tables, 10 indexes)
    Operator->>Render: 5. Verify DB readiness: GET /readyz (returns 200 OK)
    Operator->>Render: 6. Interactive Bootstrap CLI (kumarsagar77283@gmail.com)
    Operator->>Render: 7. Deploy Unified Free Web Service (Single Container running Nginx + FastAPI on loopback)
    Operator->>App: 8. Execute Multi-Role Smoke Test Suite on https://campusfix-staging.onrender.com
```

1. **Database Provisioning**: Create isolated database `campusfix_staging` on Neon Free Tier with TLS enforced (`?ssl=require`).
2. **Pre-Migration Safety Branch**: Create instant zero-copy branch `neon branches create pre-staging-0c98aec98ce5`.
3. **Isolated Release Task Migration**: Apply Alembic schema migrations via a one-off release command (`alembic upgrade head`). Zero automatic startup migrations.
4. **Health Verification**: Confirm database connectivity via `GET /readyz` (returns HTTP 200 `{"status": "ready", "database": "connected"}`).
5. **Authorized Admin Provisioning**: Execute interactive `bootstrap_admin.py` for `kumarsagar77283@gmail.com` with masked password entry. Re-run to verify `ALREADY_ADMIN` idempotency.
6. **Unified Container Service Deployment**: Launch Render Free Web Service running the unified multi-stage container ([`Dockerfile`](file:///c:/Sagar%20Project/CampusFix/Dockerfile)) with Nginx listening on dynamic `$PORT` and reverse-proxying `/api/` to FastAPI on loopback `127.0.0.1:8000`.
7. **End-to-End Verification**: Execute live smoke test suite on the default Render URL, DevTools cookie inspection, RBAC validation, and physical accessibility evaluation. Account for initial 50s cold start delay on sleeping free instance.

---

### 8.7 Outstanding Operational & Architecture Risks (Free-Tier Staging Register)

All runtime risks remain actively tracked and must be verified during staging smoke testing:

1. **Service Sleep & Unified Cold Start**: The Render Free Web Service sleeps after 15 min idle. The unified single-container architecture ensures frontend and backend wake up together on initial visit (single ~50s spin-up window, eliminating cascading two-service delays).
2. **Backend Network Isolation**: Resolved. By packaging Nginx and FastAPI into a single container, FastAPI binds strictly to loopback `127.0.0.1:8000`. Zero public backend URLs exist, entirely mitigating external backend ingress vulnerabilities.
3. **Resource Quota Enforcement**: Memory must remain below 512 MB to prevent OOM termination. Total active hours must remain within 750 hrs/month, bandwidth under 5 GB/month, and database storage under Neon's 0.5 GB quota.
4. **Future Starter Tier Upgrade Readiness**: If staging testing requires zero cold starts, continuous 24/7 uptime, or native Render Private Services, upgrading the Web Service to Render Starter ($7/mo) remains available without application refactoring.
5. **Validated Docker Runtime**: Container multi-stage build (`Dockerfile`), unprivileged non-root execution (`campusfix` UID `10001`), dynamic `$PORT` substitution, `/healthz` & `/readyz` routing, fail-fast termination, and `SIGTERM` graceful shutdown (10s drain window) were successfully tested and validated on Docker Desktop in Phase 5.6.1.
6. **HTTPS & Browser Cookie Flow**: Refresh cookie enforces `Secure=True`, `HttpOnly=True`, `SameSite=Lax`, and `Path=/api/v1/auth` across both production and staging (`settings.is_cookie_secure`). Render automated Let's Encrypt TLS terminates at the edge and satisfies all modern browser cookie policies.
7. **Manual Accessibility Verification**: Screen-reader pronunciation (NVDA/VoiceOver), 400% zoom reflow, and physical touch-target verification remain pending physical evaluation during the staging pilot.
8. **Backend Scope Discrepancy Tracking**:
   * *Ticket Cancellation*: `ticket_fsm.py` line 275 permits admin cancellation if `is_creator`, while frontend strictly restricts cancellation to student creators.
   * *Omitted Admin Endpoints*: `/api/v1/admin/dashboard/metrics` and `/api/v1/admin/users` remain deferred per backend scope freeze; frontend safely routes to `/admin/categories`.

---

> [!CAUTION]
> **GOVERNANCE BOUNDARY MAINTAINED — PLANNING ALIGNMENT ONLY**:
> Phase 5.6 execution remains **STOPPED**. No cloud resources or databases have been provisioned, no containers built or deployed, and no application code modified. Deployment will begin only upon explicit Project Owner authorization to proceed.
