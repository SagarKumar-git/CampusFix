# Phase 1 Acceptance Criteria & Verification Matrix — CampusFix

| Document Version | 1.0.0 |
| :--- | :--- |
| **Status** | Approved Acceptance Matrix |
| **Maintainer** | Senior QA Engineer & Frontend Architect |
| **Scope** | Verification Criteria for SCR-01 through SCR-09 & Design System |
| **Last Updated** | 2026-10-27 (UTC) |

---

## 1. Overview & Verification Methodology

This matrix establishes the definitive acceptance criteria for all Phase 1 deliverables. These criteria will serve as the testing foundation for Vitest, React Testing Library, and end-to-end browser tests in Phase 4 and Phase 5.

Every criterion is testable, unambiguous, and mapped to specific Functional Requirements (FR) and Non-Functional Requirements (NFR).

---

## 2. Screen-by-Screen Acceptance Criteria

### SCR-01: Authentication Portal (`/login`, `/register`)
- [ ] **AC-SCR01-01 (Role Gating)**: Authenticated users navigating to `/login` or `/register` are automatically redirected to their role home (`/student/tickets`, `/staff/queue`, or `/admin/dashboard`).
- [ ] **AC-SCR01-02 (Registration Constraints)**: Form blocks submission if password is < 8 characters, lacks numbers, or lacks uppercase/lowercase characters (`FR-001`).
- [ ] **AC-SCR01-03 (Role Assignment)**: Successful public registration only creates accounts with the `STUDENT` role (`FR-001`, `FR-002`).
- [ ] **AC-SCR01-04 (Credential Failure)**: Submitting incorrect password triggers HTTP 401 response and renders the top error banner without losing the email input value (`FR-003`).
- [ ] **AC-SCR01-05 (Accessibility)**: All form inputs possess programmatic `<label>` associations; password visibility toggle has dynamic `aria-label` attribute (`NFR-011`).

### SCR-02: Student Portal / My Tickets (`/student/tickets`)
- [ ] **AC-SCR02-01 (Isolation / IDOR)**: Query results strictly contain tickets where `creator_id == current_user.id` (`FR-012`).
- [ ] **AC-SCR02-02 (Empty State)**: When student has zero tickets, an illustrated empty state renders with an actionable "Report Your First Issue" CTA button (`NFR-013`).
- [ ] **AC-SCR02-03 (Filtering)**: Selecting status filter "RESOLVED" re-queries `/api/v1/tickets?status=RESOLVED` without a full page reload.
- [ ] **AC-SCR02-04 (Pagination)**: Pagination bar displays active page, total items, and disables "Previous" on page 1 (`NFR-009`).
- [ ] **AC-SCR02-05 (Responsive Layout)**: On screen widths < 768px, table collapses into stacked cards with full touch target areas (`NFR-012`).

### SCR-03: Ticket Submission Flow (`/tickets/new`)
- [ ] **AC-SCR03-01 (Category Loading)**: Form fetches active categories from `GET /api/v1/categories`; inactive categories are not displayed (`FR-025`).
- [ ] **AC-SCR03-02 (Field Validation)**: Title < 5 chars, Description < 10 chars, or unselected Category prevents form submission and displays inline error messages (`FR-009`).
- [ ] **AC-SCR03-03 (Default Priority)**: Priority selector initializes with `MEDIUM` selected (`FR-009`).
- [ ] **AC-SCR03-04 (Creation & Redirect)**: Successful submission (HTTP 201) immediately redirects the browser to `SCR-04` (`/tickets/:id`) with success notification (`FR-010`).
- [ ] **AC-SCR03-05 (Submission Debounce)**: Submitting button is disabled and displays a spinner while the network call is pending to prevent duplicate submissions.

### SCR-04: Ticket Detail & Timeline (`/tickets/:id`)
- [ ] **AC-SCR04-01 (Resource Authorization)**: A student attempting to open a ticket belonging to another user receives an HTTP 404/403 not found screen (`FR-012`).
- [ ] **AC-SCR04-02 (Dynamic Actions)**:
  - If user is `STUDENT` and status is `SUBMITTED` or `ASSIGNED`: "Cancel Ticket" button is visible (`FR-016`).
  - If status is `IN_PROGRESS`: "Cancel Ticket" button is hidden/disabled (`FR-016`).
  - If user is `STAFF`: "Begin Work" visible if `ASSIGNED`; "Resolve" visible if `IN_PROGRESS`.
  - If user is `ADMINISTRATOR` and status is `RESOLVED` or `REJECTED`: "Reopen Ticket" button is visible (`FR-014`).
