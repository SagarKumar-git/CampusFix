# UI/UX Specification & Design Architecture — CampusFix

| Document Version | 1.1.0 |
| :--- | :--- |
| **Status** | Phase 1 Complete (Design System & Wireframes Approved) |
| **Maintainer** | UI/UX Engineer & Frontend Lead |
| **Last Updated** | 2026-10-27 (UTC) |

---

## 1. Principles & Design Philosophy

The CampusFix user experience is designed for speed, operational density, and accessibility. Students reporting issues need an uncluttered, friction-free 60-second submission flow on mobile or desktop. Facilities technicians and administrators require a high-density, keyboard-friendly workbench that surfaces priorities, statuses, and locations at a glance.

### Core Tenets:
1. **Zero Decorative Deception**: Every button, pill, link, and control maps to a real, functional backend capability. No placeholder buttons that do nothing.
2. **Neutral Professional Aesthetics**: Modern, trustworthy corporate/institutional palette using neutral slates, indigo accents, and semantic status colors. Avoid fake university seals or unverifiable branding.
3. **Deterministic Feedback States**: Every asynchronous operation explicitly renders one of four distinct states:
   - **Loading**: Skeleton placeholders (avoiding jarring layout shifts).
   - **Empty**: Context-aware guidance with call-to-action (e.g., "No open tickets. Need to report an issue?").
   - **Error**: Actionable, human-readable error banners with retry options.
   - **Success**: Non-intrusive toast or banner confirmations with state updates.
4. **Strict Accessibility (WCAG 2.1 AA)**:
   - Minimum 4.5:1 text-to-background contrast ratio.
   - Visible focus rings (`focus-visible:ring-2 focus-visible:ring-offset-2`).
   - Screen-reader accessible forms (`aria-describedby` for error states, semantic `<form>`, `<label>`, `<fieldset>`).

---

## 2. Design Tokens System (Tailwind Mappings)

### 2.1 Semantic Color Palette
```javascript
// tailwind.config.js token mappings
colors: {
  brand: {
    50: '#eef2ff',
    100: '#e0e7ff',
    500: '#6366f1',
    600: '#4f46e5', // Primary brand action
    700: '#4338ca',
  },
  neutral: {
    50: '#f8fafc',  // Canvas background
    100: '#f1f5f9', // Card headers / borders
    200: '#e2e8f0', // Inactive borders
    600: '#475569', // Secondary text
    900: '#0f172a', // Primary high-contrast text
  },
  status: {
    submitted: { bg: '#eff6ff', text: '#1d4ed8', border: '#bfdbfe' },   // Blue
    assigned: { bg: '#fef3c7', text: '#b45309', border: '#fde68a' },    // Amber
    in_progress: { bg: '#f3e8ff', text: '#7e22ce', border: '#e9d5ff' }, // Purple
    resolved: { bg: '#ecfdf5', text: '#047857', border: '#a7f3d0' },    // Emerald Green
    rejected: { bg: '#fef2f2', text: '#b91c1c', border: '#fecaca' },    // Rose Red
    cancelled: { bg: '#f1f5f9', text: '#475569', border: '#cbd5e1' },   // Slate Muted
  },
  priority: {
    low: { bg: '#f1f5f9', text: '#334155' },
    medium: { bg: '#e0f2fe', text: '#0369a1' },
    high: { bg: '#ffedd5', text: '#c2410c' },
    critical: { bg: '#fee2e2', text: '#991b1b' },
  }
}
```

### 2.2 Typography Scale
- Primary Font: Inter, system-ui, sans-serif
- Monospace (Codes & IDs): JetBrains Mono, Menlo, monospace (`CFX-2026-00042`)
- Headings: `text-2xl font-bold tracking-tight` (Page Titles), `text-lg font-semibold` (Card Headers)
- Body: `text-sm font-normal text-neutral-600`
- Meta & Badges: `text-xs font-medium`

---

## 3. Screen Inventory

| Screen ID | Name | Role Access | Primary Purpose |
| :--- | :--- | :--- | :--- |
| **SCR-01** | **Authentication Portal** | Public | Login (email/password) & Student self-registration toggle. |
| **SCR-02** | **Student Portal / My Tickets** | `STUDENT` | Overview of student's filed issues, status badges, and quick CTA to report new issue. |
| **SCR-03** | **Ticket Submission Flow** | `STUDENT`, `ADMIN` | Clean single-page or stepped form for issue reporting with category, location, and priority selection. |
| **SCR-04** | **Ticket Detail & Timeline** | All (Role-gated) | Full incident details, current state banner, assigned staff, and chronological audit timeline. |
| **SCR-05** | **Staff Workbench Queue** | `STAFF` | Dual tabs: "Assigned to Me" and "Unassigned Queue" with quick-claim actions and priority sorting. |
| **SCR-06** | **Resolution & Note Dialogs** | `STAFF`, `ADMIN` | Modals for required notes: Resolution summary, Rejection reason, and Student cancellation confirmation. |
| **SCR-07** | **Admin Operations Dashboard** | `ADMINISTRATOR` | Key performance metrics (active vs. resolved), category breakdown, high-incident location heatmaps. |
| **SCR-08** | **Category Management Console** | `ADMINISTRATOR` | Table of facility categories with add, edit, and toggle active/inactive status. |
| **SCR-09** | **User Directory & Role Manager** | `ADMINISTRATOR` | Directory of registered campus accounts with role modification capabilities. |

---

## 4. Interaction Patterns & Error Presentation

1. **Form Validation Feedback**:
   - Inline validation triggers on `onBlur` and `onSubmit`.
   - Clear visual red border and descriptive helper text directly under the affected field.
   - Global form error alert positioned at the top of the modal/form if an API rejection occurs.
2. **Action Confirmation Modals**:
   - Destructive or permanent state transitions (`CANCELLED`, `REJECTED`, `RESOLVED`) require explicit confirmation dialogs with required textarea fields.
3. **Empty States**:
   - Render friendly, actionable SVGs with clear explanations (e.g., "You haven't reported any issues yet. If something on campus is broken, click 'Report New Issue'.").

---

## 5. Phase 1 Deliverables Index

Phase 1 design specifications have been fully authored and approved:
- [**`docs/DESIGN_SYSTEM.md`**](file:///c:/Sagar%20Project/CampusFix/docs/DESIGN_SYSTEM.md): Complete tokenized color palettes, WCAG 2.1 AA contrast matrix, typography scales, 4px spatial rhythm, component blueprints (buttons, inputs, selects, dialogs, tables, pagination), and role-specific navigation shells.
- [**`docs/PHASE_1_WIREFRAMES.md`**](file:///c:/Sagar%20Project/CampusFix/docs/PHASE_1_WIREFRAMES.md): Exhaustive specifications and dual desktop/mobile ASCII wireframes for all nine screens (`SCR-01` through `SCR-09`) with deterministic state models (loading, empty, error, success), validation, and keyboard interaction.
- [**`docs/USER_FLOWS.md`**](file:///c:/Sagar%20Project/CampusFix/docs/USER_FLOWS.md): End-to-end user journeys for Student submission & tracking, Staff work execution & resolution, Admin dispatch & reopening, and silent token rotation & logout.
- [**`docs/PHASE_1_ACCEPTANCE.md`**](file:///c:/Sagar%20Project/CampusFix/docs/PHASE_1_ACCEPTANCE.md): Testable verification criteria and accessibility checklist for all nine screens.

