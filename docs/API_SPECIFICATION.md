# API Specification — CampusFix RESTful Services

| Document Version | 1.0.0 |
| :--- | :--- |
| **Status** | Approved Baseline (Phase 0) |
| **Maintainer** | Backend Lead & API Architect |
| **Last Updated** | 2026-10-27 (UTC) |

---

## 1. RESTful Conventions & Standards

All CampusFix APIs follow strict RESTful conventions:
- **Base URI**: `/api/v1`
- **Transport**: HTTPS with TLS 1.3
- **Data Exchange**: Content-Type `application/json; charset=utf-8`
- **Authentication**: Bearer Token in `Authorization: Bearer <access_token>` header
- **Standard HTTP Verbs**: `GET` (idempotent read), `POST` (resource creation / state transition), `PATCH` (partial resource update), `DELETE` (resource removal / soft deletion)
- **Pagination**: Query parameters `page` (default 1) and `page_size` (default 20, max 100). Response includes `meta: { total, page, page_size, total_pages }`.

---

## 2. Standard Envelope Formats

### 2.1 Success Envelope
```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 45,
    "total_pages": 3
  }
}
```

### 2.2 Error Envelope
```json
{
  "success": false,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Ticket with ID '550e8400-e29b-41d4-a716-446655440000' does not exist.",
    "details": null
  },
  "timestamp": "2026-10-27T13:45:00Z"
}
```

---

## 3. Endpoints Matrix

### 3.1 Authentication & Profile (`/api/v1/auth`)

| Method | Endpoint | Access Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/register` | Public | Register new Student account. |
| `POST` | `/auth/login` | Public | Authenticate; returns access JWT and sets `HttpOnly` refresh cookie. |
| `POST` | `/auth/refresh` | Public (Cookie) | Issues fresh access JWT using valid refresh cookie. |
| `POST` | `/auth/logout` | Authenticated | Clears refresh cookie and terminates active session. |
| `GET` | `/auth/me` | Authenticated | Returns identity and role profile of current user. |

#### `POST /auth/register`
- **Request Body**:
  ```json
  {
    "full_name": "Jane Doe",
    "email": "jane.doe@university.edu",
    "password": "SecurePassword123!"
  }
  ```
- **Response (HTTP 201 Created)**:
  ```json
  {
    "success": true,
    "data": {
      "id": "c1f7a43e-7c98-4c8d-8a2b-3e5f1b2c3d4e",
      "email": "jane.doe@university.edu",
      "full_name": "Jane Doe",
      "role": "STUDENT"
    }
  }
  ```

#### `POST /auth/login`
- **Request Body**:
  ```json
  {
    "email": "jane.doe@university.edu",
    "password": "SecurePassword123!"
  }
  ```
- **Response (HTTP 200 OK)**:
  - Header: `Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth; Max-Age=604800`
  ```json
  {
    "success": true,
    "data": {
      "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
      "token_type": "bearer",
      "expires_in": 900,
      "user": {
        "id": "c1f7a43e-7c98-4c8d-8a2b-3e5f1b2c3d4e",
        "email": "jane.doe@university.edu",
        "full_name": "Jane Doe",
        "role": "STUDENT"
      }
    }
  }
  ```

#### `POST /auth/refresh`
- **Request**:
  - Cookie: `refresh_token=<token_string>`
  - Headers: `Origin` or `Referer` matching allowlisted frontend origin.
- **Concurrency & Transaction Guarantee**:
  - Processed inside an atomic database transaction acquiring a row lock (`SELECT ... FOR UPDATE`) on the matching SHA-256 token hash.
  - Two concurrent requests presenting the same refresh token cannot both succeed. The first request consumes the token and issues a replacement. The second request blocks on the lock, reads `revoked_at IS NOT NULL`, detects token reuse, invalidates the entire token family, and is rejected with HTTP 401.
- **Response (HTTP 200 OK - Valid Rotation)**:
  - Header: `Set-Cookie: refresh_token=<new_token>; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth; Max-Age=604800` (New token inheriting the same `family_id`)
  ```json
  {
    "success": true,
    "data": {
      "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
      "token_type": "bearer",
      "expires_in": 900
    }
  }
  ```
- **Response (HTTP 401 Unauthorized - Reused / Revoked Token)**:
  - Header: `Set-Cookie: refresh_token=; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth; Max-Age=0` (Cookie cleared)
  ```json
  {
    "success": false,
    "error": {
      "code": "TOKEN_REUSE_DETECTED",
      "message": "Refresh token has already been consumed. Active session family revoked.",
      "details": null
    },
    "timestamp": "2026-10-27T15:20:00Z"
  }
  ```
- **Response (HTTP 401 Unauthorized - Expired or Invalid Token)**:
  - Returns `TOKEN_EXPIRED` or `INVALID_TOKEN` and clears the refresh cookie.

#### `POST /auth/logout`
- **Request**: Sent with `refresh_token` in cookie and `Authorization: Bearer <access_token>`.
- **Response (HTTP 200 OK)**:
  - Header: `Set-Cookie: refresh_token=; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth; Max-Age=0` (Cookie cleared)
  ```json
  {
    "success": true,
    "data": {
      "message": "Successfully logged out."
    }
  }
  ```

#### `GET /auth/me`
- **Headers**: `Authorization: Bearer <access_token>`
- **Response (HTTP 200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "id": "c1f7a43e-7c98-4c8d-8a2b-3e5f1b2c3d4e",
      "email": "jane.doe@university.edu",
      "full_name": "Jane Doe",
      "role": "STUDENT",
      "is_active": true,
      "created_at": "2026-10-27T12:00:00Z"
    }
  }
  ```

