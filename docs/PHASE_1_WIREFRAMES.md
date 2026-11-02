# Phase 1 Wireframe & Screen Specifications — CampusFix

| Document Version | 1.0.0 |
| :--- | :--- |
| **Status** | Implementation-Ready Design Baseline |
| **Maintainer** | Senior UI/UX Designer & Frontend Design-System Architect |
| **Scope** | Complete Screen Specifications for SCR-01 through SCR-09 |
| **Last Updated** | 2026-10-27 (UTC) |

---

## 1. Overview & Screen Inventory

This specification establishes the authoritative visual and interaction blueprint for all nine screens in CampusFix. Each screen specification details layout hierarchy, desktop/mobile ASCII wireframes, UI components, deterministic states (loading, empty, error, success), accessibility attributes, responsive breakpoints, API contracts, and testable acceptance criteria.

| Screen ID | Screen Name | Authorized Roles | Primary Route | Relevant Endpoints |
| :--- | :--- | :--- | :--- | :--- |
| **SCR-01** | **Authentication Portal** | Public (Unauthenticated) | `/login`, `/register` | `POST /auth/login`, `POST /auth/register` |
| **SCR-02** | **Student Portal / My Tickets** | `STUDENT` | `/student/tickets` | `GET /tickets?page=&page_size=&status=` |
| **SCR-03** | **Ticket Submission Flow** | `STUDENT`, `ADMINISTRATOR` | `/tickets/new` | `GET /categories`, `POST /tickets` |
| **SCR-04** | **Ticket Detail & Timeline** | Authenticated (Role-Gated) | `/tickets/:id` | `GET /tickets/:id`, `GET /tickets/:id/history` |
| **SCR-05** | **Staff Workbench Queue** | `STAFF` | `/staff/queue` | `GET /tickets`, `POST /tickets/:id/assign`, `POST /tickets/:id/transition` |
| **SCR-06** | **Resolution & Note Dialogs** | `STAFF`, `ADMINISTRATOR`, `STUDENT` | Modals on `/tickets/:id` | `POST /tickets/:id/transition` |
| **SCR-07** | **Admin Operations Dashboard** | `ADMINISTRATOR` | `/admin/dashboard` | `GET /admin/dashboard/metrics`, `GET /tickets` |
| **SCR-08** | **Category Management Console** | `ADMINISTRATOR` | `/admin/categories` | `GET /categories`, `POST /categories`, `PATCH /categories/:id` |
| **SCR-09** | **User Directory & Role Manager**| `ADMINISTRATOR` | `/admin/users` | `GET /admin/users`, `PATCH /admin/users/:id/role` |

---

## 2. Screen Specifications

```text
====================================================================================================
SCR-01: AUTHENTICATION PORTAL (LOGIN & STUDENT REGISTRATION)
====================================================================================================
```

### 1. Purpose & Authorized Roles
- **Purpose**: Provides secure user authentication for all roles and self-registration exclusively for students.
- **Authorized Roles**: Public / Unauthenticated. (Authenticated users visiting this screen are automatically redirected to their role-specific landing page: `/student/tickets`, `/staff/queue`, or `/admin/dashboard`).

### 2. Information Hierarchy & Page Layout
- Center-aligned floating authentication card with neutral canvas background (`bg-neutral-50`).
- Top banner: CampusFix Brand Logo, wordmark, and institutional disclaimer.
- Mode Selector: Segmented tabs toggle between **"Sign In"** and **"Create Student Account"**.
- Single-column form structure with clear vertical rhythm, explicit labels, and password visibility toggle.
- Bottom helper text: Institutional password policy and help contact link.

### 3. ASCII Wireframes

#### Desktop Viewport (1280px)
```text
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|                                    [ CampusFix Mark ]                                            |
|                                        CampusFix                                                 |
|                        Campus Facilities Incident Management Portal                              |
|                                                                                                  |
|                      +----------------------------------------------------+                      |
|                      |   [ Sign In (Active) ]   |  [ Register (Student) ] |                      |
|                      +----------------------------------------------------+                      |
|                      |                                                    |                      |
|                      |  Email Address *                                   |                      |
|                      |  [ jane.doe@university.edu                       ] |                      |
|                      |                                                    |                      |
|                      |  Password *                             [ Show ]   |                      |
|                      |  [ *******************                           ] |                      |
|                      |                                                    |                      |
|                      |  +----------------------------------------------+  |                      |
|                      |  | [!] Invalid email or password. Please retry. |  |  (Error Alert)       |
|                      |  +----------------------------------------------+  |                      |
|                      |                                                    |                      |
|                      |  [               Sign In to Portal             ]  |  (Primary CTA)       |
|                      |                                                    |                      |
|                      |  ----------------------- OR ---------------------- |                      |
|                      |                                                    |                      |
|                      |  New campus resident? Switch to Registration above |                      |
|                      |                                                    |                      |
|                      +----------------------------------------------------+                      |
|                                                                                                  |
|                     Demo notice: Privileged Staff & Admin accounts are seeded.                   |
+--------------------------------------------------------------------------------------------------+
```

#### Mobile Viewport (375px)
```text
+-----------------------------------+
| [CampusFix] Campus Incident Portal|
+-----------------------------------+
| [ Sign In (Active) ] [ Register ] |
|-----------------------------------|
| Email Address *                   |
| [ student@univ.edu              ] |
|                                   |
| Password *               [ Show ] |
| [ ********                      ] |
|                                   |
| [        Sign In to Portal      ] |
|                                   |
| Need an account? Tap Register tab |
|                                   |
| Notice: Synthetic demo accounts   |
+-----------------------------------+
```

### 4. Components, Fields & Controls
- **Segmented Control Tabs**: Toggle between Login (`/login`) and Register (`/register`).
- **Fields (Login)**:
  - `email`: Text input, type `email`, autocomplete `username`, required.
  - `password`: Text input, type `password`, autocomplete `current-password`, required, with visibility toggle button.
- **Fields (Registration)**:
  - `full_name`: Text input, type `text`, min 2, max 100 chars, autocomplete `name`, required.
  - `email`: Text input, type `email`, format validation (`*@*.*`), required.
  - `password`: Password input with interactive rule checklist:
    - Min 8 characters
    - At least 1 number
    - At least 1 uppercase letter
    - At least 1 lowercase letter
- **Buttons**:
  - `Submit CTA`: Full width, primary brand style (`bg-brand-600 text-white hover:bg-brand-700`). Shows loading spinner during submission.

### 5. UI States
- **Idle**: Clean form with placeholder hints and inactive submit button state until minimum constraints met.
- **Submitting (Loading)**: Primary button disabled, spinner rendered, inputs read-only.
- **Validation Error (Inline)**: Red border on affected input, error message below field linked via `aria-describedby`.
- **Server Error (Top Banner)**: Red alert banner (`bg-red-50 text-red-800 border-red-200`) at the top of the card detailing rejection (e.g. `Invalid credentials` or `Email already registered`).
- **Success (Registration)**: Card transitions into a green success checkmark with button: "Registration successful! Please Sign In".

### 6. Validation Rules & Feedback
- Email regex: `/^[^\s@]+@[^\s@]+\.[^\s@]+$/`
- Password regex: `/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/`
- Immediate inline error cleared upon user input (`onChange`).

### 7. Accessibility (WCAG 2.1 AA)
- Semantic `<form>` with `<fieldset>` and distinct `<label>` tags linked via `htmlFor`.
- Password visibility toggle has `aria-label="Show password as plain text"` / `aria-label="Hide password"`.
- Focus trapped within active form elements, initial focus set to `email` input upon mount.

