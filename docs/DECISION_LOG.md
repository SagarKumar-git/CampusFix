# Decision Log — CampusFix Architecture Decision Records (ADRs)

| Document Version | 1.1.0 |
| :--- | :--- |
| **Status** | Approved Baseline (Phase 0) |
| **Maintainer** | Software Architect & Technical Lead |
| **Last Updated** | 2026-10-27 (UTC) |

---

## Index of Decisions

- [ADR-001: Core Technology Stack Selection](#adr-001-core-technology-stack-selection)
- [ADR-002: Authentication & Token Management Strategy](#adr-002-authentication--token-management-strategy)
- [ADR-003: Deterministic Ticket Lifecycle & State Transition Enforcement](#adr-003-deterministic-ticket-lifecycle--state-transition-enforcement)
- [ADR-004: Modular Monolithic Architecture & Monorepo Layout](#adr-004-modular-monolithic-architecture--monorepo-layout)
- [ADR-005: Concurrency Control & Ticket State Race Condition Prevention](#adr-005-concurrency-control--ticket-state-race-condition-prevention)
- [ADR-006: Synthetic Seed Data & Credential Governance](#adr-006-synthetic-seed-data--credential-governance)
- [ADR-007: Role Hierarchy & Server-Side Authorization Model](#adr-007-role-hierarchy--server-side-authorization-model)
- [ADR-008: Security Constraints & Defensive Engineering Baseline](#adr-008-security-constraints--defensive-engineering-baseline)

---

## ADR-001: Core Technology Stack Selection

### Context
CampusFix requires a secure, high-performance, maintainable web platform with strong type safety, clear API schemas, and robust database migrations. The solution must support fast student ticket reporting and high-density staff operational management.

### Decision
Adopt the following unified technology stack:
- **Frontend**: React 18+ with strict TypeScript, Vite for rapid compilation, Tailwind CSS for tokenized utility styling, and React Router v6.
- **Backend**: Python 3.11+, FastAPI (asynchronous, OpenAPI-native), Pydantic v2 (strict request/response validation), SQLAlchemy 2.0 (declarative async ORM), and Alembic for declarative database migrations.
- **Database**: PostgreSQL 15+ (ACID-compliant relational store with JSONB, indexing, and transactional integrity).
- **Tooling & QA**: Ruff (Python linting/formatting), pytest (backend unit/integration), Vitest & React Testing Library (frontend).

### Consequences & Trade-offs
- **Pros**: Automatic OpenAPI schema generation from Pydantic; full end-to-end type safety across backend schemas and frontend TypeScript interfaces; rich migration ecosystem via Alembic; fast build times with Vite and Ruff.
- **Cons**: Requires maintaining two separate development runtimes (Node.js and Python) within the local workspace.

---

## ADR-002: Authentication & Token Management Strategy

### Context
User authentication must prevent token theft, Cross-Site Scripting (XSS) compromise, and Cross-Site Request Forgery (CSRF). Storing long-lived tokens in browser `localStorage` or `sessionStorage` exposes the system to token exfiltration via XSS.

### Decision
Implement a hybrid access/refresh token pattern with token-family tracking, atomic single-use rotation, and family-wide reuse invalidation:
1. **Access Token**: Short-lived JSON Web Token (JWT) with a 15-minute lifespan, held in frontend application memory (React state) and transmitted via the `Authorization: Bearer <token>` header.
2. **Refresh Token**: Cryptographically random token with a 7-day lifespan, stored strictly in an `HttpOnly`, `SameSite=Lax`, and `Secure` cookie.
3. **Database Persistence & Family Identification**:
   - The SHA-256 hash of each issued refresh token is persisted in `refresh_tokens`. Raw tokens are never stored.
   - Initial login (`/auth/login`) mints a unique `family_id = gen_random_uuid()`.
4. **Atomic Token Rotation & Concurrency Protection**:
   - Each call to `/api/v1/auth/refresh` executes inside an atomic database transaction using row-level locking (`SELECT ... FOR UPDATE` on `refresh_tokens WHERE token_hash = :hash`).
   - If `revoked_at IS NULL` and unexpired, the token is consumed (`revoked_at = CLOCK_TIMESTAMP()`), and a replacement token is issued inheriting the **exact same `family_id`**.
   - Row locking serializes concurrent refresh requests, guaranteeing that two parallel requests cannot both consume the same token.
5. **Token Reuse Detection & Family Revocation**:
   - If an already-revoked token is presented, the server detects a replay attack and invalidates all active tokens in that chain (`UPDATE refresh_tokens SET revoked_at = CLOCK_TIMESTAMP() WHERE family_id = :family_id AND revoked_at IS NULL`).
   - **Session Isolation**: Sessions on other devices (having distinct `family_id` values) remain active and unaffected.
6. **Server-Side Logout**:
   - Logout marks the session's active refresh token as revoked in the database and clears the client cookie (`Max-Age=0`).
7. **CSRF Mitigation**:
   - Enforce `SameSite=Lax` for refresh cookies and validate `Origin`/`Referer` headers on state-changing authentication endpoints.

### Consequences & Trade-offs
- **Pros**: Minimizes window of vulnerability if an access token is leaked; prevents JavaScript access to long-lived refresh credentials; detects and neutralizes token theft via family-wide invalidation without logging out unrelated devices; eliminates race conditions via database row locks.
- **Cons**: Requires database row-level locking and indexed lookup on token refresh; requires precise CORS configuration (`allow_credentials=True`) for cookie exchange across development origins.

---

## ADR-003: Deterministic Ticket Lifecycle & State Transition Enforcement

### Context
In naive issue tracking systems, ticket status is treated as an arbitrary string or editable dropdown field. This allows illegal jumps (e.g., from `SUBMITTED` directly to `RESOLVED` without an assignee, or editing a `CANCELLED` ticket). Furthermore, reopening failed repairs or mistakenly rejected tickets requires explicit governance.

### Decision
Implement a formal Finite State Machine (FSM) inside the backend domain service layer (`TicketService`):
1. **Defined States**: `SUBMITTED`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `REJECTED`, `CANCELLED`.
2. **Strict Transition Matrix**: State transitions are validated against a lookup dictionary of permitted source-to-target transitions. Any illegal transition raises an explicit HTTP 422 Unprocessable Entity error.
3. **Mandatory Metadata**:
   - `REJECTED` demands a `rejection_reason` (minimum 10 characters).
   - `RESOLVED` demands `resolution_notes` (minimum 10 characters).
   - `REOPENED` (transition from `RESOLVED` or `REJECTED` to `ASSIGNED` or `SUBMITTED`) is strictly restricted to the `ADMINISTRATOR` role and demands a `reopening_reason` (minimum 10 characters). Students cannot reopen tickets directly; recurring issues must be filed as new tickets.
4. **Immutable Audit Log**: Every transition triggers a database insert into `ticket_status_history` recording status changes, the actor, and any assigned technician within the same database transaction.

### Consequences & Trade-offs
- **Pros**: Eliminates invalid data states; guarantees audit compliance; simplifies frontend UI state rendering; provides an accountable path to resume work on incomplete repairs.
- **Cons**: Requires structured API endpoints for state transitions rather than a generic `PATCH /tickets/{id}`.

---

## ADR-004: Modular Monolithic Architecture & Monorepo Layout

### Context
Modern web architectures frequently overcomplicate early-stage projects with microservices, Redis queues, and distributed message brokers, adding substantial operational overhead and failure points.

### Decision
Structure CampusFix as a **Modular Monolith** within a single monorepo:
- `backend/`: FastAPI application organized by layers (`api/`, `core/`, `models/`, `schemas/`, `services/`).
- `frontend/`: React Vite application organized by domain modules (`api/`, `components/`, `pages/`, `hooks/`, `types/`).
- `docs/`: Central project documentation and ADRs.

No microservices, Redis, Celery, or external message brokers will be introduced in the MVP.

### Consequences & Trade-offs
- **Pros**: Zero distributed network latency; simplified local development and CI/CD pipelines; unified versioning and atomic commits; simple transactional boundaries in PostgreSQL.
- **Cons**: Background long-running tasks must execute synchronously or via FastAPI `BackgroundTasks` until async queueing is explicitly required.

---

## ADR-005: Concurrency Control & Ticket State Race Condition Prevention

### Context
Multiple staff members or an administrator and student may concurrently attempt to modify the same ticket (e.g., two staff members claiming the same unassigned ticket, or a student cancelling a ticket at the exact moment a staff member marks it in progress).

### Decision
Apply concurrency control mechanisms:
1. **Row-Level Locking on Status Transitions**: Use PostgreSQL `SELECT ... FOR UPDATE` within the transition transaction in `TicketService` to serialize concurrent mutations on the same ticket record.
2. **Optimistic Versioning**: Maintain an integer `version` field on the `tickets` table incremented on each update. If an update specifies a mismatched version, the request fails with HTTP 409 Conflict.

### Consequences & Trade-offs
- **Pros**: Complete protection against lost updates, double-assignment, and invalid ghost transitions.
- **Cons**: Frontend must handle HTTP 409 Conflict gracefully by refreshing stale data.

---

## ADR-006: Synthetic Seed Data & Credential Governance

### Context
Using real student information, institutional credentials, or hardcoded administrative passwords during development creates grave privacy and security vulnerabilities.

### Decision
Establish strict data and credential governance:
1. **Zero Real Data**: All users, ticket descriptions, room numbers, and contact details must use synthetic, fictitious data.
2. **Explicit Seed Script**: Seed data will be populated via a dedicated CLI script (`python -m app.scripts.seed`) populated with deterministic demo accounts:
   - `student.demo@campusfix.local` / `StudentDemo123!`
   - `staff.demo@campusfix.local` / `StaffDemo123!`
   - `admin.demo@campusfix.local` / `AdminDemo123!`
3. **No Default Production Credentials**: Seed scripts are prohibited from running automatically in production mode. Environment configuration must enforce strong, unique passwords for production provisioning.

### Consequences & Trade-offs
- **Pros**: Zero exposure of personal identifiable information (PII); predictable testing fixtures for development and automated integration tests.
- **Cons**: Developers must run explicit seed commands to initialize local sandbox environments.

---

## ADR-007: Role Hierarchy & Server-Side Authorization Model

### Context
Frontend role checks can easily be bypassed by a malicious actor tampering with local storage or sending forged requests via curl/Postman. A formal role hierarchy and server-side authorization enforcement policy are necessary.

### Decision
Establish three distinct, non-overlapping roles:
1. `STUDENT`:
   - Can register public accounts.
   - Can create tickets and view ONLY tickets they submitted (`creator_id == current_user.id`).
   - Can cancel their own tickets only while in `SUBMITTED` or `ASSIGNED` status.
2. `STAFF`:
   - Accounts can only be provisioned by an administrator.
   - Can view assigned tickets or unassigned queue.
   - Can self-claim unassigned tickets.
   - Can transition assigned tickets to `IN_PROGRESS` and `RESOLVED`.
   - Cannot manage categories, delete tickets, or edit user roles.
3. `ADMINISTRATOR`:
   - Full global visibility across all tickets.
   - Can manually assign/reassign tickets to staff members.
   - Can reject out-of-scope tickets with mandatory reason.
   - Can manage facility categories and user accounts.
   - Can access aggregate operational metrics.

**Zero Trust Enforcement**: All role checks are performed in FastAPI dependency injection (`require_role(...)`). Client claims are treated as purely decorative for UI navigation.

### Consequences & Trade-offs
- **Pros**: Complete backend enforcement; eliminates privilege escalation and unauthorized access.
- **Cons**: Requires granular FastAPI dependency definitions for every route category.

---

## ADR-008: Security Constraints & Defensive Engineering Baseline

### Context
College campus web portals are frequent targets for credential stuffing, SQL injection, script tampering, and data scraping. The application must embed defense-in-depth principles.

### Decision
Enforce the following non-negotiable security constraints:
1. **Password Hashing**: Argon2id or bcrypt (cost >= 12).
2. **SQL Injection Defense**: 100% parameterization via SQLAlchemy 2.0 ORM; dynamic raw string queries are strictly forbidden.
3. **IDOR Mitigation**: Scoped queries filtering on user ID for non-admin/staff roles.
4. **CORS Hardening**: Strict allowlist of known frontend origins; credentials disallowed for wildcard origins.
5. **Sanitized Errors**: Exception handlers transform all internal errors into uniform JSON error envelopes without stack traces or environment secrets.
6. **Rate Limiting**: Rate limits applied to `/auth/login` and `/tickets` creation.

### Consequences & Trade-offs
- **Pros**: Protects system integrity and personal data against standard web attack vectors.
- **Cons**: Strict error masking requires robust server-side logging for developer debugging.