---

### 3.2 Categories (`/api/v1/categories`)

| Method | Endpoint | Access Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/categories` | Authenticated | List all active issue categories for ticket filing. |
| `POST` | `/categories` | `ADMINISTRATOR` | Create a new issue category. |
| `PATCH` | `/categories/{id}` | `ADMINISTRATOR` | Update or deactivate an existing category. |

#### `GET /categories` Response (HTTP 200 OK):
```json
{
  "success": true,
  "data": [
    {
      "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "name": "Classroom Audio-Visual",
      "description": "Projectors, microphones, smartboards, audio systems.",
      "is_active": true
    },
    {
      "id": "3f2e1d0c-4b5a-6a7b-8c9d-0e1f2a3b4c5d",
      "name": "Electrical & Lighting",
      "description": "Power outlets, flickering lights, circuit breaker trips.",
      "is_active": true
    }
  ]
}
```

---

### 3.3 Tickets Management (`/api/v1/tickets`)

| Method | Endpoint | Access Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/tickets` | `STUDENT`, `ADMIN` | File a new facility issue ticket. |
| `GET` | `/tickets` | Authenticated | List tickets with filters. Role-gated: Students see only own tickets. |
| `GET` | `/tickets/{id}` | Authenticated | View details of a specific ticket. Resource-gated for Students. |
| `POST` | `/tickets/{id}/assign` | `STAFF`, `ADMIN` | Assign or self-claim a ticket. |
| `POST` | `/tickets/{id}/transition` | Role-gated | Transition status (e.g., to IN_PROGRESS, RESOLVED, REJECTED, CANCELLED). |
| `GET` | `/tickets/{id}/history` | Authenticated | View chronological audit history for a ticket. |

#### `POST /tickets`
- **Request Body**:
  ```json
  {
    "title": "Projector HDMI Port Damaged in Room 402",
    "description": "The HDMI wall input is bent and will not establish connection with laptops during morning lectures.",
    "category_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "location": "Science Block A, Lecture Room 402",
    "priority": "HIGH"
  }
  ```
- **Response (HTTP 201 Created)**:
  ```json
  {
    "success": true,
    "data": {
      "id": "7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d",
      "ticket_number": "CFX-2026-00042",
      "title": "Projector HDMI Port Damaged in Room 402",
      "description": "The HDMI wall input is bent and will not establish connection with laptops during morning lectures.",
      "category_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "location": "Science Block A, Lecture Room 402",
      "priority": "HIGH",
      "status": "SUBMITTED",
      "creator_id": "c1f7a43e-7c98-4c8d-8a2b-3e5f1b2c3d4e",
      "assigned_staff_id": null,
      "version": 1,
      "created_at": "2026-10-27T13:40:00Z",
      "updated_at": "2026-10-27T13:40:00Z"
    }
  }
  ```