### 8. Responsive Behavior
- **Desktop (1280px)**: Centered card width 440px with generous 32px padding, elevated shadow (`shadow-md`).
- **Tablet (768px)**: Centered card width 400px.
- **Mobile (375px)**: Edge-to-edge layout with 16px horizontal margins, card flat border with subtle shadow.

### 9. API Integrations
- `POST /api/v1/auth/login` (body: `{email, password}`)
- `POST /api/v1/auth/register` (body: `{full_name, email, password}`)
- Sets `HttpOnly` refresh cookie on login and persists in-memory JWT.

### 10. Testable Acceptance Criteria
- **AC-01.1**: Successful login redirects `STUDENT` to `/student/tickets`, `STAFF` to `/staff/queue`, and `ADMINISTRATOR` to `/admin/dashboard`.
- **AC-01.2**: Attempting to submit registration with non-matching password rules displays inline validation errors and prevents network call.
- **AC-01.3**: Failed login response (401) renders top banner with exact error message and retains the entered email address.

---

```text
====================================================================================================
SCR-02: STUDENT PORTAL / MY TICKETS
====================================================================================================
```

### 1. Purpose & Authorized Roles
- **Purpose**: Gives students immediate visibility over all campus tickets they have reported, their statuses, assigned staff, and quick access to report a new issue or cancel an open report.
- **Authorized Roles**: `STUDENT` only.

### 2. Information Hierarchy & Page Layout
- **Topbar**: Logo, Brand, "My Tickets" active tab, "+ Report Issue" primary CTA, and User Profile avatar dropdown.
- **Page Header**: "Campus Facility Reports" title, summary count ("Showing 3 tickets"), and filter bar.
- **Filter Toolbar**:
  - Search input (searches ticket number or title).
  - Status filter dropdown (`ALL`, `SUBMITTED`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `REJECTED`, `CANCELLED`).
  - Priority filter dropdown (`ALL`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- **Main Area**: Responsive ticket card grid (cards on mobile/tablet, rich table on desktop).
- **Pagination Footer**: Page size selector (20, 50) and Next/Prev buttons.

### 3. ASCII Wireframes

#### Desktop Viewport (1280px)
```text
+--------------------------------------------------------------------------------------------------+
| CampusFix  [ My Tickets ]                          [ + Report Issue ]  [ Jane Doe (Student) v ]  |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  My Submitted Tickets                                                                            |
|  Track and manage facility issues you reported across campus.                                    |
|                                                                                                  |
|  +--------------------------------------------------------------------------------------------+  |
|  | Search by ID or title... [Q] | Status: [ All Statuses v ] | Priority: [ All Priorities v ] |  |
|  +--------------------------------------------------------------------------------------------+  |
|                                                                                                  |
|  +--------------------------------------------------------------------------------------------+  |
|  | TICKET ID      | TITLE & LOCATION            | CATEGORY       | PRIORITY | STATUS   | ACTION   |  |
|  |----------------|-----------------------------|----------------|----------|----------|----------|  |
|  | CFX-2026-00042 | Projector HDMI Port Damaged | Classroom AV   | HIGH     | IN PROGR | View >   |  |
|  |                | Science Block A, Room 402   |                |          | [Purple] |          |  |
|  |----------------|-----------------------------|----------------|----------|----------|----------|  |
|  | CFX-2026-00038 | Water Leak Under Sink       | Plumbing       | CRITICAL | ASSIGNED | View >   |  |
|  |                | Hostel 3, 2nd Floor Restroom|                |          | [Amber]  |          |  |
|  |----------------|-----------------------------|----------------|----------|----------|----------|  |
|  | CFX-2026-00019 | Broken Desk Chair Rest      | Furniture      | LOW      | RESOLVED | View >   |  |
|  |                | Main Library, Cubicle 12    |                |          | [Green]  |          |  |
|  +--------------------------------------------------------------------------------------------+  |
|                                                                                                  |
|  Showing 1 - 3 of 3 tickets                             Page 1 of 1   [ < Prev ]  [ Next > ]     |
+--------------------------------------------------------------------------------------------------+
```

#### Mobile Viewport (375px)
```text
+-----------------------------------+
| = CampusFix          [ + Report ] |
+-----------------------------------+
| My Tickets (3)                    |
| [ Search tickets...             ] |
| Status: [ All Statuses v ]        |
|-----------------------------------|
| [CFX-2026-00042]            HIGH  |
| Projector HDMI Port Damaged       |
| Science Block A, Room 402         |
| Status: (o) IN PROGRESS           |
| Category: Classroom AV            |
| [ View Details & Timeline > ]     |
|-----------------------------------|
| [CFX-2026-00038]        CRITICAL  |
| Water Leak Under Sink             |
| Hostel 3, Restroom                |
| Status: (o) ASSIGNED              |
| [ View Details & Timeline > ]     |
+-----------------------------------+
| [ Tickets ]   [ + Report ]   [ Me]| (Bottom Nav)
+-----------------------------------+
```

### 4. Components, Fields & Controls
- **Filter Bar**: Text search (debounced 300ms), Status select, Priority select, Clear Filters button.
- **Ticket Table (Desktop)**: Columns: Code, Title + Location, Category, Priority Badge, Status Badge, Action Link.
- **Ticket Card (Mobile)**: Stacked cards with elevation `shadow-sm`, bold title, monospace ID pill, status dot.
- **Empty State Container**: Illustrated SVG, "No issues reported yet", and primary CTA button "Report an Issue".
- **Floating CTA (Mobile)**: Bottom navigation center button for quick 1-tap issue intake.

### 5. UI States
- **Loading State**: 5 rows of animated pulse skeleton bars (`animate-pulse bg-neutral-200`) preserving layout height.
- **Empty State (Zero Submissions)**: "You haven't reported any campus facility issues. See something broken? Let our maintenance team know." + Button: "+ Report Your First Issue".
- **Empty State (Filtered Out)**: "No tickets match your active filter criteria." + Button: "Reset Filters".
- **Error State**: Banner: "Unable to load tickets due to a server connection failure." + Button: "Retry".

### 6. Validation & Data Rules
- Server-side filter binding directly maps to `GET /api/v1/tickets?status=&priority=&page=&page_size=`.
- Strict IDOR defense: Results strictly restricted by backend to `creator_id == current_user.id`.

### 7. Accessibility (WCAG 2.1 AA)
- Data table features `<caption>` visually hidden (`sr-only`) describing the table content.
- Column headers have `scope="col"`.
- Row items link to details via entire row click target with keyboard focus indicator on `<a href="/tickets/CFX-...">`.

### 8. Responsive Behavior
- **Desktop (1280px)**: Full multi-column data table with horizontal hover highlighting (`hover:bg-neutral-50`).
- **Tablet (768px)**: Condensed table omitting Category column (rendered as subtext below title).
- **Mobile (375px)**: Complete transformation to stacked cards; table headers hidden. Bottom navigation enabled.

### 9. API Integrations
- `GET /api/v1/tickets?page=1&page_size=20&status=&priority=`
- Headers: `Authorization: Bearer <access_token>`.

### 10. Testable Acceptance Criteria
- **AC-02.1**: Student only sees tickets they created; tickets belonging to other students never appear.
- **AC-02.2**: Selecting status filter "RESOLVED" appends query parameter `status=RESOLVED` and re-fetches list.
- **AC-02.3**: Clicking "+ Report Issue" navigates to `/tickets/new`.

---

```text
====================================================================================================
SCR-03: TICKET SUBMISSION FLOW
====================================================================================================
```

### 1. Purpose & Authorized Roles
- **Purpose**: Friction-free, single-page incident intake form enabling students (and admins) to submit facility issues in under 60 seconds.
- **Authorized Roles**: `STUDENT`, `ADMINISTRATOR`.

### 2. Information Hierarchy & Page Layout
- **Breadcrumb**: `Home / My Tickets / Report Facility Issue`.
- **Card Container**: Max width 680px, centered on canvas with high-contrast header and descriptive subhead.
- **Form Layout**:
  1. Incident Category (Dropdown populated from active categories).
  2. Location Details (Structured text string with contextual placeholder).
  3. Priority Selector (Radio card group with Low, Medium, High, Critical descriptions).
  4. Issue Title (High-level summary).
  5. Detailed Description (Detailed defect context with character counter).
- **Footer**: Cancel button (returns to `/student/tickets`) and Submit button.

### 3. ASCII Wireframes

#### Desktop Viewport (1280px)
```text
+--------------------------------------------------------------------------------------------------+
| CampusFix  [ My Tickets ]                                              [ Jane Doe (Student) v ]  |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  < Back to My Tickets                                                                            |
|                                                                                                  |
|                      +----------------------------------------------------+                      |
|                      | Report a Campus Facility Issue                     |                      |
|                      | Provide details below so maintenance can dispatch. |                      |
|                      |----------------------------------------------------|                      |
|                      | Facility Category *                                |                      |
|                      | [ Select category (e.g. Classroom AV, Plumbing)  v]|                      |
|                      |                                                    |                      |
|                      | Specific Location *                                |                      |
|                      | [ e.g. Science Block A, Room 402                   ] |                      |
|                      | Helper: Include building, floor, and room number.  |                      |
|                      |                                                    |                      |
|                      | Severity / Priority *                              |                      |
|                      | ( ) Low      (*) Medium     ( ) High   ( ) Critical|                      |
|                      |                                                    |                      |
|                      | Issue Summary / Title *                            |                      |
|                      | [ Projector HDMI port damaged and bent           ] |                      |
|                      | 44 / 120 characters                                |                      |
|                      |                                                    |                      |
|                      | Detailed Description *                             |                      |
|                      | +------------------------------------------------+ |                      |
|                      | | The HDMI wall input in Room 402 is damaged.    | |                      |
|                      | | Laptops cannot connect for lecture slides.     | |                      |
|                      | |                                                | |                      |
|                      | +------------------------------------------------+ |                      |
|                      | 94 / 2000 characters (min 10)                      |                      |
|                      |                                                    |                      |
|                      |----------------------------------------------------|                      |
|                      | [ Cancel ]                   [ Submit Work Order ] |                      |
|                      +----------------------------------------------------+                      |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

#### Mobile Viewport (375px)
```text
+-----------------------------------+
| < Cancel      Report Facility Defect
+-----------------------------------+
| Category *                        |
| [ Classroom Audio-Visual        v]|
|                                   |
| Location *                        |
| [ Science Block A, Room 402     ] |
|                                   |
| Priority *                        |
| [ Low ] [* Med *] [ High ] [ Crit]|
|                                   |
| Title *                           |
| [ Projector HDMI damaged        ] |
| 25 / 120 chars                    |
|                                   |
| Description * (min 10 chars)      |
| +-------------------------------+ |
| | The HDMI port is bent and     | |
| | cannot connect to laptops.    | |
| +-------------------------------+ |
| 58 / 2000 chars                   |
|                                   |
| [       Submit Work Order       ] |
+-----------------------------------+
```

### 4. Components, Fields & Controls
- **Category Select**: Custom accessible select box populated via `GET /api/v1/categories`. Only active categories rendered.
- **Location Input**: Text input, min 3 chars, max 100 chars.
- **Priority Radio Group**: 4 segmented radio pills with visual badge accents (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`). Default is `MEDIUM`.
- **Title Input**: Text input, min 5 chars, max 120 chars, with dynamic counter.
- **Description Textarea**: Multi-line textarea (5 rows), min 10 chars, max 2000 chars, with character counter.
- **Actions**: Secondary "Cancel" link button, Primary "Submit Work Order" button with loading spinner.

