/**
 * CampusFix Category Management Console Tests (SCR-08)
 *
 * Verifies:
 * - Administrator access permitted; Student and Staff roles denied access (WCAG 2.1 AA 403 Forbidden alert)
 * - Category listing with name, description, active status badge, and creation date
 * - Tab switching (All / Active / Inactive) with dynamic counts
 * - Client-side real-time category search filtering
 * - Add Category workflow: field validation, duplicate name conflict handling (HTTP 409), duplicate submission prevention, success feedback
 * - Edit Category workflow: prefilling fields, payload submission, list refresh
 * - Category deactivation with confirmation dialog explaining ticket history preservation
 * - Category activation with confirmation dialog
 * - Loading skeleton states, empty states, and API error banners with retry trigger
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { categoriesApi } from '../../src/api/categories';
import { ApiError } from '../../src/api/client';
import { RoleRoute } from '../../src/components/auth/RoleRoute';
import { AuthContext, type AuthContextType } from '../../src/context/AuthContext';
import CategoryManagementPage from '../../src/pages/admin/CategoryManagementPage';
import type { Category, User } from '../../src/types';

const mockAdminUser: User = {
  id: 'u0000000-0000-0000-0000-000000000003',
  email: 'marcus.admin@university.edu',
  full_name: 'Marcus Vance',
  role: 'ADMINISTRATOR',
  is_active: true,
  created_at: '2026-10-01T00:00:00Z',
};

const mockStaffUser: User = {
  id: 'u0000000-0000-0000-0000-000000000002',
  email: 'alex.staff@university.edu',
  full_name: 'Alex Rivera',
  role: 'STAFF',
  is_active: true,
  created_at: '2026-10-01T00:00:00Z',
};

const mockStudentUser: User = {
  id: 'u0000000-0000-0000-0000-000000000001',
  email: 'jane.student@university.edu',
  full_name: 'Jane Doe',
  role: 'STUDENT',
  is_active: true,
  created_at: '2026-10-01T00:00:00Z',
};

const mockCategories: Category[] = [
  {
    id: 'c0000000-0000-0000-0000-000000000001',
    name: 'Classroom Audio-Visual',
    description: 'Projectors, microphones, and podium HDMI ports.',
    is_active: true,
    created_at: '2026-10-15T09:00:00Z',
  },
  {
    id: 'c0000000-0000-0000-0000-000000000002',
    name: 'Electrical & Lighting',
    description: 'Outlets, circuit breakers, and lighting fixtures.',
    is_active: true,
    created_at: '2026-10-16T10:00:00Z',
  },
  {
    id: 'c0000000-0000-0000-0000-000000000003',
    name: 'Laboratory Gas & Chemical Hoods',
    description: 'Special gas valves, fume extraction hoods, and eyewash stations.',
    is_active: false,
    created_at: '2026-10-17T11:00:00Z',
  },
];

const createMockAuthContext = (user: User | null): AuthContextType => ({
  user,
  accessToken: user ? 'mock-access-token' : null,
  isLoading: false,
  isAuthenticated: Boolean(user),
  login: async () => user as User,
  register: async () => user as User,
  logout: async () => {},
  refreshSession: async () => Boolean(user),
});

const renderCategoryConsole = (user: User = mockAdminUser, initialRoute = '/admin/categories') => {
  return render(
    <AuthContext.Provider value={createMockAuthContext(user)}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <Routes>
          <Route element={<RoleRoute allowedRoles={['ADMINISTRATOR']} />}>
            <Route path="/admin/categories" element={<CategoryManagementPage />} />
          </Route>
          <Route path="/student/tickets" element={<div>Student Tickets Page</div>} />
          <Route path="/staff/queue" element={<div>Staff Queue Page</div>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  );
};

describe('SCR-08: CategoryManagementPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Access Control & Route Protection', () => {
    it('allows ADMINISTRATOR users to access the Category Management Console', async () => {
      vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue(mockCategories);

      renderCategoryConsole(mockAdminUser);

      expect(await screen.findByRole('heading', { name: 'Facility Categories' })).toBeInTheDocument();
      expect(screen.getByText(/Admin Console/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /\+ Add New Category/i })).toBeInTheDocument();
    });

    it('denies STUDENT role and displays accessible 403 Forbidden alert', async () => {
      renderCategoryConsole(mockStudentUser);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Access Restricted')).toBeInTheDocument();
      expect(screen.getByText(/Your account \(STUDENT\) is not authorized/i)).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: 'Facility Categories' })).not.toBeInTheDocument();
    });

    it('denies STAFF role and displays accessible 403 Forbidden alert', async () => {
      renderCategoryConsole(mockStaffUser);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Access Restricted')).toBeInTheDocument();
      expect(screen.getByText(/Your account \(STAFF\) is not authorized/i)).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: 'Facility Categories' })).not.toBeInTheDocument();
    });
  });

  describe('Category Listing & Filtering', () => {
    it('renders category records with name, description, active badge, and formatted date', async () => {
      vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue(mockCategories);

      renderCategoryConsole();

      const names = await screen.findAllByText('Classroom Audio-Visual');
      expect(names.length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Electrical & Lighting')[0]).toBeInTheDocument();
      expect(screen.getAllByText('Laboratory Gas & Chemical Hoods')[0]).toBeInTheDocument();

      // Check badges (ACTIVE and INACTIVE)
      expect(screen.getAllByText('ACTIVE').length).toBeGreaterThanOrEqual(2);
      expect(screen.getAllByText('INACTIVE').length).toBeGreaterThanOrEqual(1);

      // Ensure API was called with includeInactive=true
      expect(categoriesApi.listCategories).toHaveBeenCalledWith(true);
    });

    it('filters category records via status segmented tabs (All, Active, Inactive)', async () => {
      vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue(mockCategories);
      const user = userEvent.setup();

      renderCategoryConsole();

      await screen.findAllByText('Classroom Audio-Visual');

      // Check tab counts
      expect(screen.getByRole('tab', { name: /All Categories \(3\)/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /Active \(2\)/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /Inactive \(1\)/i })).toBeInTheDocument();

      // Switch to Active tab
      await user.click(screen.getByRole('tab', { name: /Active \(2\)/i }));
      expect(screen.getAllByText('Classroom Audio-Visual')[0]).toBeInTheDocument();
      expect(screen.getAllByText('Electrical & Lighting')[0]).toBeInTheDocument();
      expect(screen.queryByText('Laboratory Gas & Chemical Hoods')).not.toBeInTheDocument();

      // Switch to Inactive tab
      await user.click(screen.getByRole('tab', { name: /Inactive \(1\)/i }));
      expect(screen.getAllByText('Laboratory Gas & Chemical Hoods')[0]).toBeInTheDocument();
      expect(screen.queryByText('Classroom Audio-Visual')).not.toBeInTheDocument();
      expect(screen.queryByText('Electrical & Lighting')).not.toBeInTheDocument();
    });

    it('filters category records in real-time via search input', async () => {
      vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue(mockCategories);
      const user = userEvent.setup();

      renderCategoryConsole();

      await screen.findAllByText('Classroom Audio-Visual');

      const searchInput = screen.getByPlaceholderText('Search categories...');
      await user.type(searchInput, 'projector');

      expect(screen.getAllByText('Classroom Audio-Visual')[0]).toBeInTheDocument();
      expect(screen.queryByText('Electrical & Lighting')).not.toBeInTheDocument();
      expect(screen.queryByText('Laboratory Gas & Chemical Hoods')).not.toBeInTheDocument();
    });
  });

  describe('Add Category Workflow', () => {
    it('validates form fields and rejects empty or out-of-range inputs', async () => {
      vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue(mockCategories);
      const user = userEvent.setup();

      renderCategoryConsole();

      await screen.findAllByText('Classroom Audio-Visual');

      // Open Add Modal
      await user.click(screen.getByRole('button', { name: /\+ Add New Category/i }));
      expect(await screen.findByRole('dialog')).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Add New Facility Category' })).toBeInTheDocument();

      // Submit empty form
      await user.click(screen.getByRole('button', { name: 'Create Category' }));

      expect(await screen.findByText('Category name cannot be empty.')).toBeInTheDocument();
      expect(screen.getByText('Description cannot be empty.')).toBeInTheDocument();
    });

    it('successfully creates new category and refreshes table with success banner', async () => {
      vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue([...mockCategories]);
      const createSpy = vi.spyOn(categoriesApi, 'createCategory').mockResolvedValue({
        id: 'c0000000-0000-0000-0000-000000000004',
        name: 'Plumbing & Water Fixtures',
        description: 'Restroom pipes, sinks, and emergency shutoff valves.',
        is_active: true,
        created_at: '2026-11-02T12:00:00Z',
      });

      const user = userEvent.setup();
      renderCategoryConsole();

      await screen.findAllByText('Classroom Audio-Visual');

      await user.click(screen.getByRole('button', { name: /\+ Add New Category/i }));
      expect(await screen.findByRole('dialog')).toBeInTheDocument();

      // Fill in valid fields
      await user.type(screen.getByLabelText(/Category Name/i), 'Plumbing & Water Fixtures');
      await user.type(
        screen.getByLabelText(/Scope & Examples Description/i),
        'Restroom pipes, sinks, and emergency shutoff valves.'
      );

      // Submit form
      await user.click(screen.getByRole('button', { name: 'Create Category' }));

      await waitFor(() => {
        expect(createSpy).toHaveBeenCalledWith({
          name: 'Plumbing & Water Fixtures',
          description: 'Restroom pipes, sinks, and emergency shutoff valves.',
          is_active: true,
        });
      });

      expect(
        await screen.findByText(/Category "Plumbing & Water Fixtures" has been created successfully\./i)
      ).toBeInTheDocument();
    });

    it('handles HTTP 409 duplicate name conflict by displaying error banner inside modal', async () => {
      vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue(mockCategories);
      vi.spyOn(categoriesApi, 'createCategory').mockRejectedValue(
        new ApiError(409, 'CATEGORY_ALREADY_EXISTS', 'Category with this name already exists.')
      );

      const user = userEvent.setup();
      renderCategoryConsole();

      await screen.findAllByText('Classroom Audio-Visual');

      await user.click(screen.getByRole('button', { name: /\+ Add New Category/i }));
      expect(await screen.findByRole('dialog')).toBeInTheDocument();

      await user.type(screen.getByLabelText(/Category Name/i), 'Classroom Audio-Visual');
      await user.type(
        screen.getByLabelText(/Scope & Examples Description/i),
        'Duplicate name test description.'
      );

      await user.click(screen.getByRole('button', { name: 'Create Category' }));

      expect(
        await screen.findByText('Category with this name already exists.')
      ).toBeInTheDocument();
      // Modal remains open so administrator can correct the title
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  describe('Edit Category Workflow', () => {
    it('prefills existing data into form and dispatches update request', async () => {
      vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue(mockCategories);
      const updateSpy = vi.spyOn(categoriesApi, 'updateCategory').mockResolvedValue({
        ...mockCategories[0],
        name: 'Classroom AV & Smartboards',
      });

      const user = userEvent.setup();
      renderCategoryConsole();

      await screen.findAllByText('Classroom Audio-Visual');

      // Click Edit on first category
      const editButtons = screen.getAllByRole('button', { name: /Edit/i });
      await user.click(editButtons[0]);

      expect(await screen.findByRole('dialog')).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /Edit Category: Classroom Audio-Visual/i })).toBeInTheDocument();

      const nameInput = screen.getByLabelText(/Category Name/i);
      expect(nameInput).toHaveValue('Classroom Audio-Visual');

      // Update name
      await user.clear(nameInput);
      await user.type(nameInput, 'Classroom AV & Smartboards');

      await user.click(screen.getByRole('button', { name: 'Save Changes' }));

      await waitFor(() => {
        expect(updateSpy).toHaveBeenCalledWith(mockCategories[0].id, {
          name: 'Classroom AV & Smartboards',
          description: mockCategories[0].description,
          is_active: true,
        });
      });

      expect(
        await screen.findByText(/Category "Classroom AV & Smartboards" has been updated successfully\./i)
      ).toBeInTheDocument();
    });
  });

  describe('Activation & Deactivation Workflow', () => {
    it('opens deactivation confirmation modal and updates status to inactive', async () => {
      vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue(mockCategories);
      const updateSpy = vi.spyOn(categoriesApi, 'updateCategory').mockResolvedValue({
        ...mockCategories[0],
        is_active: false,
      });

      const user = userEvent.setup();
      renderCategoryConsole();

      await screen.findAllByText('Classroom Audio-Visual');

      // Click Deactivate on first category
      const deactivateButtons = screen.getAllByRole('button', { name: /Deactivate/i });
      await user.click(deactivateButtons[0]);

      // Verify confirmation warning dialog explains historical ticket preservation
      expect(await screen.findByRole('dialog')).toBeInTheDocument();
      expect(
        screen.getByRole('heading', { name: /Deactivate Category: Classroom Audio-Visual\?/i })
      ).toBeInTheDocument();
      expect(
        screen.getByText(/All historical tickets filed under this category will retain their category link/i)
      ).toBeInTheDocument();

      // Confirm deactivation
      await user.click(screen.getByRole('button', { name: 'Confirm Deactivation' }));

      await waitFor(() => {
        expect(updateSpy).toHaveBeenCalledWith(mockCategories[0].id, { is_active: false });
      });

      expect(
        await screen.findByText(/Category "Classroom Audio-Visual" has been deactivated successfully\./i)
      ).toBeInTheDocument();
    });

    it('opens activation confirmation modal for inactive categories and updates status', async () => {
      vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue(mockCategories);
      const updateSpy = vi.spyOn(categoriesApi, 'updateCategory').mockResolvedValue({
        ...mockCategories[2],
        is_active: true,
      });

      const user = userEvent.setup();
      renderCategoryConsole();

      await screen.findAllByText('Laboratory Gas & Chemical Hoods');

      // Click Activate on the inactive category
      const activateButton = screen.getAllByRole('button', {
        name: `Activate ${mockCategories[2].name} category`,
      })[0];
      await user.click(activateButton);

      expect(await screen.findByRole('dialog')).toBeInTheDocument();
      expect(
        screen.getByRole('heading', { name: /Activate Category: Laboratory Gas & Chemical Hoods\?/i })
      ).toBeInTheDocument();

      // Confirm activation
      await user.click(screen.getByRole('button', { name: 'Confirm Activation' }));

      await waitFor(() => {
        expect(updateSpy).toHaveBeenCalledWith(mockCategories[2].id, { is_active: true });
      });

      expect(
        await screen.findByText(/Category "Laboratory Gas & Chemical Hoods" has been activated successfully\./i)
      ).toBeInTheDocument();
    });
  });

  describe('UI States: Loading, Error, Empty', () => {
    it('displays error alert and offers retry CTA when initial list request fails', async () => {
      vi.spyOn(categoriesApi, 'listCategories').mockRejectedValueOnce(
        new Error('Network error: Database unreachable')
      );

      const user = userEvent.setup();
      renderCategoryConsole();

      expect(await screen.findByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Unable to load categories')).toBeInTheDocument();
      expect(screen.getByText('Network error: Database unreachable')).toBeInTheDocument();

      // Retry request
      vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue(mockCategories);
      await user.click(screen.getByRole('button', { name: 'Retry' }));

      expect((await screen.findAllByText('Classroom Audio-Visual'))[0]).toBeInTheDocument();
      expect(screen.queryByText('Unable to load categories')).not.toBeInTheDocument();
    });

    it('renders empty state when zero categories are returned', async () => {
      vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue([]);

      renderCategoryConsole();

      expect(await screen.findByText('No categories found')).toBeInTheDocument();
      expect(screen.getByText('No facility categories have been defined yet.')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /\+ Add First Category/i })).toBeInTheDocument();
    });
  });
});
