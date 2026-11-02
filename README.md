# CampusFix

CampusFix is an enterprise-grade, secure, and accessible web platform designed for university campus facility issue reporting, tracking, and operational resolution. It bridges the gap between campus facility users (students, faculty, staff) and facilities operations teams through transparent ticket lifecycles, role-based workflows, and operational metrics.

> **Project Notice**: CampusFix is an independent engineering project intended for demonstration and potential pilot deployment. It is not an officially endorsed or adopted university production system. All branding, logos, and seed records use neutral placeholders and synthetic data.

---

## 1. System Overview

CampusFix provides a unified, structured workflow for campus physical infrastructure management:
- **Students & Campus Community**: Quickly report routine facility malfunctions (classroom AV, laboratory fixtures, HVAC, furniture, electrical, plumbing) with location tagging, priority indicators, and track resolution transparently.
- **Maintenance & Facilities Staff**: Triage incoming tickets, receive assignments, update execution progress with detailed work logs, and mark resolutions with formal sign-off.
- **University Operations Administrators**: Oversee service-level metrics, manage facility categories and staff assignments, audit status transitions, and extract operational analytics.

---

## 2. Core Architecture & Tech Stack

The system adheres to a strict requirements-first, modular monolith architecture:

| Tier | Technologies |
| :--- | :--- |
| **Frontend** | React 18+, TypeScript (strict mode), Vite, Tailwind CSS, React Router v6, Vitest + React Testing Library |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async/declarative), Alembic, PostgreSQL 15+ |
| **Security** | Argon2id password hashing, Short-lived JWT Access Tokens (15 min) + Secure HttpOnly SameSite Refresh Cookies (7 days) with token-family rotation and reuse revocation, Server-side RBAC + Resource-Level Authorization |
| **DevOps & QA** | Git, GitHub Actions (CI), Ruff (linting & formatting), pytest (backend unit/integration), Vitest (frontend unit/integration), Vercel-ready frontend, Docker / PaaS-ready backend |

---

## 3. Project Governance & Phased Lifecycle

Development follows a strict phase-gated execution plan:

- [x] **Phase 0: Inception, Requirements & Architectural Baseline** *(Completed)*
- [x] **Phase 1: UI/UX Design System, Screen Specifications & Wireframes** *(Completed)*
- [ ] **Phase 2: Repository Foundations, Tooling, Database Connectivity & Migrations** *(Gate Review / Complete)*
  - [x] **Checkpoint 2.1: Repository Initialization, Folder Structure & Tooling** *(Completed)*
  - [x] **Checkpoint 2.2: Backend Tooling, Linting & Python Dependencies** *(Completed)*
  - [x] **Checkpoint 2.3: Frontend Tooling, Linting & TypeScript Environment** *(Completed)*
  - [x] **Checkpoint 2.4: Database Connection Pool & Alembic Migration Baseline** *(Completed)*
  - [x] **Checkpoint 2.5: Database Models and Initial Schema Migration** *(Completed)*
  - [x] **Checkpoint 2.6: Integrated Smoke Test Harness & Phase 2 Gate Review** *(Completed)*
- [ ] **Phase 3: Core Domain Models, Auth Engine, Ticket State Machine & REST APIs** *(Pending)*
- [ ] **Phase 4: Client Interfaces (Student, Staff, Admin) & API Integration** *(Pending)*
- [ ] **Phase 5: End-to-End Verification, Security Audit & Regression Hardening** *(Pending)*
- [ ] **Phase 6: CI/CD Pipeline, Deployment Configuration & Pilot Readiness Checklist** *(Pending)*
- [ ] **Phase 7: User Feedback & University Pilot Evaluation** *(Pending)*

---

## 4. Documentation Index

Comprehensive project documentation is maintained in the [`docs/`](docs/) directory:

- [**docs/PROJECT_CHARTER.md**](docs/PROJECT_CHARTER.md): Vision, business goals, scope boundaries, and stakeholder matrix.
- [**docs/REQUIREMENTS.md**](docs/REQUIREMENTS.md): 28 Functional Requirements, 16 NFRs, and 14 user stories with Given-When-Then criteria.
- [**docs/DECISION_LOG.md**](docs/DECISION_LOG.md): Architectural Decision Records (ADR-001 through ADR-008).
- [**docs/ARCHITECTURE.md**](docs/ARCHITECTURE.md): Modular monolith layout, state machine transitions, sequence diagrams, and concurrency controls.
- [**docs/DATABASE_DESIGN.md**](docs/DATABASE_DESIGN.md): PostgreSQL 3NF schemas, ERD, indexes, constraints, and audit ledger.
- [**docs/API_SPECIFICATION.md**](docs/API_SPECIFICATION.md): OpenAPI/REST contracts, payload schemas, error formats, and RBAC rules.
- [**docs/DESIGN_SYSTEM.md**](docs/DESIGN_SYSTEM.md): Tokenized colors, WCAG 2.1 AA contrast matrix, typography scales, and component blueprints.
- [**docs/PHASE_1_WIREFRAMES.md**](docs/PHASE_1_WIREFRAMES.md): ASCII wireframes and interaction blueprints for all screens (`SCR-01` through `SCR-09`).
- [**docs/USER_FLOWS.md**](docs/USER_FLOWS.md): Detailed user journeys for Student, Staff, and Administrator roles.
- [**docs/PHASE_1_ACCEPTANCE.md**](docs/PHASE_1_ACCEPTANCE.md): Testable verification criteria for design and wireframes.
- [**docs/TESTING_STRATEGY.md**](docs/TESTING_STRATEGY.md): Unit, integration, authorization boundary, and state transition test harnesses.
- [**docs/SECURITY.md**](docs/SECURITY.md): Threat model, OWASP mitigations, token rotation, and credential safety.
- [**docs/DEPLOYMENT.md**](docs/DEPLOYMENT.md): Hosting topology, environment variables, migration runbooks, and health probes.
- [**docs/PROJECT_STATUS.md**](docs/PROJECT_STATUS.md): Current phase status, risk register, and phase-gate criteria.