### 5. UI States
- **Category Loading State**: Dropdown shows animated placeholder "Loading campus categories...".
- **Category Load Error**: Amber banner: "Unable to load facility categories. Please refresh."
- **Submitting State**: Submit button displays loading spinner, all fields disabled to prevent duplicate submissions.
- **Validation Failure State**: Red field borders and helper error messages:
  - "Title must be between 5 and 120 characters."
  - "Description must provide at least 10 characters of detail."
  - "Please specify the campus location."
- **Submission Success**: Redirects immediately to `SCR-04` (`/tickets/:id`) with success toast: "Ticket CFX-2026-00042 submitted successfully."

### 6. Validation & Feedback Rules
- Client enforces synchronous validation before dispatching `POST /api/v1/tickets`.
- Character counter changes color to amber at 90% limit, and red when limit is breached.

### 7. Accessibility (WCAG 2.1 AA)
- Radio group contained in `<fieldset>` with `<legend class="text-xs font-semibold uppercase">Severity / Priority</legend>`.
- Keyboard arrow keys navigate between priority radio buttons (`ArrowRight`, `ArrowLeft`).
- Error messages explicitly connected using `aria-describedby="title-error"`.

### 8. Responsive Behavior
- **Desktop (1280px)**: 680px centered card with 32px padding.
- **Tablet (768px)**: Full width container with 24px horizontal padding.
- **Mobile (375px)**: Priority selector renders as a 4-column horizontal pill group; full-bleed buttons at bottom.

### 9. API Integrations
- `GET /api/v1/categories` (Fetch active categories on mount).
- `POST /api/v1/tickets` (Body: `{title, description, category_id, location, priority}`).

### 10. Testable Acceptance Criteria
- **AC-03.1**: Submitting without a category or with title < 5 chars blocks submission with inline error messages.
- **AC-03.2**: On successful creation (HTTP 201), user is redirected to the ticket detail page (`/tickets/:id`).
- **AC-03.3**: Default priority selection is always initialized to `MEDIUM`.

---

```text
====================================================================================================
SCR-04: TICKET DETAIL & TIMELINE
====================================================================================================
```

### 1. Purpose & Authorized Roles
- **Purpose**: Authoritative single-view display for a specific ticket, rendering incident metadata, current lifecycle state banner, assigned staff technician, and the full chronological audit history. Contains role-specific action buttons (Cancel, Assign, Begin Work, Resolve, Reject, Reopen).
- **Authorized Roles**: All authenticated roles (Resource-isolated: students can only open their own tickets; staff and admins can open any ticket).

### 2. Information Hierarchy & Page Layout
- **Header**: Ticket reference code (`CFX-2026-00042`), submission timestamp, status badge, priority badge, and dynamic action buttons based on role and current status.
- **Two-Column Layout (Desktop)**:
  - **Left / Main Column (65%)**:
    - Current State Overview Banner.
    - Full Incident Description & Category/Location meta.
    - Resolution / Rejection Notes Box (if resolved/rejected).
    - Chronological Status & Assignment Audit Timeline.
  - **Right / Sidebar Column (35%)**:
    - Reporter Details Card (Full name, student email, creation date).
    - Assignment Card (Technician name or "Unassigned", with quick assign button for Admin/Staff).
    - Metadata Card (UUID, version integer, last updated timestamp).

