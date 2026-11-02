# Project Charter — CampusFix

| Document Version | 1.1.0 |
| :--- | :--- |
| **Status** | Approved Baseline (Phase 0) |
| **Author** | Senior Full-Stack Software Engineer & Technical Documentation Owner |
| **Last Updated** | 2026-10-27 (UTC) |
| **Target Audience** | Project Owner, University Evaluators, Engineering Team |

---

## 1. Project Vision

To build a professional, maintainable, secure, and accessible web-based campus facility issue reporting and resolution platform that establishes accountability, operational visibility, and transparency between university campus residents and facilities maintenance teams.

> **Institutional Notice**: CampusFix is an independent engineering project intended for evaluation, demonstration, and potential pilot deployment. It is not an officially endorsed or adopted university system. All branding, campus facility names, and user records are synthetic placeholders.

---

## 2. Problem Statement

Across higher-education institutions, physical campus facility disruptions—such as broken classroom projectors, faulty laboratory equipment, defective furniture, plumbing failures, or electrical hazards—frequently degrade the educational and residential experience.

Current informal reporting workflows (such as informal messaging groups, unmonitored emails, or physical paper logbooks) exhibit major operational deficiencies:
1. **Lack of Visibility**: Students submit issues into untracked channels without unique reference numbers, estimated turnaround times, or notification of acknowledgment.
2. **Duplicate Submissions**: Multiple individuals independently report identical facility defects, creating noise and triage overhead for maintenance crews.
3. **Accountability Gaps**: Hand-offs between staff lack verifiable records; there is no authoritative audit trail documenting who accepted a ticket, when physical repair began, or what corrective action was performed.
4. **Administrative Data Blindness**: Campus leadership lacks aggregated telemetry on recurring equipment failure points, building-level incident frequencies, or maintenance team turnaround metrics.

---

## 3. Target Users

| User Persona | Role | Primary Needs & Use Cases |
| :--- | :--- | :--- |
| **Student / Campus Resident** | `STUDENT` | Reports physical defects quickly (< 60 seconds) with location and category; tracks status changes transparently; receives resolution confirmation; cancels mistake submissions. |
| **Facilities Maintenance Technician** | `STAFF` | Accesses prioritized queue of assigned work orders; updates progress with field notes; marks repairs resolved with mandatory corrective descriptions; accesses only authorized data. |
| **Campus Operations Administrator** | `ADMINISTRATOR` | Oversees campus-wide ticket queues; assigns and reassigns work orders to qualified staff; manages categories; audits status history; analyzes operational performance metrics. |
| **Project Owner / Human Evaluator** | Project Reviewer | Reviews phase-gated engineering milestones, verifies automated test evidence, audits security boundaries, and evaluates pilot readiness. |

---

## 4. Proposed Solution

CampusFix provides a unified, role-based web application built as a modular monolith:
- **Responsive Web Portal**: Clean, accessible interface built with React, TypeScript, and Tailwind CSS, tailored for mobile and desktop screens.
- **Deterministic Ticket Lifecycle**: A finite state machine enforcing strict lifecycle progression (`SUBMITTED` → `ASSIGNED` → `IN_PROGRESS` → `RESOLVED` / `REJECTED` / `CANCELLED`), preventing illegal state jumps and requiring mandatory notes for closure or rejection.
- **Role-Based & Resource-Level Authorization**: FastAPI backend enforcing server-side RBAC and resource ownership boundaries (students can only access their own tickets; staff access their work queue; admins maintain global oversight).
- **Immutable Historical Audit Ledger**: Automatic append-only recording of every ticket state mutation, capturing timestamp (UTC), actor, prior state, target state, and notes.

---

## 5. Goals and Measurable Success Criteria

### 5.1 Project Goals
1. Standardize facility incident intake into a structured, categorized, and traceable digital workflow.
2. Eliminate lost or untracked facility reports through automated lifecycle progression and unique reference codes (`CFX-YYYY-XXXXX`).
3. Maintain zero trust for client data through comprehensive server-side authorization and input validation.
4. Deliver high usability across device viewports with WCAG 2.1 AA accessibility compliance.

