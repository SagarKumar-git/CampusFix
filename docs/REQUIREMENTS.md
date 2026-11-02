# Requirements Specification — CampusFix

| Document Version | 1.1.0 |
| :--- | :--- |
| **Status** | Approved Baseline (Phase 0) |
| **Author** | Senior Full-Stack Software Engineer & Requirements Lead |
| **Last Updated** | 2026-10-27 (UTC) |

---

## 1. Introduction & Overview

This specification establishes the authoritative functional and non-functional requirements for the **CampusFix** web application. Every requirement is uniquely indexed, categorized by subsystem, prioritized using the MoSCoW framework (**Must Have**, **Should Have**, **Could Have**), and directly mapped to testable criteria.

---

## 2. Functional Requirements (FR)

### 2.1 Authentication & Account Management

| ID | Title | Priority | Description & Business Rules |
| :--- | :--- | :--- | :--- |
| **FR-001** | Student Self-Registration | **Must** | The system must allow students to register using their full name, institutional email address format (`*@*.*`), and a secure password (minimum 8 characters, at least 1 number, 1 uppercase letter, 1 lowercase letter). Public registration must exclusively grant the `STUDENT` role. |
| **FR-002** | Privileged Account Provisioning | **Must** | The system must prohibit public registration for `STAFF` and `ADMINISTRATOR` roles. Privileged accounts must be provisioned through secure administrative actions or synthetic development seed scripts. |
| **FR-003** | Secure Credential Authentication | **Must** | The system must authenticate users via email and password. Passwords must be hashed using Argon2id or bcrypt. Plaintext passwords must never be stored, logged, or returned in API responses. |
| **FR-004** | Token-Based Session Management & Family Tracking | **Must** | On successful login, the system must issue a short-lived JSON Web Token (JWT) access token (15-minute expiry) in response JSON and a cryptographically secure refresh token (7-day expiry) stored inside an `HttpOnly`, `SameSite=Lax`, and `Secure` cookie. The system must mint a unique `family_id` (UUID) identifying the session chain and persist the SHA-256 digest of the refresh token in `refresh_tokens` bound to `user_id`, `family_id`, and `expires_at`. |
| **FR-005** | Atomic Token Rotation, Reuse Detection & Revocation | **Must** | The system must provide a token refresh endpoint (`POST /auth/refresh`) that validates the refresh cookie against `refresh_tokens` using row-level locking (`SELECT ... FOR UPDATE`) inside an atomic database transaction. On valid refresh, the consumed token is marked revoked (`revoked_at = CLOCK_TIMESTAMP()`) and a replacement token is issued inheriting the exact same `family_id`. If an already-revoked token is presented, the system must detect token reuse, immediately revoke all active refresh tokens sharing that `family_id`, and return HTTP 401 Unauthorized (`TOKEN_REUSE_DETECTED`). Unrelated device sessions for the same user (having different `family_id` values) must remain valid. Logout (`POST /auth/logout`) must mark the token family as revoked in the database and clear the client cookie. |
| **FR-006** | Profile Introspection (`/me`) | **Must** | Authenticated users must be able to query their own profile details (ID, full name, email, role, active status). |
| **FR-007** | Server-Side RBAC Enforcement | **Must** | The system must enforce three immutable roles: `STUDENT`, `STAFF`, and `ADMINISTRATOR`. Role checks must execute on the backend for every protected endpoint. Requests with insufficient permissions must return HTTP 403 Forbidden. |

---

### 2.2 Ticket Creation & Intake