- [ ] **AC-SCR04-03 (Audit History)**: Timeline renders all audit history records chronologically with author, timestamps, prior/new status, and transition notes (`FR-017`).
- [ ] **AC-SCR04-04 (Resolution Notes Callout)**: If status is `RESOLVED`, the resolution notes are displayed in a prominent green callout box (`FR-015`).

### SCR-05: Staff Workbench Queue (`/staff/queue`)
- [ ] **AC-SCR05-01 (Role Gating)**: Access by `STUDENT` role returns HTTP 403 Forbidden.
- [ ] **AC-SCR05-02 (Tab Segregation)**: "Assigned to Me" tab strictly shows tickets where `assigned_staff_id == current_user.id`; "Unassigned Pool" shows `status == SUBMITTED` tickets (`FR-019`).
- [ ] **AC-SCR05-03 (Self-Claim Action)**: Clicking "Claim Ticket" from Unassigned Pool updates `assigned_staff_id`, shifts status to `ASSIGNED`, and decrements unassigned count (`FR-020`).
- [ ] **AC-SCR05-04 (Start Work Action)**: Clicking "Start Work" transitions ticket to `IN_PROGRESS` and logs the timestamp (`FR-021`).

### SCR-06: Resolution & Note Dialogs (Modal Overlays)
- [ ] **AC-SCR06-01 (Character Minimum)**: Submit button is disabled until the notes/reason textarea contains at least 10 non-whitespace characters (`FR-015`).
- [ ] **AC-SCR06-02 (Focus Trap & Dismissal)**: Modal traps keyboard focus; pressing `Escape` closes the modal without submitting (`NFR-011`).
- [ ] **AC-SCR06-03 (Concurrency Conflict)**: If the backend returns HTTP 409 Conflict, an error banner is shown inside the dialog prompting user to reload (`FR-018`).
- [ ] **AC-SCR06-04 (Reopen Target Selection)**: Reopen dialog requires admin to choose target status (`ASSIGNED` or `SUBMITTED`) (`FR-014`).

### SCR-07: Admin Operations Dashboard (`/admin/dashboard`)
- [ ] **AC-SCR07-01 (Role Gating)**: Access is strictly limited to `ADMINISTRATOR`.
- [ ] **AC-SCR07-02 (Metrics Accuracy)**: Total ticket counts, status distributions, and priority breakdowns match `GET /admin/dashboard/metrics` response payload (`FR-027`).
- [ ] **AC-SCR07-03 (Direct Dispatch)**: Dispatch dropdown allows assigning any active technician to unassigned tickets directly from the table (`FR-024`).

### SCR-08: Category Management Console (`/admin/categories`)
- [ ] **AC-SCR08-01 (Category Creation)**: Administrator can add a new category with name and description; category immediately appears in the table (`FR-025`).
- [ ] **AC-SCR08-02 (Deactivation)**: Toggling a category to inactive sets `is_active = false` and updates badge to `INACTIVE` without deleting historical tickets (`FR-025`).
- [ ] **AC-SCR08-03 (Name Uniqueness)**: Duplicate category names trigger inline error feedback.

### SCR-09: User Directory & Role Manager (`/admin/users`)
- [ ] **AC-SCR09-01 (User Search)**: Searching by name or email filters the list with a 300ms debounce.
- [ ] **AC-SCR09-02 (Role Modification)**: Upgrading a user's role to `STAFF` or `ADMINISTRATOR` sends `PATCH /admin/users/{id}/role` and updates role badge immediately (`FR-026`).
- [ ] **AC-SCR09-03 (Self-Modification Guard)**: The logged-in administrator's own account has role modification controls disabled to prevent accidental administrative lockouts.

---

## 3. Design System & Accessibility (WCAG 2.1 AA) Verification

| Checklist Item | Target Standard | Verification Method |
| :--- | :--- | :--- |
| **Color Contrast (Text)** | Normal text >= 4.5:1, Large text >= 3.0:1 | Automated axe-core / Lighthouse audit |
| **Color Contrast (UI Components)** | Input borders, focus rings, status badges >= 3.0:1 | Color meter / token verification |
| **Keyboard Operability** | All interactive elements navigable via `Tab` / `Shift+Tab` | Manual keyboard pass without mouse |
| **Focus Visible** | 2px solid ring with 2px offset on all focused elements | Visual focus indicator check |
| **Form Labels** | Explicit `<label for="...">` or `aria-labelledby` | Screen reader & DOM inspector check |
| **Error Feedback** | Inline errors connected with `aria-describedby` | Accessibility tree inspection |
| **Dialog Modals** | `role="dialog"`, `aria-modal="true"`, focus trapped | Modal navigation audit |
| **Responsive Scalability** | No horizontal scrolling or overlap from 360px to 1920px | Chrome DevTools viewport resizing |