### 5.2 Measurable Success Criteria (Key Performance Indicators)
- **Zero Critical Security Vulnerabilities**: 100% compliance with OWASP Top 10 defenses (zero IDOR leaks, zero plain-text passwords, secure session cookies, parameterized SQL queries).
- **100% State Machine Determinism**: All valid state transitions succeed and all invalid state jumps are rejected with HTTP 422 in automated test suites.
- **Automated Test Coverage**: >= 85% line and branch coverage across backend business logic and API endpoints; component and integration test coverage for critical frontend flows.
- **Sub-150ms API Latency**: 95th percentile response latency under 150ms for core paginated ticket queries under nominal 50-user concurrent load.
- **WCAG 2.1 Level AA Compliance**: Zero high-contrast or keyboard navigation defects across desktop and mobile viewports.

---

## 6. Constraints and Assumptions

### 6.1 Constraints
- **Workspace Confinement**: All code, configuration, and documentation must reside exclusively within the `CampusFix` workspace.
- **Fixed Technology Stack**: Backend: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, PostgreSQL, pytest, Ruff. Frontend: React 18+, TypeScript (strict mode), Vite, Tailwind CSS, React Router v6, Vitest, React Testing Library.
- **Zero Architectural Bloat**: No microservices, Redis, Celery/RabbitMQ, Kubernetes, or external paid third-party APIs permitted for the MVP.
- **Data Privacy**: No real university records, student IDs, or institutional credentials may be utilized. All development and testing rely strictly on synthetic fixtures.
- **Phase-Gated Development**: Progression between phases is strictly sequential and requires explicit project owner approval.

### 6.2 Assumptions
- Users access the platform via modern standards-compliant web browsers on desktop, tablet, or smartphone devices.
- Campus facility locations can be sufficiently designated by structured text strings (e.g., "Block B, Science Wing, Room 302") in the initial MVP without requiring a complex multi-table physical asset hierarchy.
- The university operates under a unified timezone; all timestamps are stored in UTC and rendered in local time on the client.

---

## 7. Risks and Dependencies

| Risk ID | Description | Severity | Probability | Mitigation Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **RSK-01** | **Scope Creep**: Premature addition of photo attachments, push notifications, or AI categorization. | High | Medium | Enforced MVP scope boundaries; deferred non-essential capabilities to post-core phases. |
| **RSK-02** | **Race Conditions / Lost Updates**: Concurrent status transitions or dual assignments by staff. | High | Medium | Applied database row-level locking (`SELECT FOR UPDATE`) and optimistic versioning (`version` counter). |
| **RSK-03** | **IDOR Data Leaks**: Students accessing other students' private facility tickets. | Critical | Low | Enforced resource-level check (`creator_id == current_user.id`) in backend service layer on every ticket query. |
| **RSK-04** | **Unvalidated University Domain Rules**: Facility teams might require specialized category structures or multi-tiered approval workflows. | Medium | High | Defined modular categories table and flexible FSM that can be extended following pilot feedback. |
| **RSK-05** | **Token Theft via XSS**: Exfiltration of long-lived user session credentials. | High | Low | Stored refresh tokens strictly in `HttpOnly`, `SameSite=Lax`, `Secure` cookies; kept access tokens short-lived (15 min) in client memory. |

### Technical Dependencies
- Node.js (v18+) and npm for frontend development and testing.
- Python (v3.11+) and virtual environment tools (`uv` or `venv`) for backend services.
- PostgreSQL (v15+) relational database instance.

---

## 8. Explicitly Excluded Features (MVP Out-of-Scope)

The following capabilities are deliberately excluded from the initial MVP to guarantee engineering rigor, maintainability, and delivery predictability:
- **Binary File & Photo Attachments**: Excluded from initial core MVP to avoid object storage complexity and unvalidated file upload attack vectors until core business logic and FSM are fully verified.
- **SMS / Push Notifications**: Out-of-scope; email/in-app notification stubs will be specified in Phase 3/4.
- **Institutional Single Sign-On (SSO / SAML 2.0 / Shibboleth)**: Out-of-scope for MVP; standard email/password authentication with Argon2id will be implemented with modular hooks for future SSO plugins.
- **Multi-Tenant University Partitioning**: The MVP models a single university domain.
- **Native Mobile Apps (iOS/Android)**: Mobile responsiveness is delivered via mobile-first web layouts.
- **AI Triage / Automated Image Damage Classification**: Out-of-scope.
- **Microservices / Distributed Task Queues / Redis / Celery**: Out-of-scope.