### 3. ASCII Wireframes

#### Desktop Viewport (1280px)
```text
+--------------------------------------------------------------------------------------------------+
| CampusFix  [ My Tickets ]                                              [ Jane Doe (Student) v ]  |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  < Back to Tickets                                                                               |
|                                                                                                  |
|  TICKET CFX-2026-00042              [ PRIORITY: HIGH ]  [ IN PROGRESS (Purple) ]                 |
|  Projector HDMI Port Damaged                                                                     |
|                                                     [ Cancel Ticket ] (Student Action)           |
|                                                     [ Resolve Work Order ] [ Reject ] (Staff/Adm)|
|  +-----------------------------------------------------+ +------------------------------------+  |
|  | CURRENT STATE OVERVIEW                              | | TICKET ASSIGNMENT                  |  |
|  | Work is currently in progress by technician.        | | Assigned Tech: Alex Rivera (Staff) |  |
|  | Started: Oct 27, 2026 at 14:00 UTC                  | | Assigned on: Oct 27, 2026 13:50    |  |
|  +-----------------------------------------------------+ +------------------------------------+  |
|  | INCIDENT DETAILS                                    | | REPORTER INFORMATION               |  |
|  | Location: Science Block A, Lecture Room 402         | | Name: Jane Doe                     |  |
|  | Category: Classroom Audio-Visual                    | | Role: Campus Student               |  |
|  | Description:                                        | | Email: jane.doe@university.edu     |  |
|  | The HDMI wall input is bent and will not establish  | +------------------------------------+  |
|  | connection with laptops during morning lectures.    | | SYSTEM METADATA                    |  |
|  +-----------------------------------------------------+ | Version: 2 (Optimistic Lock)       |  |
|  | AUDIT HISTORY TIMELINE                              | | Created: Oct 27, 2026 13:40 UTC    |  |
|  |                                                     | | Updated: Oct 27, 2026 14:00 UTC    |  |
|  | (o) IN_PROGRESS — Oct 27, 14:00 UTC                 | +------------------------------------+  |
|  |     By: Alex Rivera (Staff)                         |                                         |
|  |     Notes: Arrived on site with replacement kit.    |                                         |
|  |                                                     |                                         |
|  | (o) ASSIGNED — Oct 27, 13:50 UTC                    |                                         |
|  |     By: Marcus Vance (Admin) -> To: Alex Rivera     |                                         |
|  |     Notes: Dispatched to AV repair specialist.      |                                         |
|  |                                                     |                                         |
|  | (o) SUBMITTED — Oct 27, 13:40 UTC                   |                                         |
|  |     By: Jane Doe (Student)                          |                                         |
|  |     Notes: Ticket submitted.                        |                                         |
|  +-----------------------------------------------------+                                         |
+--------------------------------------------------------------------------------------------------+
```

#### Mobile Viewport (375px)
```text
+-----------------------------------+
| < Back     CFX-2026-00042         |
+-----------------------------------+
| [ IN PROGRESS ]   [ HIGH PRIORITY]|
| Projector HDMI Port Damaged       |
|                                   |
| [ Mark Work as Resolved ] (Staff) |
| [ Cancel My Ticket ] (Student)    |
|-----------------------------------|
| INCIDENT DETAILS                  |
| Location: Science Block A, Rm 402 |
| Category: Classroom Audio-Visual  |
| Description:                      |
| The HDMI wall input is bent and   |
| cannot connect to laptops.        |
|-----------------------------------|
| ASSIGNED TO:                      |
| Alex Rivera (Facilities Staff)    |
|-----------------------------------|
| AUDIT TIMELINE                    |
| (o) IN PROGRESS - Oct 27, 14:00   |
|     Tech: Alex Rivera             |
| (o) ASSIGNED - Oct 27, 13:50      |
|     Assigned to Alex Rivera       |
| (o) SUBMITTED - Oct 27, 13:40     |
|     By: Jane Doe                  |
+-----------------------------------+
```

### 4. Components, Fields & Controls
- **Status Header**: Displays badge, priority indicator, and action buttons.
- **Dynamic Action Bar**:
  - `STUDENT`: "Cancel Ticket" button (visible only when status is `SUBMITTED` or `ASSIGNED`).
  - `STAFF`: "Claim Ticket" (if unassigned), "Begin Work" (if `ASSIGNED`), "Resolve Work Order" (if `IN_PROGRESS`).
  - `ADMINISTRATOR`: "Assign Technician", "Resolve", "Reject Ticket", "Reopen Ticket" (if `RESOLVED` or `REJECTED`).
- **Audit Timeline**: Vertical timeline component with colored node indicators, timestamps, actor names, and transition comments.
- **Resolution Box**: Highlighted green callout rendered when status is `RESOLVED` displaying `resolution_notes`.
- **Rejection Box**: Highlighted red callout rendered when status is `REJECTED` displaying `rejection_reason`.

### 5. UI States
- **Loading State**: Two-column skeleton layout with shimmering placeholders for details, sidebar, and timeline nodes.
- **Error State (404 / IDOR)**: Clean 404 container: "Ticket not found or you do not have permission to view it." + Button: "Back to Tickets".
- **Error State (500)**: "Failed to load ticket details." + Retry button.
- **Optimistic Concurrency State (409 Conflict)**: Alert banner: "This ticket was modified by another user. Reloading latest state..." (automatically refetches `GET /api/v1/tickets/:id`).

### 6. Validation & Business Rule Enforcement
- The client dynamically renders action buttons based on `user.role`, `ticket.status`, and `ticket.creator_id`.
- The current integer `version` is tracked in component state and transmitted as `expected_version` in all mutations.

### 7. Accessibility (WCAG 2.1 AA)
- Audit timeline is structured as an ordered list (`<ol class="relative border-l border-neutral-200">`) with semantic list items (`<li>`).
- Each timeline status node has a hidden screen-reader label: `<span class="sr-only">Transitioned to</span> IN_PROGRESS`.

### 8. Responsive Behavior
- **Desktop (1280px)**: 65% / 35% two-column grid.
- **Tablet (768px)**: Single column with Sidebar rendered below Incident Details and above Timeline.
- **Mobile (375px)**: Single-column vertical stack with full-width primary action buttons fixed at the top of the content.

### 9. API Integrations
- `GET /api/v1/tickets/{id}`
- `GET /api/v1/tickets/{id}/history`
- `POST /api/v1/tickets/{id}/transition`
- `POST /api/v1/tickets/{id}/assign`

### 10. Testable Acceptance Criteria
- **AC-04.1**: Students attempting to load a ticket ID created by another student receive a 404/403 error page.
- **AC-04.2**: When ticket status is `IN_PROGRESS`, student cancellation button is disabled and hidden.
- **AC-04.3**: Timeline renders every entry returned from `/history` in correct reverse-chronological order.

---

```text
====================================================================================================
SCR-05: STAFF WORKBENCH QUEUE
====================================================================================================
```

### 1. Purpose & Authorized Roles
- **Purpose**: High-efficiency operational workbench enabling facilities maintenance staff to review work orders assigned to them, inspect the unassigned triage pool, claim tickets, and transition tickets to In Progress.
- **Authorized Roles**: `STAFF` only.