#### `GET /tickets`
- **Access Role**: Authenticated (Role-Gated & Resource-Filtered)
- **Query Parameters**:
  - `page` (integer, default 1, min 1): 1-based page index.
  - `page_size` (integer, default 20, min 1, max 100): Page item limit.
  - `status` (string, optional): Filter by ticket status. Supports single status (e.g. `status=SUBMITTED`) or multiple statuses using comma-separated values (e.g. `status=ASSIGNED,IN_PROGRESS`). Valid values: `SUBMITTED`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `REJECTED`, `CANCELLED`.
  - `assigned_staff_id` (string, optional): Filter by staff assignee. Accepts:
    - Literal `"me"`: Resolves to the authenticated user's ID (strictly available for `STAFF` and `ADMINISTRATOR` roles; enables technicians to query their own queue).
    - Valid UUID string: Filters tickets assigned to a specific technician ID (available for `ADMINISTRATOR` and `STAFF`).
  - `category_id` (UUID, optional): Filter by specific facility issue category.
  - `priority` (string enum, optional): Filter by priority (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- **Validation Rules & Error Handling**:
  - Invalid UUID format in `category_id` or `assigned_staff_id`: returns HTTP 422 Unprocessable Entity.
  - Invalid status tokens in comma-separated `status` string: returns HTTP 422 Unprocessable Entity.
  - Out-of-bounds `page < 1` or `page_size < 1` or `page_size > 100`: returns HTTP 422 Unprocessable Entity.
  - Attempting to pass `assigned_staff_id=me` without an active authenticated session returns HTTP 401 Unauthorized.
- **Server Enforcement & Ownership Restrictions**:
  - **`STUDENT`**: The server unconditionally enforces `WHERE creator_id = current_user.id` at the database query level (strict IDOR defense). If a student supplies `assigned_staff_id`, the parameter is ignored by the query planner, guaranteeing that students can never view tickets filed by other users.
  - **`STAFF`**: Can filter their own assigned queue (`assigned_staff_id=me`), unassigned incoming triage pool (`status=SUBMITTED`), or broader operational tickets matching category/priority filters.
  - **`ADMINISTRATOR`**: Full global visibility across all tickets with arbitrary combinations of status, staff assignee, category, and priority filters.
- **Pagination Interactions**:
  - Filtering directly scopes the matched record set, dynamically updating `meta.total` and recalculating `meta.total_pages = ceil(total / page_size)`.
- **Response (HTTP 200 OK)**:
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d",
        "ticket_number": "CFX-2026-00042",
        "title": "Projector HDMI Port Damaged in Room 402",
        "category_name": "Classroom Audio-Visual",
        "location": "Science Block A, Lecture Room 402",
        "priority": "HIGH",
        "status": "SUBMITTED",
        "creator_name": "Jane Doe",
        "assigned_staff_name": null,
        "created_at": "2026-10-27T13:40:00Z"
      }
    ],
    "meta": {
      "page": 1,
      "page_size": 20,
      "total": 1,
      "total_pages": 1
    }
  }
  ```

#### `GET /tickets/{id}`
- **Headers**: `Authorization: Bearer <access_token>`
- **Response (HTTP 200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "id": "7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d",
      "ticket_number": "CFX-2026-00042",
      "title": "Projector HDMI Port Damaged in Room 402",
      "description": "The HDMI wall input is bent and will not establish connection with laptops during morning lectures.",
      "category": {
        "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        "name": "Classroom Audio-Visual"
      },
      "location": "Science Block A, Lecture Room 402",
      "priority": "HIGH",
      "status": "SUBMITTED",
      "creator": {
        "id": "c1f7a43e-7c98-4c8d-8a2b-3e5f1b2c3d4e",
        "full_name": "Jane Doe"
      },
      "assigned_staff": null,
      "resolution_notes": null,
      "rejection_reason": null,
      "version": 1,
      "created_at": "2026-10-27T13:40:00Z",
      "updated_at": "2026-10-27T13:40:00Z"
    }
  }
  ```

#### `POST /tickets/{id}/assign`
- **Request Body**:
  ```json
  {
    "staff_id": "e2a1b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c",
    "expected_version": 1
  }
  ```
- **Response (HTTP 200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "id": "7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d",
      "ticket_number": "CFX-2026-00042",
      "status": "ASSIGNED",
      "assigned_staff_id": "e2a1b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c",
      "version": 2,
      "updated_at": "2026-10-27T13:50:00Z"
    }
  }
  ```

#### `POST /tickets/{id}/transition`
- **Request Body (Resolution Example)**:
  ```json
  {
    "target_status": "RESOLVED",
    "notes": "Replaced the damaged HDMI faceplate and tested video feed with standard 1080p output. Fully functional.",
    "expected_version": 2
  }
  ```
- **Request Body (Reopening by Administrator Example)**:
  ```json
  {
    "target_status": "ASSIGNED",
    "notes": "Lecturer reported projector video flickering again during afternoon session. Reopening for secondary diagnostic.",
    "expected_version": 3
  }
  ```
- **Response (HTTP 200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "id": "7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d",
      "ticket_number": "CFX-2026-00042",
      "status": "RESOLVED",
      "resolution_notes": "Replaced the damaged HDMI faceplate and tested video feed with standard 1080p output. Fully functional.",
      "version": 3,
      "updated_at": "2026-10-27T14:15:00Z"
    }
  }
  ```