| ID | Title | Priority | Description & Business Rules |
| :--- | :--- | :--- | :--- |
| **FR-008** | Unique Ticket Identification | **Must** | Every ticket must be assigned a globally unique UUID primary key and an alphanumeric, human-readable reference code (`CFX-YYYY-XXXXX`, e.g., `CFX-2026-00042`). |
| **FR-009** | Mandatory Ticket Submission Fields | **Must** | A ticket submission must validate and require: Title (5–120 chars), Description (10–2000 chars), Category ID (valid active category), Location string (3–100 chars), and Priority (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`, default `MEDIUM`). |
| **FR-010** | Creator Binding & Initial State | **Must** | The system must automatically bind the authenticated user's ID as `creator_id` and initialize the ticket in `SUBMITTED` status. Clients are prohibited from specifying arbitrary initial statuses or creator IDs. |
| **FR-011** | Creation Timestamps | **Must** | The system must record UTC timestamps for `created_at` and `updated_at` on every ticket record. |
| **FR-012** | Student Ticket Isolation (IDOR Defense) | **Must** | When querying tickets, students must only be permitted to retrieve tickets where `creator_id == current_user.id`. Requests for other students' tickets must return HTTP 404 (or 403) with zero information leaked. |

---

### 2.3 Ticket Lifecycle & State Transitions

| ID | Title | Priority | Description & Business Rules |
| :--- | :--- | :--- | :--- |
| **FR-013** | Finite State Machine Enforcement | **Must** | The system must enforce six valid statuses: `SUBMITTED`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `REJECTED`, `CANCELLED`. Arbitrary or undocumented state transitions must be rejected with HTTP 422 Unprocessable Entity. |
| **FR-014** | Permitted Transition & Reopening Rules | **Must** | The system must strictly enforce valid transitions: `SUBMITTED` → `ASSIGNED`, `REJECTED`, `CANCELLED`; `ASSIGNED` → `IN_PROGRESS`, `ASSIGNED` (reassignment), `REJECTED`, `CANCELLED`; `IN_PROGRESS` → `RESOLVED`, `ASSIGNED` (paused), `REJECTED`; `RESOLVED` → `ASSIGNED` (reopened by Admin), `SUBMITTED` (reopened by Admin); `REJECTED` → `ASSIGNED` (reopened by Admin), `SUBMITTED` (reopened by Admin); `CANCELLED` is terminal. Students cannot reopen tickets. |
| **FR-015** | Mandatory Transition Commentary | **Must** | Moving to `REJECTED` strictly requires a `rejection_reason` (min 10 chars). Moving to `RESOLVED` strictly requires `resolution_notes` (min 10 chars). Reopening a `RESOLVED` or `REJECTED` ticket strictly requires an `ADMINISTRATOR` role and a `reopening_reason` (min 10 chars) recorded in the audit history. |
| **FR-016** | Student Cancellation Rules | **Must** | A student can only cancel their own ticket, and only when the ticket is in `SUBMITTED` or `ASSIGNED` status. Once a ticket is `IN_PROGRESS`, student cancellation is blocked. |
| **FR-017** | Immutable Status & Assignment History | **Must** | Every state transition or staff assignment modification must write an immutable entry to `ticket_status_history` recording `ticket_id`, `from_status`, `to_status`, `changed_by_user_id`, `assigned_to_user_id` (nullable), `notes`, and UTC `created_at`. |
| **FR-018** | Concurrency Conflict Detection | **Must** | The system must apply optimistic locking via an integer `version` field. If a state update specifies a stale version, the request must fail with HTTP 409 Conflict. |

---

### 2.4 Staff Operations & Work Queue

| ID | Title | Priority | Description & Business Rules |
| :--- | :--- | :--- | :--- |
| **FR-019** | Staff Work Queue Access | **Must** | Staff members must be able to view tickets assigned to them (via `assigned_staff_id=me`) or unassigned tickets available in the triage pool (via `status=SUBMITTED`). |
| **FR-020** | Ticket Self-Assignment | **Should** | Authorized staff members must be able to claim unassigned `SUBMITTED` tickets, transitioning them to `ASSIGNED` with their own user ID bound. |
| **FR-021** | Work Commencement Logging | **Must** | Staff members must transition assigned tickets to `IN_PROGRESS` before completing physical work, establishing an active timestamp. |
| **FR-022** | Resolution Sign-off | **Must** | Staff members must be able to formally close an `IN_PROGRESS` ticket to `RESOLVED` by submitting mandatory completion notes detailing the corrective action taken. |

---

### 2.5 Administrator Management & Reporting

| ID | Title | Priority | Description & Business Rules |
| :--- | :--- | :--- | :--- |
| **FR-023** | Global Ticket Oversight | **Must** | Administrators must have full visibility across all tickets, with multi-attribute filtering (comma-separated `status`, `category_id`, `priority`, `assigned_staff_id`) and server-side pagination. |
| **FR-024** | Staff Work Order Assignment | **Must** | Administrators must be able to assign or reassign any active ticket to any active staff member. |
| **FR-025** | Facility Category Management | **Must** | Administrators must be able to create, update, activate, and deactivate facility issue categories. Hard deletion of categories associated with existing tickets is prohibited. |
| **FR-026** | User & Role Management | **Must** | Administrators must be able to view user rosters (supporting `search`, `role`, and `is_active` filters), alter user roles, and deactivate or reactivate user accounts. |
| **FR-027** | Operational Metrics Dashboard | **Should** | Administrators must be able to view high-level operational statistics: ticket counts by status, priority breakdown, and average resolution time. |
| **FR-028** | Category Incident Export | **Could** | The system could allow administrators to export ticket summaries in CSV format for institutional reporting. |

---

## 3. Non-Functional Requirements (NFR)

### 3.1 Security & Compliance (NFR-SEC)

| ID | Title | Priority | Target Standard & Specification |
| :--- | :--- | :--- | :--- |
| **NFR-001** | Password Hashing | **Must** | All user passwords must be hashed using Argon2id or bcrypt (cost factor >= 12). Plaintext passwords must never touch disk or logs. |
| **NFR-002** | Zero Committed Secrets | **Must** | No cryptographic keys, database passwords, or operational secrets may be committed to source control. Configuration must be loaded from environment variables. |
| **NFR-003** | Input Validation & Sanitization | **Must** | All incoming request bodies must be validated against strict Pydantic schemas. Unrecognized or extraneous fields must be rejected or stripped. |
| **NFR-004** | SQL Injection Immunity | **Must** | 100% of database queries must be executed via SQLAlchemy 2.0 ORM using parameter binding. Dynamic string-interpolated SQL is strictly prohibited. |
| **NFR-005** | CORS Restrictions | **Must** | Cross-Origin Resource Sharing must be configured with explicit allowed origins. Wildcard `*` origins with credentials must be blocked. |
| **NFR-006** | Brute-Force Rate Limiting | **Must** | Rate limiting must be enforced on authentication endpoints (`/auth/login`) to mitigate automated credential guessing. |
| **NFR-007** | Sanitized Error Envelopes | **Must** | Internal stack traces, raw database error strings, and server internals must never be exposed to clients. Errors must return standard JSON envelopes. |

---

### 3.2 Performance & Scalability (NFR-PERF)

| ID | Title | Priority | Target Standard & Specification |
| :--- | :--- | :--- | :--- |
| **NFR-008** | API Response Latency | **Must** | 95% of read requests (`GET /api/v1/tickets`) must respond in < 150ms under a nominal concurrent load of 50 users. |
| **NFR-009** | Server-Side Pagination | **Must** | All list endpoints must mandate server-side pagination with a default page size of 20 and a maximum cap of 100 items per page. |
| **NFR-010** | Database Indexing | **Must** | Foreign keys (`creator_id`, `assigned_staff_id`, `category_id`), statuses, ticket numbers, and creation timestamps must have explicit B-tree indexes. |

---

### 3.3 Usability & Accessibility (NFR-UX)

| ID | Title | Priority | Target Standard & Specification |
| :--- | :--- | :--- | :--- |
| **NFR-011** | Accessibility Standards | **Must** | The client interface must conform to WCAG 2.1 Level AA, maintaining >= 4.5:1 color contrast, full keyboard navigability, and visible focus rings. |
| **NFR-012** | Responsive Layouts | **Must** | Interfaces must adapt responsively without layout breakage or horizontal scrolling across viewport widths from 360px (mobile) to 1920px (desktop). |
| **NFR-013** | Deterministic UI States | **Must** | All data-driven views must provide explicit visual states for Loading (skeletons), Empty (guidance CTA), Error (actionable banner), and Success (toast/banner). |

---

### 3.4 Maintainability & Engineering Quality (NFR-MNT)

| ID | Title | Priority | Target Standard & Specification |
| :--- | :--- | :--- | :--- |
| **NFR-014** | End-to-End Type Safety | **Must** | Frontend must run strict-mode TypeScript (`noImplicitAny: true`); Backend must adhere to Pydantic v2 schemas and type annotations verified by Ruff. |
| **NFR-015** | Versioned Schema Migrations | **Must** | Database schemas must be version-controlled using forward-compatible Alembic migrations. Runtime auto-creation of tables is prohibited in production. |
| **NFR-016** | Automated Test Reproducibility| **Must** | All test suites must be fully automated and executable locally via single-command invocations (`pytest` and `npm run test`). |

---

## 4. User Stories & Acceptance Criteria

### US-001: Student Files a New Facility Issue
- **Role**: `STUDENT`
- **Story**: As a campus resident or student, I want to report a broken facility item in my classroom or hostel, so that facilities staff are alerted and I can track progress toward resolution.
- **Priority**: **Must Have**
- **Acceptance Criteria**:
  - **Given** I am an authenticated student on the ticket creation screen,
  - **When** I submit a title ("Damaged Projector Screen"), description, valid category, room location ("Room 204"), and priority ("HIGH"),
  - **Then** a new ticket record is created in `SUBMITTED` status,
  - **And** a human-readable code (`CFX-2026-XXXXX`) is generated,
  - **And** the creator is bound to my user ID,
  - **And** an initial entry is written into `ticket_status_history`.

---

### US-002: Student Views and Filters Personal Tickets
- **Role**: `STUDENT`
- **Story**: As a campus student, I want to view the list of tickets I have submitted, so that I can monitor their current statuses without seeing issues reported by other students.
- **Priority**: **Must Have**
- **Acceptance Criteria**:
  - **Given** I am an authenticated student navigating to "My Tickets",
  - **When** the ticket list loads,
  - **Then** only tickets where `creator_id == current_user.id` are returned,
  - **And** attempting to request a ticket belonging to another student via URL directly returns HTTP 404/403.

---

### US-003: Student Cancels an Open Ticket
- **Role**: `STUDENT`
- **Story**: As a campus student, I want to cancel an issue I reported by mistake, so that staff do not waste time on an invalid work order.
- **Priority**: **Must Have**
- **Acceptance Criteria**:
  - **Given** I am the creator of a ticket currently in `SUBMITTED` or `ASSIGNED` status,
  - **When** I confirm cancellation with an explanation note,
  - **Then** the ticket transitions to `CANCELLED` status and a history entry is recorded,
  - **And** if the ticket was already in `IN_PROGRESS` status, cancellation is blocked with a clear error message.

---

### US-004: Staff Reviews Queue and Begins Work
- **Role**: `STAFF`
- **Story**: As a facilities technician, I want to inspect tickets assigned to me and mark them as In Progress, so that dispatchers and students know work is actively being executed.
- **Priority**: **Must Have**
- **Acceptance Criteria**:
  - **Given** I am an authenticated staff member viewing my work queue,
  - **When** I select an `ASSIGNED` ticket and trigger "Begin Work",
  - **Then** the ticket status updates to `IN_PROGRESS`,
  - **And** a history record logs my user ID and the transition timestamp.

---

### US-005: Staff Resolves a Work Order with Mandatory Notes
- **Role**: `STAFF`
- **Story**: As a facilities technician, I want to mark a ticket as resolved and document the physical fix, so that the maintenance record is closed with verifiable evidence.
- **Priority**: **Must Have**
- **Acceptance Criteria**:
  - **Given** I am the assigned staff member for an `IN_PROGRESS` ticket,
  - **When** I attempt to resolve the ticket without providing resolution notes,
  - **Then** the submission is rejected with a validation error,
  - **When** I supply resolution notes (minimum 10 characters) and submit,
  - **Then** the status transitions to `RESOLVED`, the notes are saved to the ticket, and the student sees the resolution summary.

---

### US-006: Administrator Triage and Work Order Assignment
- **Role**: `ADMINISTRATOR`
- **Story**: As a campus operations administrator, I want to assign unassigned tickets to qualified technicians, so that work orders are scheduled efficiently.
- **Priority**: **Must Have**
- **Acceptance Criteria**:
  - **Given** I am logged in with the `ADMINISTRATOR` role,
  - **When** I select an active staff member from the assignment modal for a `SUBMITTED` ticket,
  - **Then** the ticket's `assigned_staff_id` is updated, the status transitions to `ASSIGNED`,
  - **And** a history log records the assignment action with my admin ID.

---

### US-007: Administrator Rejects an Invalid Ticket with Reason
- **Role**: `ADMINISTRATOR`
- **Story**: As a campus operations administrator, I want to reject duplicate or out-of-scope complaints, so that technicians only work on legitimate issues.
- **Priority**: **Must Have**
- **Acceptance Criteria**:
  - **Given** an open ticket in `SUBMITTED` or `ASSIGNED` status,
  - **When** I reject the ticket without supplying a rejection reason,
  - **Then** the form blocks submission with a validation error,
  - **When** I provide an explanation (minimum 10 characters) and confirm,
  - **Then** the ticket transitions to `REJECTED`, and the reason is recorded and visible to the student.

---

### US-008: Administrator Configures Facility Categories
- **Role**: `ADMINISTRATOR`
- **Story**: As a campus operations administrator, I want to create and manage facility categories, so that reporting options reflect current campus infrastructure.
- **Priority**: **Must Have**
- **Acceptance Criteria**:
  - **Given** I am in the Category Management console,
  - **When** I create a new category ("Laboratory Gas & Fixtures"),
  - **Then** it immediately becomes available in the student ticket filing dropdown,
  - **And** deactivating a category hides it from new submissions while preserving historical ticket associations.

---

### US-009: Administrator Reviews Operational Metrics Dashboard
- **Role**: `ADMINISTRATOR`
- **Story**: As a campus operations administrator, I want to view aggregate ticket metrics, so that I can identify operational bottlenecks and high-incident campus facilities.
- **Priority**: **Should Have**
- **Acceptance Criteria**:
  - **Given** I am on the Admin Overview Dashboard,
  - **When** the page loads,
  - **Then** I see accurate counts of tickets grouped by status, breakdown by priority, and average resolution turnaround times.

---

### US-010: Student Self-Registration & Credential Validation
- **Role**: `STUDENT`
- **Story**: As an unregistered student, I want to register for a personal account, so that I can submit facility reports.
- **Priority**: **Must Have**
- **Acceptance Criteria**:
  - **Given** I am an unauthenticated user on the registration form,
  - **When** I submit a valid institutional email, full name, and strong password (>= 8 chars with uppercase, lowercase, number),
  - **Then** my account is created with the `STUDENT` role,
  - **And** attempting to register with an invalid password format or non-email string returns HTTP 422 with validation errors,
  - **And** attempting to submit privileged role fields in the payload is ignored or rejected.

---

### US-011: User Login, Token Refresh & Silent Rotation
- **Role**: All Users (`STUDENT`, `STAFF`, `ADMINISTRATOR`)
- **Story**: As a registered user, I want to log in securely and maintain an active session without frequent re-authentications.
- **Priority**: **Must Have**
- **Acceptance Criteria**:
  - **Given** valid user credentials,
  - **When** I submit `POST /api/v1/auth/login`,
  - **Then** I receive a 15-minute JWT access token in the response body,
  - **And** a 7-day refresh token in an `HttpOnly`, `SameSite=Lax`, `Secure` cookie,
  - **And** the refresh token hash is stored in the database with a newly minted `family_id`,
  - **When** the access token expires and the client calls `POST /api/v1/auth/refresh` with the cookie,
  - **Then** the server acquires a row lock, atomically consumes the previous token, and issues a rotated refresh cookie inheriting the same `family_id`,
  - **And** if an already-consumed token is presented, the server revokes all remaining active tokens in that `family_id` and returns HTTP 401 Unauthorized,
  - **And** sessions on other devices for that user (with different `family_id` values) remain active.

---

### US-012: Secure Logout & Refresh Token Revocation
- **Role**: All Users (`STUDENT`, `STAFF`, `ADMINISTRATOR`)
- **Story**: As an authenticated user, I want to log out, so that my session cannot be reused on a shared computer.
- **Priority**: **Must Have**
- **Acceptance Criteria**:
  - **Given** I am an authenticated user with an active refresh cookie,
  - **When** I call `POST /api/v1/auth/logout`,
  - **Then** the database marks my active refresh token as revoked (`revoked_at` set),
  - **And** the response clears the refresh token cookie,
  - **And** any subsequent attempt to refresh using that revoked token returns HTTP 401 Unauthorized.

---

### US-013: Administrator Reopens a Resolved or Rejected Ticket
- **Role**: `ADMINISTRATOR`
- **Story**: As a campus operations administrator, I want to reopen a previously resolved or rejected ticket if the repair was incomplete or rejected in error, so that work can resume under the same audit trail.
- **Priority**: **Must Have**
- **Acceptance Criteria**:
  - **Given** a ticket in `RESOLVED` or `REJECTED` status and an authenticated `ADMINISTRATOR`,
  - **When** I submit a reopening request without providing a reason,
  - **Then** the request is rejected with a validation error,
  - **When** I supply a `reopening_reason` (minimum 10 characters) and target status (`ASSIGNED` or `SUBMITTED`),
  - **Then** the ticket transitions to the target status,
  - **And** a new entry is appended to `ticket_status_history` logging the admin ID, previous state, new state, and reopening reason,
  - **And** if a student or staff member attempts to reopen the ticket, the request is rejected with HTTP 403 Forbidden.

---

### US-014: Optimistic Concurrency Conflict Detection
- **Role**: All Users (`STUDENT`, `STAFF`, `ADMINISTRATOR`)
- **Story**: As a system user, I want conflicting concurrent updates to be safely rejected, so that state transitions are not overwritten blindly.
- **Priority**: **Must Have**
- **Acceptance Criteria**:
  - **Given** a ticket currently at version `N`,
  - **When** User A and User B concurrently submit transitions both specifying `expected_version = N`,
  - **Then** the first transaction succeeds and increments the ticket version to `N + 1`,
  - **And** the second transaction detects the version mismatch and is rejected with HTTP 409 Conflict without modifying ticket state.

---

## 5. Unvalidated Assumptions That Require Real-World Investigation

The following assumptions are documented as engineering hypotheses for the initial prototype. They are **not** verified facts and must be investigated during Phase 7 campus pilot feedback:

1. **Location Granularity**:
   - *Assumption*: Plain text location strings (e.g. "Science Block A, Room 302") provide sufficient detail for technicians to find the physical issue.
   - *Investigation Required*: Does the maintenance team need a formal hierarchy (Campus → Building → Floor → Room) or asset tag barcodes to locate equipment quickly?
2. **Category Taxonomy**:
   - *Assumption*: Proposed initial categories (Classroom AV, Electrical, Plumbing, Furniture, HVAC, Network) cover > 90% of routine campus complaints.
   - *Investigation Required*: Do university facility departments operate separate plumbing vs. mechanical teams that require distinct specialized sub-categories?
3. **Staff Triage Model**:
   - *Assumption*: Centralized administrative triage combined with staff self-claiming represents the optimal dispatch workflow.
   - *Investigation Required*: Do real campus facility departments prefer automated round-robin routing based on category or technician shift schedules?
4. **Student Communication Preferences**:
   - *Assumption*: In-app status tracking is sufficient for students without immediate SMS or push notifications.
   - *Investigation Required*: Will students actively check the web portal, or does low portal return traffic lead to abandoned tickets without email/SMS alerts?
5. **Network Connectivity in Campus Basements**:
   - *Assumption*: Facilities technicians have continuous 4G/Wi-Fi connectivity while executing repairs.
   - *Investigation Required*: Do campus maintenance personnel routinely work in network-dead basements or service tunnels requiring offline work caching?