### 2. Information Hierarchy & Page Layout
- **Topbar**: Logo, Brand, "Staff Queue" active tab, active shift indicator, and Profile avatar.
- **Workbench Sub-Navigation Tabs**:
  - **Tab 1: "Assigned to Me"** (with badge count of active assigned tickets).
  - **Tab 2: "Unassigned Triage Pool"** (tickets in `SUBMITTED` status awaiting pickup).
  - **Tab 3: "Resolved by Me"** (closed historical tickets).
- **Queue Controls**: Fast filter bar (Category select, Priority filter, Sort by: Oldest / Newest / Priority).
- **Ticket Table / List**: Operational columns optimized for technicians (Ticket ID, Priority, Room/Building, Summary, Status, Quick Actions).

### 3. ASCII Wireframes

#### Desktop Viewport (1280px)
```text
+--------------------------------------------------------------------------------------------------+
| CampusFix  [ Staff Workbench ]                                         [ Alex Rivera (Staff) v ] |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  Facilities Maintenance Queue                                                                    |
|                                                                                                  |
|  +--------------------------------------------------------------------------------------------+  |
|  | [ Assigned to Me (4) ]   |   [ Unassigned Pool (7) ]   |   [ My Completed Work (32) ]      |  |
|  +--------------------------------------------------------------------------------------------+  |
|  | Filter by Category: [ All Categories v ] | Priority: [ All v ] | Sort: [ Priority High-Low v]|  |
|  +--------------------------------------------------------------------------------------------+  |
|                                                                                                  |
|  +--------------------------------------------------------------------------------------------+  |
|  | ID & PRIORITY  | LOCATION & DEFECT             | SUBMITTED | STATUS      | QUICK ACTION     |  |
|  |----------------|-------------------------------|-----------|-------------|------------------|  |
|  | CFX-2026-00042 | Science Block A, Room 402     | 2h ago    | IN PROGRESS | [ Open Work > ]  |  |
|  | [HIGH]         | Projector HDMI Port Damaged   |           | [Purple]    |                  |  |
|  |----------------|-------------------------------|-----------|-------------|------------------|  |
|  | CFX-2026-00038 | Hostel 3, Restroom 2nd Floor  | 4h ago    | ASSIGNED    | [ Start Work ]   |  |
|  | [CRITICAL]     | Water Leak Under Main Sink    |           | [Amber]     | [ Open Work > ]  |  |
|  |----------------|-------------------------------|-----------|-------------|------------------|  |
|  | CFX-2026-00040 | Engineering Wing, Lab 101     | 1d ago    | ASSIGNED    | [ Start Work ]   |  |
|  | [MEDIUM]       | Flickering Overhead Tube Light|           | [Amber]     | [ Open Work > ]  |  |
|  +--------------------------------------------------------------------------------------------+  |
|                                                                                                  |
|  Showing 1 - 3 of 4 active work orders                   Page 1 of 1  [ < Prev ]  [ Next > ]     |
+--------------------------------------------------------------------------------------------------+
```

#### Mobile Viewport (375px)
```text
+-----------------------------------+
| CampusFix Staff Workbench     [Q] |
+-----------------------------------+
| [ Assigned (4) ] [ Unassigned (7)]|
| Filter: [ All Categories v ]      |
|-----------------------------------|
| [CFX-2026-00038]         CRITICAL |
| Water Leak Under Main Sink        |
| Location: Hostel 3, Restroom      |
| Status: (o) ASSIGNED              |
|                                   |
| [      Begin Physical Work      ] |
| [ View Incident Details >       ] |
|-----------------------------------|
| [CFX-2026-00042]             HIGH |
| Projector HDMI Port Damaged       |
| Location: Science Block A, Rm 402 |
| Status: (o) IN PROGRESS           |
|                                   |
| [ Mark Work Order Resolved >    ] |
+-----------------------------------+
```

### 4. Components, Fields & Controls
- **Workbench Tab Switcher**: Segmented tab control with live badge counts.
- **Quick Action Buttons**:
  - `Start Work`: Triggers instant state transition to `IN_PROGRESS` via `POST /tickets/{id}/transition`.
  - `Claim Ticket`: Triggers self-assignment via `POST /tickets/{id}/assign` with `staff_id = current_user.id`.
  - `Resolve`: Opens resolution dialog (`SCR-06`).
- **Priority Indicator Badge**: High-contrast colored pill with warning icon for `CRITICAL` issues.

### 5. UI States
- **Loading State**: Table skeleton with pulsing row placeholders.
- **Empty State (Assigned)**: "Great job! You have no pending work orders assigned. Check the Unassigned Pool to claim open issues."
- **Empty State (Unassigned)**: "No unassigned tickets in the campus queue. All incoming reports have been dispatched."
- **Action In-Flight**: Row-level spinner replaces the button during transition to prevent double-click actions.

### 6. Validation & Concurrency Rules
- Passing `expected_version` on every transition request. If another technician claimed or modified the ticket concurrently, a 409 Conflict banner prompts the staff member to refresh the queue.

### 7. Accessibility (WCAG 2.1 AA)
- Tab headers use `role="tablist"` with `aria-selected="true/false"` and `aria-controls="queue-tab-panel"`.
- Keyboard arrow navigation supported across tabs.

### 8. Responsive Behavior
- **Desktop (1280px)**: Compact data grid with inline action buttons.
- **Tablet (768px)**: Table layout with wrapped action button clusters.
- **Mobile (375px)**: Stacked cards with large 48px touch-target action buttons.

### 9. API Integrations
- `GET /api/v1/tickets?assigned_staff_id=me&status=ASSIGNED,IN_PROGRESS`
- `GET /api/v1/tickets?status=SUBMITTED` (for Unassigned Pool)
- `POST /api/v1/tickets/{id}/assign` (Body: `{staff_id, expected_version}`)
- `POST /api/v1/tickets/{id}/transition` (Body: `{target_status: "IN_PROGRESS", expected_version}`)

### 10. Testable Acceptance Criteria
- **AC-05.1**: Clicking "Start Work" immediately transitions ticket status to `IN_PROGRESS` and moves it to active state.
- **AC-05.2**: Clicking "Claim Ticket" from the Unassigned tab binds the ticket to the current staff member and updates the badge count.
- **AC-05.3**: Switching tabs updates the query parameter without causing a full-page reload.

---

```text
====================================================================================================
SCR-06: RESOLUTION & NOTE DIALOGS
====================================================================================================
```

### 1. Purpose & Authorized Roles
- **Purpose**: Accessible modal confirmation dialogs for mandatory status transitions:
  1. **Resolve Dialog** (`STAFF`, `ADMINISTRATOR`): Mandatory resolution notes detailing physical repair.
  2. **Reject Dialog** (`STAFF`, `ADMINISTRATOR`): Mandatory rejection reason explaining out-of-scope or duplicate reports.
  3. **Cancel Dialog** (`STUDENT`): Confirmation dialog for student-initiated ticket cancellation.
  4. **Reopen Dialog** (`ADMINISTRATOR`): Mandatory reopening justification to return closed tickets to the active queue.
- **Authorized Roles**: Role-specific per dialog variant.

### 2. Information Hierarchy & Page Layout
- **Modal Backdrop**: Dimmed semi-transparent overlay (`bg-neutral-900/50`) with focus trap.
- **Dialog Header**: Semantic title ("Resolve Work Order", "Reject Facility Ticket", "Reopen Ticket") with close button (`X`).
- **Context Banner**: Brief recap of ticket reference code (`CFX-2026-00042`) and issue title.
- **Input Area**: Textarea with minimum character count indicator (min 10 characters required).
- **Target Status Selector (Reopen Dialog only)**: Radio selection between `ASSIGNED` (active queue) and `SUBMITTED` (triage pool).
- **Dialog Footer**: Secondary "Cancel / Dismiss" button and Primary Confirmation button ("Confirm Resolution", "Confirm Rejection", "Reopen Ticket").