#### `GET /tickets/{id}/history`
- **Headers**: `Authorization: Bearer <access_token>`
- **Response (HTTP 200 OK)**:
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e",
        "ticket_id": "7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d",
        "from_status": null,
        "to_status": "SUBMITTED",
        "changed_by": {
          "id": "c1f7a43e-7c98-4c8d-8a2b-3e5f1b2c3d4e",
          "full_name": "Jane Doe"
        },
        "assigned_to": null,
        "notes": "Ticket submitted.",
        "created_at": "2026-10-27T13:40:00Z"
      },
      {
        "id": "9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f",
        "ticket_id": "7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d",
        "from_status": "SUBMITTED",
        "to_status": "ASSIGNED",
        "changed_by": {
          "id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
          "full_name": "Admin User"
        },
        "assigned_to": {
          "id": "e2a1b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c",
          "full_name": "Tech Specialist"
        },
        "notes": "Assigned to AV technician.",
        "created_at": "2026-10-27T13:50:00Z"
      }
    ]
  }
  ```

---

### 3.4 Administrative Operations (`/api/v1/admin`)

| Method | Endpoint | Access Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/admin/users` | `ADMINISTRATOR` | List users with pagination and role filters. |
| `PATCH` | `/admin/users/{id}/role` | `ADMINISTRATOR` | Upgrade/downgrade a user's role. |
| `GET` | `/admin/dashboard/metrics` | `ADMINISTRATOR` | Retrieve operational metrics (counts by status, resolution times). |

#### `GET /admin/users`
- **Access Role**: `ADMINISTRATOR` strictly (Requests by `STUDENT` or `STAFF` return HTTP 403 Forbidden).
- **Headers**: `Authorization: Bearer <access_token>`
- **Query Parameters**:
  - `page` (integer, default 1, min 1): 1-based page index.
  - `page_size` (integer, default 20, min 1, max 100): Page item limit.
  - `search` (string, optional): Case-insensitive substring match against `full_name` or `email`. Leading and trailing whitespace is stripped.
  - `role` (string enum, optional): Filter by user role (`STUDENT`, `STAFF`, `ADMINISTRATOR`).
  - `is_active` (boolean, optional): Filter by user account active status (`true`, `false`).
- **Validation Rules & Error Handling**:
  - Invalid role enum string: returns HTTP 422 Unprocessable Entity (`VALIDATION_ERROR`).
  - Invalid boolean representation for `is_active`: returns HTTP 422 Unprocessable Entity.
  - Out-of-bounds `page < 1` or `page_size < 1` or `page_size > 100`: returns HTTP 422 Unprocessable Entity.
- **Authorization & Security**:
  - Non-administrators (`STUDENT`, `STAFF`) are blocked at the router dependency level, returning HTTP 403 Forbidden (`INSUFFICIENT_PERMISSIONS`).
  - Unauthenticated requests return HTTP 401 Unauthorized.
- **Response (HTTP 200 OK)**:
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "c1f7a43e-7c98-4c8d-8a2b-3e5f1b2c3d4e",
        "email": "jane.doe@university.edu",
        "full_name": "Jane Doe",
        "role": "STUDENT",
        "is_active": true,
        "created_at": "2026-10-27T12:00:00Z"
      },
      {
        "id": "e2a1b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c",
        "email": "alex.rivera@university.edu",
        "full_name": "Alex Rivera",
        "role": "STAFF",
        "is_active": true,
        "created_at": "2026-09-15T09:30:00Z"
      }
    ],
    "meta": {
      "page": 1,
      "page_size": 20,
      "total": 128,
      "total_pages": 7
    }
  }
  ```

#### `PATCH /admin/users/{id}/role`
- **Request Body**:
  ```json
  {
    "role": "STAFF"
  }
  ```
- **Response (HTTP 200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "id": "e2a1b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c",
      "email": "staff.member@university.edu",
      "full_name": "Staff Member",
      "role": "STAFF",
      "is_active": true
    }
  }
  ```

#### `GET /admin/dashboard/metrics` Response (HTTP 200 OK):
```json
{
  "success": true,
  "data": {
    "total_tickets": 128,
    "by_status": {
      "SUBMITTED": 14,
      "ASSIGNED": 22,
      "IN_PROGRESS": 18,
      "RESOLVED": 68,
      "REJECTED": 4,
      "CANCELLED": 2
    },
    "by_priority": {
      "CRITICAL": 5,
      "HIGH": 32,
      "MEDIUM": 65,
      "LOW": 26
    },
    "avg_resolution_hours": 18.4
  }
}
```
