# Deployment Strategy & Operational Runbooks — CampusFix

| Document Version | 1.0.0 |
| :--- | :--- |
| **Status** | Approved Baseline (Phase 0) |
| **Maintainer** | DevOps Lead & Systems Architect |
| **Last Updated** | 2026-10-27 (UTC) |

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
| **Frontend** | Vercel / Netlify / Cloudflare Pages | Static single-page assets (`frontend/dist`) | Globally distributed edge CDN, zero server maintenance. |
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

The backend exposes two standard operational health probes:
1. **Liveness Probe (`GET /healthz`)**:
   - Returns HTTP 200 `{ "status": "healthy" }` if the FastAPI web process is responsive.
2. **Readiness Probe (`GET /readyz`)**:
   - Executes a lightweight `SELECT 1` on PostgreSQL.
   - Returns HTTP 200 `{ "status": "ready", "database": "connected" }` if the database pool is healthy.
   - Returns HTTP 503 `{ "status": "unhealthy", "database": "unreachable" }` if database connection fails.