### 3. ASCII Wireframes

#### Variant A: Staff Resolution Dialog (Desktop & Mobile)
```text
+--------------------------------------------------------------------+
|  Resolve Work Order: CFX-2026-00042                            [X] |
|--------------------------------------------------------------------|
|  Issue: Projector HDMI Port Damaged (Science Block A, Rm 402)      |
|                                                                    |
|  Please document the corrective physical action taken. This will   |
|  be recorded in the permanent maintenance ledger and shown to the  |
|  reporting student.                                                |
|                                                                    |
|  Corrective Resolution Notes * (min 10 characters)                 |
|  +---------------------------------------------------------------+ |
|  | Replaced damaged HDMI faceplate with new Cat6-HDMI extender.  | |
|  | Tested with instructor laptop at 1080p 60Hz. Signal verified. | |
|  |                                                               | |
|  +---------------------------------------------------------------+ |
|  124 / 1000 characters                                             |
|                                                                    |
|--------------------------------------------------------------------|
|  [ Dismiss ]                           [ Confirm & Mark Resolved ] |
+--------------------------------------------------------------------+
```

#### Variant B: Administrator Reopening Dialog (Desktop & Mobile)
```text
+--------------------------------------------------------------------+
|  Reopen Ticket: CFX-2026-00042                                 [X] |
|--------------------------------------------------------------------|
|  Warning: This ticket was marked RESOLVED on Oct 27. Reopening it  |
|  will return it to the active maintenance queue.                   |
|                                                                    |
|  Target Reopen Status *                                            |
|  (*) Return to ASSIGNED (Keep technician Alex Rivera)              |
|  ( ) Return to SUBMITTED (Send back to unassigned triage pool)     |
|                                                                    |
|  Mandatory Reopening Justification * (min 10 characters)           |
|  +---------------------------------------------------------------+ |
|  | Student reports video flickering resumed during afternoon lec.| |
|  | Technician needs to inspect ceiling cabling behind projector. | |
|  +---------------------------------------------------------------+ |
|  128 / 1000 characters                                             |
|                                                                    |
|--------------------------------------------------------------------|
|  [ Cancel ]                                    [ Confirm Reopen ]  |
+--------------------------------------------------------------------+
```

### 4. Components, Fields & Controls
- **Modal Shell**: Accessible dialog container with `aria-modal="true"`.
- **Textarea**: 4-row input with real-time character count. Min 10, max 1000 characters.
- **Radio Selector (Reopen)**: Target status choice (`ASSIGNED` vs `SUBMITTED`).
- **Submit Buttons**:
  - Resolve: `bg-emerald-600 text-white hover:bg-emerald-700`
  - Reject: `bg-red-600 text-white hover:bg-red-700`
  - Reopen: `bg-brand-600 text-white hover:bg-brand-700`

### 5. UI States
- **Initial Open**: Textarea empty, submit button disabled until 10 characters are entered.
- **Submitting**: Submit button displays loading spinner, textarea disabled.
- **Validation Error**: "Notes must contain at least 10 characters of detail."
- **Server Error (409 Conflict)**: Red error alert: "State conflict: this ticket has already been updated. Please refresh."

### 6. Validation & Business Rule Enforcement
- Strictly enforces `FR-015`: Rejection reason (min 10 chars), Resolution notes (min 10 chars), Reopening reason (min 10 chars).
- Sends `expected_version` to prevent overwriting concurrent state.

### 7. Accessibility (WCAG 2.1 AA)
- Focus is trapped within the dialog container using standard focus-trap.
- Pressing `Escape` triggers dialog close without submitting.
- Initial focus placed directly into the textarea upon modal mount.
- On close, focus returns to the button that triggered the dialog.

### 8. Responsive Behavior
- **Desktop (1280px)**: Modal width 560px centered vertically and horizontally.
- **Tablet (768px)**: Modal width 500px.
- **Mobile (375px)**: Bottom-sheet style modal or full-screen overlay with sticky confirmation buttons at bottom.

### 9. API Integrations
- `POST /api/v1/tickets/{id}/transition`
  - Resolve payload: `{target_status: "RESOLVED", notes: "...", expected_version: N}`
  - Reject payload: `{target_status: "REJECTED", notes: "...", expected_version: N}`
  - Reopen payload: `{target_status: "ASSIGNED", notes: "...", expected_version: N}`

### 10. Testable Acceptance Criteria
- **AC-06.1**: Submit button is strictly disabled when notes input length < 10 characters.
- **AC-06.2**: Confirming resolution closes the modal, triggers success toast, and transitions ticket state on `SCR-04`.
- **AC-06.3**: Pressing `Escape` key dismisses modal without triggering API requests.

---

```text
====================================================================================================
SCR-07: ADMIN OPERATIONS DASHBOARD
====================================================================================================
```

### 1. Purpose & Authorized Roles
- **Purpose**: Executive campus oversight dashboard providing operations administrators with real-time ticket metrics, status distributions, priority breakdowns, average resolution turnaround times, and immediate access to unassigned or critical tickets.
- **Authorized Roles**: `ADMINISTRATOR` only.

### 2. Information Hierarchy & Page Layout
- **Topbar**: Logo, Brand, Admin Navigation links ("Dashboard", "Dispatch", "Categories", "Users"), and Profile menu.
- **Header Section**: "Campus Operations Overview", Date Filter picker (Today, 7 Days, 30 Days, All Time), and "Refresh Metrics" button.
- **KPI Stat Cards (Row 1)**:
  - Total Active Issues (`SUBMITTED` + `ASSIGNED` + `IN_PROGRESS`).
  - Unassigned / Triage Pending (`SUBMITTED`).
  - Resolved Issues (Total resolved with percentage).
  - Average Resolution Turnaround (Hours, e.g. "18.4 hrs").
- **Visual Analytics Section (Row 2)**:
  - Status Distribution Bar / Grid (breakdown across all 6 lifecycle states).
  - Priority Breakdown Bar (Critical, High, Medium, Low).
- **Actionable Dispatch Table (Row 3)**:
  - High-priority & unassigned tickets needing immediate triage.

### 3. ASCII Wireframes

