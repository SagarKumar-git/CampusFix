/**
 * CampusFix TypeScript Domain & API Contracts
 *
 * Synchronized with backend Pydantic v2 schemas:
 * - app/schemas/user.py
 * - app/schemas/auth.py
 * - app/schemas/category.py
 * - app/schemas/ticket.py
 * - app/schemas/common.py
 * - app/schemas/error.py
 */

// ==============================================================================
// Enums & Literals
// ==============================================================================

export type UserRole = 'STUDENT' | 'STAFF' | 'ADMINISTRATOR';

export type TicketPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type TicketStatus =
  | 'SUBMITTED'
  | 'ASSIGNED'
  | 'IN_PROGRESS'
  | 'RESOLVED'
  | 'REJECTED'
  | 'CANCELLED';

// ==============================================================================
// User & Auth Schemas
// ==============================================================================

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface UserSummary {
  id: string;
  full_name: string;
}

export interface UserCreatePayload {
  full_name: string;
  email: string;
  password: string;
}

export interface UserLoginPayload {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginResponseData {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

// ==============================================================================
// Category Schemas
// ==============================================================================

export interface CategorySummary {
  id: string;
  name: string;
}

export interface Category {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CategoryCreatePayload {
  name: string;
  description: string;
  is_active?: boolean;
}

export interface CategoryUpdatePayload {
  name?: string;
  description?: string;
  is_active?: boolean;
}

// ==============================================================================
// Ticket Schemas
// ==============================================================================

export interface Ticket {
  id: string;
  ticket_number: string;
  title: string;
  description: string;
  category: CategorySummary;
  location: string;
  priority: TicketPriority;
  status: TicketStatus;
  creator: UserSummary;
  assigned_staff: UserSummary | null;
  resolution_notes: string | null;
  rejection_reason: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface TicketSummary {
  id: string;
  ticket_number: string;
  title: string;
  category_name: string;
  location: string;
  priority: TicketPriority;
  status: TicketStatus;
  creator_name: string;
  assigned_staff_name: string | null;
  created_at: string;
}

export interface TicketCreatePayload {
  title: string;
  description: string;
  category_id: string;
  location: string;
  priority?: TicketPriority;
}

export interface TicketAssignPayload {
  staff_id: string;
  expected_version: number;
}

export interface TicketAssignResponseData {
  id: string;
  ticket_number: string;
  status: TicketStatus;
  assigned_staff_id: string | null;
  version: number;
  updated_at: string;
}

export interface TicketTransitionPayload {
  target_status: TicketStatus;
  notes?: string | null;
  assigned_staff_id?: string | null;
  expected_version: number;
}

export interface TicketTransitionResponseData {
  id: string;
  ticket_number: string;
  status: TicketStatus;
  resolution_notes: string | null;
  rejection_reason: string | null;
  version: number;
  updated_at: string;
}

export interface TicketHistoryItem {
  id: string;
  ticket_id: string;
  from_status: string | null;
  to_status: string;
  changed_by: UserSummary;
  assigned_to: UserSummary | null;
  notes: string | null;
  created_at: string;
}

export interface TicketFilterQuery {
  page?: number;
  page_size?: number;
  status?: string;
  assigned_staff_id?: string;
  category_id?: string;
  priority?: TicketPriority;
}

// ==============================================================================
// Common Envelope & Error Schemas
// ==============================================================================

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface SuccessEnvelope<T> {
  success: true;
  data: T;
}

export interface PaginatedResponse<T> {
  success: true;
  data: T[];
  meta: PaginationMeta;
}

export interface ValidationErrorItem {
  field?: string | null;
  message: string;
  type?: string | null;
}

export interface ErrorDetail {
  code: string;
  message: string;
  details?: ValidationErrorItem[] | Record<string, unknown> | null;
}

export interface ErrorEnvelope {
  success: false;
  error: ErrorDetail;
  timestamp: string;
}

export interface MessageResponse {
  message: string;
}
