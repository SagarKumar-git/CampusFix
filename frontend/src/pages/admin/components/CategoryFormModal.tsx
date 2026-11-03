/**
 * CampusFix Category Form Modal Component
 *
 * Implements Add and Edit category workflows:
 * - Controlled input validation (Name 2-100 chars, Description 5-500 chars)
 * - Initial/current active status toggle
 * - Prevents duplicate form submissions during in-flight network requests
 * - Friendly error presentation for HTTP 409 duplicate name conflicts
 */

import React, { useEffect, useState } from 'react';
import { AlertBanner, Button, Input, Modal, Textarea } from '../../../components/ui';
import type { Category, CategoryCreatePayload, CategoryUpdatePayload } from '../../../types';

export interface CategoryFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  category?: Category | null;
  onSubmit: (
    payload: CategoryCreatePayload | CategoryUpdatePayload,
    isEdit: boolean
  ) => Promise<void>;
}

export const CategoryFormModal: React.FC<CategoryFormModalProps> = ({
  isOpen,
  onClose,
  category,
  onSubmit,
}) => {
  const isEdit = Boolean(category);

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isActive, setIsActive] = useState(true);

  const [fieldErrors, setFieldErrors] = useState<{ name?: string; description?: string }>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Initialize or reset form state when modal opens or category changes
  useEffect(() => {
    if (isOpen) {
      if (category) {
        setName(category.name);
        setDescription(category.description);
        setIsActive(category.is_active);
      } else {
        setName('');
        setDescription('');
        setIsActive(true);
      }
      setFieldErrors({});
      setSubmitError(null);
      setIsSubmitting(false);
    }
  }, [isOpen, category]);

  const validate = (): boolean => {
    const errors: { name?: string; description?: string } = {};
    const trimmedName = name.trim();
    const trimmedDesc = description.trim();

    if (!trimmedName) {
      errors.name = 'Category name cannot be empty.';
    } else if (trimmedName.length < 2 || trimmedName.length > 100) {
      errors.name = 'Category name must be between 2 and 100 characters.';
    }

    if (!trimmedDesc) {
      errors.description = 'Description cannot be empty.';
    } else if (trimmedDesc.length < 5) {
      errors.description = 'Description must be at least 5 characters.';
    } else if (trimmedDesc.length > 500) {
      errors.description = 'Description cannot exceed 500 characters.';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (!validate()) {
      return;
    }

    setIsSubmitting(true);
    try {
      const payload = {
        name: name.trim(),
        description: description.trim(),
        is_active: isActive,
      };
      await onSubmit(payload, isEdit);
      onClose();
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : 'An unexpected error occurred while saving category.';
      setSubmitError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const modalTitle = isEdit ? `Edit Category: ${category?.name}` : 'Add New Facility Category';
  const modalDescription = isEdit
    ? 'Update operational scope description, title, or active status.'
    : 'Define a new campus maintenance category available during incident filing.';

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => {
        if (!isSubmitting) onClose();
      }}
      title={modalTitle}
      description={modalDescription}
      maxWidth="md"
      preventCloseOnEscape={isSubmitting}
      preventCloseOnClickOutside={isSubmitting}
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {submitError && (
          <AlertBanner
            variant="error"
            title="Unable to save category"
            onDismiss={() => setSubmitError(null)}
          >
            {submitError}
          </AlertBanner>
        )}

        <Input
          id="category-name-input"
          label="Category Name"
          required
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            if (fieldErrors.name) {
              setFieldErrors((prev) => ({ ...prev, name: undefined }));
            }
          }}
          error={fieldErrors.name}
          placeholder="e.g. Classroom Audio-Visual"
          disabled={isSubmitting}
          maxLength={100}
        />

        <Textarea
          id="category-description-input"
          label="Scope & Examples Description"
          required
          showCount
          minChars={5}
          maxLength={500}
          rows={4}
          value={description}
          onChange={(e) => {
            setDescription(e.target.value);
            if (fieldErrors.description) {
              setFieldErrors((prev) => ({ ...prev, description: undefined }));
            }
          }}
          error={fieldErrors.description}
          placeholder="Detailed guidance on incidents belonging to this category (e.g. Projectors, microphones, wall jacks)..."
          disabled={isSubmitting}
        />

        <div className="pt-2">
          <label className="relative flex items-start gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              id="category-active-toggle"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              disabled={isSubmitting}
              className="mt-1 h-4 w-4 rounded border-neutral-300 text-brand-600 focus:ring-brand-500 disabled:opacity-50"
            />
            <div className="text-sm">
              <span className="font-medium text-neutral-800">
                Active & available for ticket submission
              </span>
              <p className="text-xs text-neutral-500">
                When unchecked, students cannot choose this category when filing new issues.
              </p>
            </div>
          </label>
        </div>

        <div className="mt-6 flex items-center justify-end gap-3 pt-4 border-t border-neutral-100">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            isLoading={isSubmitting}
            loadingText={isEdit ? 'Saving Changes...' : 'Creating Category...'}
          >
            {isEdit ? 'Save Changes' : 'Create Category'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};

export default CategoryFormModal;
