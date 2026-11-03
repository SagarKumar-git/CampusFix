/**
 * CampusFix Category Status Confirmation Modal
 *
 * Implements accessible confirmation dialog for category deactivation / activation:
 * - Details consequence on student filing and historical ticket immutability
 * - Prevents accidental deactivations with explicit confirmation
 * - Handles in-flight submission loading state
 */

import React, { useState } from 'react';
import { AlertBanner, Button, Modal } from '../../../components/ui';
import type { Category } from '../../../types';

export interface CategoryStatusModalProps {
  isOpen: boolean;
  onClose: () => void;
  category: Category | null;
  targetActive: boolean;
  onConfirm: (category: Category, targetActive: boolean) => Promise<void>;
}

export const CategoryStatusModal: React.FC<CategoryStatusModalProps> = ({
  isOpen,
  onClose,
  category,
  targetActive,
  onConfirm,
}) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!category) return null;

  const isDeactivating = !targetActive;

  const handleConfirm = async () => {
    setError(null);
    setIsSubmitting(true);
    try {
      await onConfirm(category, targetActive);
      onClose();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to update category status.';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const title = isDeactivating
    ? `Deactivate Category: ${category.name}?`
    : `Activate Category: ${category.name}?`;

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => {
        if (!isSubmitting) onClose();
      }}
      title={title}
      maxWidth="md"
      preventCloseOnEscape={isSubmitting}
      preventCloseOnClickOutside={isSubmitting}
    >
      <div className="space-y-4">
        {error && (
          <AlertBanner
            variant="error"
            title="Action Failed"
            onDismiss={() => setError(null)}
          >
            {error}
          </AlertBanner>
        )}

        {isDeactivating ? (
          <div className="space-y-3 text-sm text-neutral-700">
            <p>
              Are you sure you want to deactivate{' '}
              <strong className="text-neutral-900">{category.name}</strong>?
            </p>
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-md text-amber-900 text-xs space-y-1">
              <p className="font-semibold">What happens when a category is deactivated:</p>
              <ul className="list-disc list-inside space-y-0.5 text-amber-800">
                <li>Students will no longer see this category when filing new maintenance tickets.</li>
                <li>All historical tickets filed under this category will retain their category link and audit log.</li>
                <li>You can reactivate this category at any time from this console.</li>
              </ul>
            </div>
          </div>
        ) : (
          <div className="space-y-3 text-sm text-neutral-700">
            <p>
              Are you sure you want to activate{' '}
              <strong className="text-neutral-900">{category.name}</strong>?
            </p>
            <p className="text-xs text-neutral-500">
              Activating this category will make it immediately visible and selectable in the incident reporting dropdown for all students.
            </p>
          </div>
        )}

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
            type="button"
            variant={isDeactivating ? 'danger' : 'primary'}
            isLoading={isSubmitting}
            loadingText={isDeactivating ? 'Deactivating...' : 'Activating...'}
            onClick={handleConfirm}
          >
            {isDeactivating ? 'Confirm Deactivation' : 'Confirm Activation'}
          </Button>
        </div>
      </div>
    </Modal>
  );
};

export default CategoryStatusModal;