#### Desktop Viewport (1280px)
```text
+--------------------------------------------------------------------------------------------------+
| CampusFix  [ Dashboard ]  [ Categories ]  [ User Directory ]           [ Marcus Vance (Admin) v ]|
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  Campus Operations Overview                                        Date: [ Last 30 Days v ] [R]  |
|                                                                                                  |
|  +--------------------------------------------------------------------------------------------+  |
|  | ACTIVE TICKETS     | UNASSIGNED TRIAGE  | RESOLVED (30D)     | AVG TURNAROUND TIME         |  |
|  | 54                 | 14                 | 68 (53%)           | 18.4 Hours                  |  |
|  | +6% from last week | Needs attention!   | Goal: >50%         | Target: < 24 hrs            |  |
|  +--------------------------------------------------------------------------------------------+  |
|                                                                                                  |
|  +--------------------------------------------+ +---------------------------------------------+  |
|  | TICKETS BY STATUS                          | | TICKETS BY PRIORITY                         |  |
|  | Submitted:    [====       ] 14 (11%)       | | Critical: [==         ] 5 (4%)              |  |
|  | Assigned:     [======     ] 22 (17%)       | | High:     [========   ] 32 (25%)            |  |
|  | In Progress:  [=====      ] 18 (14%)       | | Medium:   [================] 65 (51%)       |  |
|  | Resolved:     [=================] 68 (53%) | | Low:      [======     ] 26 (20%)            |  |
|  | Rejected:     [=          ] 4 (3%)         | |                                             |  |
|  | Cancelled:    [=          ] 2 (2%)         | |                                             |  |
|  +--------------------------------------------+ +---------------------------------------------+  |
|                                                                                                  |
|  CRITICAL & UNASSIGNED TICKETS REQUIRING DISPATCH                     [ View All Work Orders > ] |
|  +--------------------------------------------------------------------------------------------+  |
|  | CODE           | LOCATION             | PRIORITY | STATUS    | CREATED   | QUICK ASSIGN     |  |
|  |----------------|----------------------|----------|-----------|-----------|------------------|  |
|  | CFX-2026-00038 | Hostel 3, Restroom   | CRITICAL | SUBMITTED | 4h ago    | [ Assign Staff v]|  |
|  | CFX-2026-00041 | Library, 1st Floor   | HIGH     | SUBMITTED | 6h ago    | [ Assign Staff v]|  |
|  +--------------------------------------------------------------------------------------------+  |
+--------------------------------------------------------------------------------------------------+
```

#### Mobile Viewport (375px)
```text
+-----------------------------------+
| = CampusFix Admin Dashboard       |
+-----------------------------------+
| Operations Overview               |
|                                   |
| [ ACTIVE: 54 ]  [ UNASSIGNED: 14 ]|
| [ RESOLVED: 68] [ AVG: 18.4 hrs ] |
|-----------------------------------|
| STATUS BREAKDOWN                  |
| - Submitted:   14                 |
| - Assigned:    22                 |
| - In Progress: 18                 |
| - Resolved:    68                 |
| - Rejected:    4                  |
| - Cancelled:   2                  |
|-----------------------------------|
| PRIORITY BREAKDOWN                |
| - Critical: 5  - High: 32         |
| - Medium: 65   - Low:  26         |
|-----------------------------------|
| NEEDS DISPATCH (2)                |
| [CFX-2026-00038]         CRITICAL |
| Hostel 3, Restroom - 4h ago       |
| [ Assign Work Order >           ] |
+-----------------------------------+
```

### 4. Components, Fields & Controls
- **Stat Metric Cards**: Elevated cards (`p-4 bg-white rounded-lg border border-neutral-200`) showing primary value, label, and secondary benchmark pill.
- **Distribution Progress Bars**: Semantic horizontal percentage bars using designated status/priority tokens.
- **Inline Dispatch Dropdown**: Direct technician picker for `SUBMITTED` tickets allowing 1-click assignment.

### 5. UI States
- **Loading State**: Shimmering card grid skeletons and bar chart placeholders.
- **Empty State**: "No tickets recorded for this time range."
- **Server Error State**: "Unable to load dashboard telemetry. Backend services may be temporarily unavailable." + Retry button.

### 6. Validation & Data Rules
- Directly consumes metrics schema from `GET /api/v1/admin/dashboard/metrics`.

### 7. Accessibility (WCAG 2.1 AA)
- Visual percentage bars are supplemented with clear numerical text representations.
- Data tables use semantic `<th>` and `<td>` tags with accessible column header scopes.

### 8. Responsive Behavior
- **Desktop (1280px)**: 4-card metric row, 2-column distribution layout, wide dispatch table.
- **Tablet (768px)**: 2x2 metric card grid, stacked distribution charts.
- **Mobile (375px)**: Single-column vertical scroll with condensed metric tiles.

### 9. API Integrations
- `GET /api/v1/admin/dashboard/metrics`
- `GET /api/v1/tickets?status=SUBMITTED&page_size=5`
- `POST /api/v1/tickets/{id}/assign`

### 10. Testable Acceptance Criteria
- **AC-07.1**: Dashboard metrics match the counts returned by `/admin/dashboard/metrics`.
- **AC-07.2**: Assigning a technician from the dispatch table updates the ticket status and removes it from the unassigned list.
- **AC-07.3**: Accessing this screen with a `STUDENT` or `STAFF` token redirects to a 403 Forbidden view.

---

```text
====================================================================================================
SCR-08: CATEGORY MANAGEMENT CONSOLE
====================================================================================================
```

### 1. Purpose & Authorized Roles
- **Purpose**: Administrative console to view, create, edit, and toggle active/inactive statuses of campus facility categories.
- **Authorized Roles**: `ADMINISTRATOR` only.

### 2. Information Hierarchy & Page Layout
- **Topbar**: Standard Administrator navigation header.
- **Header**: "Facility Categories" title, descriptive subtitle, and "+ New Category" primary button.
- **Main Area**: Data table displaying all categories:
  - Category Name
  - Description
  - Active Status Toggle Badge
  - Creation Date
  - Actions ("Edit", "Toggle Active / Deactivate")
- **Category Creation / Edit Modal**: Form to add or update category name and description.

### 3. ASCII Wireframes