---

## 5. Repository Structure

```text
CampusFix/
├── .gitignore                  # Git exclusion rules for secrets, caches, and build artifacts
├── .env.example                # Root environment template (documentary reference)
├── README.md                   # This project guide & setup instructions
├── docs/                       # Project specifications & governance documentation
│   ├── PROJECT_CHARTER.md
│   ├── REQUIREMENTS.md
│   ├── DECISION_LOG.md
│   ├── ARCHITECTURE.md
│   ├── DATABASE_DESIGN.md
│   ├── API_SPECIFICATION.md
│   ├── DESIGN_SYSTEM.md
│   ├── PHASE_1_WIREFRAMES.md
│   ├── USER_FLOWS.md
│   ├── PHASE_1_ACCEPTANCE.md
│   ├── TESTING_STRATEGY.md
│   ├── SECURITY.md
│   ├── DEPLOYMENT.md
│   └── PROJECT_STATUS.md
├── backend/                    # Python 3.11+ / FastAPI Service
│   ├── app/                    # Application source package
│   │   ├── api/                # API routes & endpoint dependencies
│   │   │   └── v1/             # API v1 versioned routes
│   │   ├── core/               # App configuration, security, database engine
│   │   ├── models/             # SQLAlchemy 2.0 ORM models
│   │   ├── schemas/            # Pydantic v2 validation schemas
│   │   └── services/           # Domain business logic & state machine
│   ├── alembic/                # Database migrations & migration environment
│   ├── tests/                  # Backend unit, integration & migration test suites
│   └── .env.example            # Backend local environment template
└── frontend/                   # React 18+ / Vite / TypeScript Client
    ├── src/                    # Frontend source tree
    │   ├── api/                # Typed API client services
    │   ├── components/         # Reusable design system UI components
    │   ├── hooks/              # Custom React hooks (auth, tickets)
    │   ├── pages/              # Role-specific route views
    │   └── types/              # TypeScript domain types & API interfaces
    ├── tests/                  # Frontend component & integration tests
    └── .env.example            # Frontend local environment template
```

---

## 6. Prerequisites

To run and contribute to CampusFix, install the following development prerequisites:

- **Git**: `2.38+`
- **Python**: `3.11+`
- **Node.js**: `18.18+` or `20.x LTS` (with `npm 9+`)
- **PostgreSQL**: `15+` (local instance or Docker container; required for backend integration testing and persistence)

---

## 7. Environment Configuration & Secret Safety

CampusFix adheres to strict credential governance. **Never commit real credentials, passwords, or cryptographic keys to version control.**

### 7.1 Backend Environment Setup

1. Copy the backend template:
   ```bash
   cp backend/.env.example backend/.env
   # On Windows PowerShell:
   Copy-Item backend/.env.example backend/.env
   ```
2. Configure `backend/.env` with local development settings:
   - Generate a local `SECRET_KEY` (minimum 32 bytes / 64 hex characters):
     ```bash
     openssl rand -hex 32
     ```
   - Update `DATABASE_URL` with your local PostgreSQL credentials:
     `postgresql+asyncpg://<username>:<password>@localhost:5432/campusfix`
   - Adjust `ALLOWED_ORIGINS` to include your local Vite dev server (`http://localhost:5173`).

### 7.2 Frontend Environment Setup

1. Copy the frontend template:
   ```bash
   cp frontend/.env.example frontend/.env
   # On Windows PowerShell:
   Copy-Item frontend/.env.example frontend/.env
   ```
2. Verify `VITE_API_BASE_URL` points to your backend instance (default: `http://localhost:8000/api/v1`).

---

## 8. Planned Development Startup Instructions

> [!NOTE]
> Application dependencies, entry points, and build manifests are scheduled for implementation in **Checkpoint 2.2** (Backend) and **Checkpoint 2.3** (Frontend). The commands below document the planned operational workflow and will become active as subsequent checkpoints complete.

### Backend Startup (Available after Checkpoint 2.2)
```bash
# [Planned - Active in Checkpoint 2.2+]
cd backend
python -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

### Database Migrations (Available after Checkpoint 2.4)
```bash
# [Planned - Active in Checkpoint 2.4+]
cd backend
alembic upgrade head
python -m app.scripts.seed   # Populates synthetic test fixtures only
```

### Frontend Startup (Available after Checkpoint 2.3)
```bash
# [Planned - Active in Checkpoint 2.3+]
cd frontend
npm install
npm run dev                  # Starts Vite dev server on http://localhost:5173
```

---

## 9. Development Principles & Synthetic Data Policy

1. **Security as an Architecture**: Zero plain-text passwords, zero committed secrets, mandatory server-side RBAC, and resource-level authorization checks on all endpoints.
2. **Deterministic State Transitions**: Ticket statuses transition strictly through an approved finite state machine. Arbitrary edits are forbidden.
3. **Data Integrity & Traceability**: Every state modification and assignment is recorded in an immutable historical audit log with actor ID, timestamp, and mandatory notes.
4. **Privacy & Synthetic Fixtures**: Real student or university credentials and personal data are strictly prohibited. Development and testing use synthetic seed datasets (`*.local` emails) only.
