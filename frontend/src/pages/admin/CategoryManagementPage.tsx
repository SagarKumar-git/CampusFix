/**
 * CampusFix SCR-08: Category Management Console
 *
 * Implements administrative maintenance category lifecycle operations:
 * - List categories with active/inactive status breakdown (include_inactive=true)
 * - Create new categories via POST /api/v1/categories (409 conflict detection)
 * - Update existing categories via PATCH /api/v1/categories/{id}
 * - Activate & Deactivate operational categories with confirmation
 * - Filter categories by active status tabs and search query
 * - Responsive layout: Accessible desktop table & mobile card stacking
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { categoriesApi } from '../../api/categories';
import {
  ActiveStatusBadge,
  AlertBanner,
  Button,
  Column,
  DataTable,
  PlusIcon,
} from '../../components/ui';
import type { Category, CategoryCreatePayload, CategoryUpdatePayload } from '../../types';
import CategoryFormModal from './components/CategoryFormModal';
import CategoryStatusModal from './components/CategoryStatusModal';

type FilterTab = 'ALL' | 'ACTIVE' | 'INACTIVE';

export const CategoryManagementPage: React.FC = () => {
  const [categories, setCategories] = useState<Category[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);

  // Filters
  const [activeTab, setActiveTab] = useState<FilterTab>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Modals
  const [isFormModalOpen, setIsFormModalOpen] = useState<boolean>(false);
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);

  const [isStatusModalOpen, setIsStatusModalOpen] = useState<boolean>(false);
  const [statusTargetCategory, setStatusTargetCategory] = useState<Category | null>(null);
  const [targetActiveState, setTargetActiveState] = useState<boolean>(false);

  // Fetch categories from backend (including inactive categories for admin view)
  const loadCategories = useCallback(async () => {
    setIsLoading(true);
    setFetchError(null);
    try {
      const items = await categoriesApi.listCategories(true);
      // Sort alphabetically by name
      items.sort((a, b) => a.name.localeCompare(b.name));
      setCategories(items);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to retrieve facility categories.';
      setFetchError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  // Tab counts
  const counts = useMemo(() => {
    const total = categories.length;
    const active = categories.filter((c) => c.is_active).length;
    const inactive = total - active;
    return { total, active, inactive };
  }, [categories]);

  // Filtered and searched category list
  const filteredCategories = useMemo(() => {
    return categories.filter((cat) => {
      // Tab filter
      if (activeTab === 'ACTIVE' && !cat.is_active) return false;
      if (activeTab === 'INACTIVE' && cat.is_active) return false;

      // Search query filter
      if (searchQuery.trim()) {
        const query = searchQuery.trim().toLowerCase();
        const matchesName = cat.name.toLowerCase().includes(query);
        const matchesDesc = cat.description.toLowerCase().includes(query);
        return matchesName || matchesDesc;
      }

      return true;
    });
  }, [categories, activeTab, searchQuery]);

  // Handle open Add Modal
  const handleOpenAdd = () => {
    setEditingCategory(null);
    setIsFormModalOpen(true);
  };

  // Handle open Edit Modal
  const handleOpenEdit = (category: Category) => {
    setEditingCategory(category);
    setIsFormModalOpen(true);
  };

  // Handle form submit (Add or Edit)
  const handleFormSubmit = async (
    payload: CategoryCreatePayload | CategoryUpdatePayload,
    isEdit: boolean
  ) => {
    if (isEdit && editingCategory) {
      const updated = await categoriesApi.updateCategory(editingCategory.id, payload);
      setSuccessBanner(`Category "${updated.name}" has been updated successfully.`);
    } else {
      const created = await categoriesApi.createCategory(payload as CategoryCreatePayload);
      setSuccessBanner(`Category "${created.name}" has been created successfully.`);
    }
    await loadCategories();
  };

  // Handle open Status (Deactivate / Activate) Modal
  const handleOpenStatusModal = (category: Category, targetActive: boolean) => {
    setStatusTargetCategory(category);
    setTargetActiveState(targetActive);
    setIsStatusModalOpen(true);
  };

  // Handle confirm status change
  const handleStatusConfirm = async (category: Category, targetActive: boolean) => {
    await categoriesApi.updateCategory(category.id, { is_active: targetActive });
    setSuccessBanner(
      `Category "${category.name}" has been ${targetActive ? 'activated' : 'deactivated'} successfully.`
    );
    await loadCategories();
  };

  // DataTable columns definition
  const columns: Column<Category>[] = [
    {
      id: 'name',
      header: 'Category Name',
      accessor: 'name',
      render: (cat) => (
        <div className="font-semibold text-neutral-900">{cat.name}</div>
      ),
    },
    {
      id: 'description',
      header: 'Scope & Description',
      accessor: 'description',
      render: (cat) => (
        <div className="text-neutral-600 line-clamp-2 max-w-md text-xs sm:text-sm">
          {cat.description}
        </div>
      ),
    },
    {
      id: 'status',
      header: 'Status',
      accessor: 'is_active',
      render: (cat) => <ActiveStatusBadge isActive={cat.is_active} />,
    },
    {
      id: 'created_at',
      header: 'Created',
      render: (cat) => {
        if (!cat.created_at) return <span className="text-neutral-400">—</span>;
        try {
          return (
            <span className="text-neutral-500 text-xs sm:text-sm whitespace-nowrap">
              {new Date(cat.created_at).toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
              })}
            </span>
          );
        } catch {
          return <span className="text-neutral-400">—</span>;
        }
      },
    },
    {
      id: 'actions',
      header: 'Actions',
      className: 'text-right',
      headerClassName: 'text-right',
      render: (cat) => (
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => handleOpenEdit(cat)}
            aria-label={`Edit ${cat.name} category`}
          >
            Edit
          </Button>

          {cat.is_active ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleOpenStatusModal(cat, false)}
              aria-label={`Deactivate ${cat.name} category`}
              className="text-red-600 hover:text-red-700 hover:bg-red-50 border border-red-200"
            >
              Deactivate
            </Button>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleOpenStatusModal(cat, true)}
              aria-label={`Activate ${cat.name} category`}
              className="text-emerald-700 hover:text-emerald-800 hover:bg-emerald-50 border border-emerald-200"
            >
              Activate
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <span className="inline-block px-2.5 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-900 mb-1 tracking-wider uppercase">
            Admin Console
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-neutral-900">
            Facility Categories
          </h1>
          <p className="text-sm text-neutral-500 mt-0.5">
            Configure the maintenance taxonomy and incident categories available to students.
          </p>
        </div>

        <div>
          <Button
            variant="primary"
            leftIcon={<PlusIcon className="w-5 h-5" />}
            onClick={handleOpenAdd}
          >
            + Add New Category
          </Button>
        </div>
      </div>

      {/* Success Notification Banner */}
      {successBanner && (
        <AlertBanner
          variant="success"
          title="Operation Successful"
          onDismiss={() => setSuccessBanner(null)}
        >
          {successBanner}
        </AlertBanner>
      )}

      {/* Error Notification Banner */}
      {fetchError && (
        <AlertBanner
          variant="error"
          title="Unable to load categories"
          onDismiss={() => setFetchError(null)}
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <span>{fetchError}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={loadCategories}
              className="text-red-700 hover:text-red-800 underline underline-offset-2 p-0 h-auto"
            >
              Retry
            </Button>
          </div>
        </AlertBanner>
      )}

      {/* Filter Tabs & Search Bar */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-white p-3 rounded-lg border border-neutral-200">
        {/* Status Segmented Tabs */}
        <div
          role="tablist"
          aria-label="Filter categories by active status"
          className="flex items-center gap-1 bg-neutral-100 p-1 rounded-md"
        >
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'ALL'}
            onClick={() => setActiveTab('ALL')}
            className={`px-3 py-1.5 text-xs font-medium rounded transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
              activeTab === 'ALL'
                ? 'bg-white text-neutral-900 shadow-xs'
                : 'text-neutral-600 hover:text-neutral-900'
            }`}
          >
            All Categories ({counts.total})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'ACTIVE'}
            onClick={() => setActiveTab('ACTIVE')}
            className={`px-3 py-1.5 text-xs font-medium rounded transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
              activeTab === 'ACTIVE'
                ? 'bg-white text-neutral-900 shadow-xs'
                : 'text-neutral-600 hover:text-neutral-900'
            }`}
          >
            Active ({counts.active})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'INACTIVE'}
            onClick={() => setActiveTab('INACTIVE')}
            className={`px-3 py-1.5 text-xs font-medium rounded transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
              activeTab === 'INACTIVE'
                ? 'bg-white text-neutral-900 shadow-xs'
                : 'text-neutral-600 hover:text-neutral-900'
            }`}
          >
            Inactive ({counts.inactive})
          </button>
        </div>

        {/* Real-time Category Search */}
        <div className="relative w-full md:w-72">
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search categories..."
            aria-label="Search categories by name or description"
            className="w-full pl-3 pr-8 py-1.5 text-xs rounded-md border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600 text-xs"
              aria-label="Clear search query"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Categories DataTable */}
      <DataTable
        columns={columns}
        data={filteredCategories}
        keyField="id"
        isLoading={isLoading}
        emptyTitle="No categories found"
        emptyDescription={
          searchQuery
            ? `No categories match "${searchQuery}".`
            : activeTab !== 'ALL'
            ? `No ${activeTab.toLowerCase()} categories found.`
            : 'No facility categories have been defined yet.'
        }
        emptyAction={
          !searchQuery && activeTab === 'ALL' ? (
            <Button variant="primary" size="sm" onClick={handleOpenAdd}>
              + Add First Category
            </Button>
          ) : undefined
        }
      />

      {/* Add / Edit Category Modal */}
      <CategoryFormModal
        isOpen={isFormModalOpen}
        onClose={() => setIsFormModalOpen(false)}
        category={editingCategory}
        onSubmit={handleFormSubmit}
      />

      {/* Deactivation / Activation Confirmation Modal */}
      <CategoryStatusModal
        isOpen={isStatusModalOpen}
        onClose={() => setIsStatusModalOpen(false)}
        category={statusTargetCategory}
        targetActive={targetActiveState}
        onConfirm={handleStatusConfirm}
      />
    </div>
  );
};

export default CategoryManagementPage;