#### Desktop Viewport (1280px)
```text
+--------------------------------------------------------------------------------------------------+
| CampusFix  [ Dashboard ]  [ Categories (Active) ]  [ User Directory ]  [ Marcus Vance (Admin) v ]|
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  Facility Issue Categories                                               [ + Add New Category ]  |
|  Configure the incident taxonomy available to students during ticket filing.                     |
|                                                                                                  |
|  +--------------------------------------------------------------------------------------------+  |
|  | CATEGORY NAME            | DESCRIPTION                           | STATUS   | ACTIONS      |  |
|  |--------------------------|---------------------------------------|----------|--------------|  |
|  | Classroom Audio-Visual   | Projectors, microphones, smartboards. | ACTIVE   | [Edit] [Deact|  |
|  | Electrical & Lighting    | Outlets, circuit breakers, fixtures.  | ACTIVE   | [Edit] [Deact|  |
|  | Plumbing & Sanitary      | Leaks, pipe blockages, restroom sinks.| ACTIVE   | [Edit] [Deact|  |
|  | Furniture & Fixtures     | Chairs, desks, whiteboards, doors.    | ACTIVE   | [Edit] [Deact|  |
|  | HVAC & Climate Control   | AC units, heaters, ventilation fans.  | ACTIVE   | [Edit] [Deact|  |
|  | Laboratory Equipment     | Special gas fixtures, chemical hoods. | INACTIVE | [Edit] [Activ|  |
|  +--------------------------------------------------------------------------------------------+  |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

#### Category Modal Wireframe (Add / Edit)
```text
+--------------------------------------------------------------------+
|  Add New Facility Category                                     [X] |
|--------------------------------------------------------------------|
|  Category Name *                                                   |
|  [ Classroom Audio-Visual                                        ] |
|                                                                    |
|  Description *                                                     |
|  +---------------------------------------------------------------+ |
|  | Projectors, microphones, sound systems, and HDMI wall inputs. | |
|  +---------------------------------------------------------------+ |
|                                                                    |
|  [X] Category is active and available for student filing           |
|--------------------------------------------------------------------|
|  [ Cancel ]                                  [ Save Category ]     |
+--------------------------------------------------------------------+
```

### 4. Components, Fields & Controls
- **Category Table**: Name, Description, Status Pill (`ACTIVE` in green, `INACTIVE` in gray), Actions.
- **Status Toggle Switch**: Accessible toggle button switching active status.
- **Add / Edit Modal**:
  - `name`: Text input, min 2, max 100 chars.
  - `description`: Textarea, min 5, max 500 chars.
  - `is_active`: Checkbox toggle.

### 5. UI States
- **Loading State**: Table skeleton shimmer.
- **Deactivating Confirmation State**: Warning alert explaining that existing tickets retain the category, but new submissions will not see it.
- **Success State**: Toast notification: "Category 'HVAC' successfully updated."

### 6. Validation & Business Rule Enforcement
- Category names must be unique. If the backend returns HTTP 409 or 422 for duplicate names, the modal displays an inline error: "A category with this name already exists."
- Hard deletion is blocked per `FR-025`; only deactivation is supported.

### 7. Accessibility (WCAG 2.1 AA)
- Action buttons have explicit labels (`aria-label="Edit Classroom Audio-Visual category"`).
- Status toggle uses `role="switch"` with `aria-checked="true/false"`.

### 8. Responsive Behavior
- **Desktop (1280px)**: Full table layout with inline action links.
- **Mobile (375px)**: Stacked category cards showing Name, Status, and Action buttons.

### 9. API Integrations
- `GET /api/v1/categories`
- `POST /api/v1/categories` (Body: `{name, description}`)
- `PATCH /api/v1/categories/{id}` (Body: `{name, description, is_active}`)

### 10. Testable Acceptance Criteria
- **AC-08.1**: Creating a new category adds it to the list and makes it available on `SCR-03`.
- **AC-08.2**: Deactivating a category sets `is_active = false` and changes the status pill to `INACTIVE`.
- **AC-08.3**: Attempting to submit empty name or description displays validation error.

---

```text
====================================================================================================
SCR-09: USER DIRECTORY & ROLE MANAGER
====================================================================================================
```

### 1. Purpose & Authorized Roles
- **Purpose**: Administrative user management directory to inspect registered campus accounts, filter by role, adjust user access levels (`STUDENT`, `STAFF`, `ADMINISTRATOR`), and toggle account active status.
- **Authorized Roles**: `ADMINISTRATOR` only.

### 2. Information Hierarchy & Page Layout
- **Topbar**: Standard Administrator navigation header.
- **Header**: "Campus User Directory", User count ("Showing 128 registered users"), and Role filter tabs.
- **Filter Bar**:
  - Search input (searches by full name or email address).
  - Role filter dropdown (`ALL`, `STUDENT`, `STAFF`, `ADMINISTRATOR`).
  - Active status filter (`ALL`, `ACTIVE`, `INACTIVE`).
- **User Data Table**:
  - User Name & Email
  - Assigned Role Badge
  - Account Active Status
  - Registered Timestamp
  - Role Action Menu ("Change Role to Staff", "Change Role to Admin", "Deactivate Account")
- **Pagination Footer**: Page size selector and pagination controls.

### 3. ASCII Wireframes

#### Desktop Viewport (1280px)
```text
+--------------------------------------------------------------------------------------------------+
| CampusFix  [ Dashboard ]  [ Categories ]  [ User Directory (Active) ]  [ Marcus Vance (Admin) v ]|
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  Campus User Directory & Access Management                                                       |
|  Manage registered student, facilities staff, and administrator accounts.                        |
|                                                                                                  |
|  +--------------------------------------------------------------------------------------------+  |
|  | Search by name or email... [Q] | Filter Role: [ All Roles v ] | Status: [ Active Users v ] |  |
|  +--------------------------------------------------------------------------------------------+  |
|                                                                                                  |
|  +--------------------------------------------------------------------------------------------+  |
|  | USER & EMAIL              | ROLE          | STATUS   | REGISTERED   | MANAGE ACCESS        |  |
|  |---------------------------|---------------|----------|--------------|----------------------|  |
|  | Jane Doe                  | STUDENT       | ACTIVE   | Oct 20, 2026 | [ Modify Role v ]    |  |
|  | jane.doe@university.edu   | [Blue]        | [Green]  |              |                      |  |
|  |---------------------------|---------------|----------|--------------|----------------------|  |
|  | Alex Rivera               | STAFF         | ACTIVE   | Sep 15, 2026 | [ Modify Role v ]    |  |
|  | alex.rivera@university.edu| [Amber]       | [Green]  |              |                      |  |
|  |---------------------------|---------------|----------|--------------|----------------------|  |
|  | Marcus Vance              | ADMINISTRATOR | ACTIVE   | Aug 01, 2026 | (Current Account)    |  |
|  | marcus.vance@univ.edu     | [Purple]      | [Green]  |              |                      |  |
|  +--------------------------------------------------------------------------------------------+  |
|                                                                                                  |
|  Showing 1 - 3 of 128 users                             Page 1 of 43  [ < Prev ]  [ Next > ]     |
+--------------------------------------------------------------------------------------------------+
```

#### Role Modification Dialog
```text
+--------------------------------------------------------------------+
|  Modify User Role: Alex Rivera                                 [X] |
|--------------------------------------------------------------------|
|  Current Role: STAFF                                               |
|  Email: alex.rivera@university.edu                                 |
|                                                                    |
|  Select New Role *                                                 |
|  ( ) STUDENT — Can only report and view personal tickets           |
|  (*) STAFF — Can view work queue, claim, and resolve tickets       |
|  ( ) ADMINISTRATOR — Full campus oversight, dispatch, & categories |
|                                                                    |
|  Notice: Role changes take effect immediately upon next request.   |
|--------------------------------------------------------------------|
|  [ Cancel ]                                    [ Update Role ]     |
+--------------------------------------------------------------------+
```

### 4. Components, Fields & Controls
- **Search Bar**: Debounced text search filtering by full name or email.
- **User Table**: Columns: User details, Role pill, Status indicator, Registration date, Actions menu.
- **Role Selector Modal**: Radio cards detailing each role's permissions.
- **Self-Protection Safeguard**: The current administrator's own account has actions disabled ("Current Account") to prevent accidental self-lockout.

### 5. UI States
- **Loading State**: Multi-row table pulse skeleton.
- **Empty State**: "No users found matching your search criteria." + Reset filter button.
- **Updating State**: Role modification button displays spinner; row briefly flashes blue upon update confirmation.
- **Error State**: "Failed to update role. Please verify your administrative credentials."

### 6. Validation & Business Rule Enforcement
- Public self-registration only issues `STUDENT`. Upgrades to `STAFF` or `ADMINISTRATOR` strictly execute through this screen via `PATCH /admin/users/{id}/role`.
- Self-downgrading of the active logged-in administrator is prevented in the UI.

### 7. Accessibility (WCAG 2.1 AA)
- Role badges use distinct color combinations with high contrast.
- Role modify modal uses accessible radio group semantics with keyboard arrow navigation.

### 8. Responsive Behavior
- **Desktop (1280px)**: Multi-column table with full email and timestamp visibility.
- **Mobile (375px)**: Stacked user cards with role badge, email, and "Modify Access" action button.

### 9. API Integrations
- `GET /api/v1/admin/users?page=1&page_size=20&role=&is_active=`
- `PATCH /api/v1/admin/users/{id}/role` (Body: `{role: "STAFF"}`)

### 10. Testable Acceptance Criteria
- **AC-09.1**: Modifying a student's role to `STAFF` updates the table badge to `STAFF` and persists via API call.
- **AC-09.2**: Searching for "alex" filters the user list to matching accounts.
- **AC-09.3**: Current administrator's own row disables role modification controls.
