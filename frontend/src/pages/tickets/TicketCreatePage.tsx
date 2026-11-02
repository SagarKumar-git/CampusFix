/**
 * CampusFix SCR-03: Ticket Submission Flow
 *
 * Implements:
 * - Dynamic category dropdown populated from GET /api/v1/categories
 * - Title (min 5 chars), Description (min 10 chars), Location (min 3 chars)
 * - Priority selector with MEDIUM as default
 * - Duplicate submission prevention (disabled button + spinner while pending)
 * - Accessible validation messaging (aria-invalid, aria-describedby, role="alert")
 * - Navigation to /tickets/:id (UUID) upon HTTP 201 Created
 */

import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { categoriesApi } from '../../api/categories';
import { ticketsApi } from '../../api/tickets';
import { AlertBanner } from '../../components/ui/AlertBanner';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Textarea } from '../../components/ui/Textarea';
import { ChevronLeftIcon } from '../../components/ui/icons';
import type { Category, TicketPriority } from '../../types';

export const TicketCreatePage: React.FC = () => {
  const navigate = useNavigate();

  // Form State
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [location, setLocation] = useState('');
  const [priority, setPriority] = useState<TicketPriority>('MEDIUM');

  // Categories loading state
  const [categories, setCategories] = useState<Category[]>([]);
  const [isCategoriesLoading, setIsCategoriesLoading] = useState(true);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);

  // Form validation & submission state
  const [fieldErrors, setFieldErrors] = useState<{
    title?: string;
    description?: string;
    categoryId?: string;
    location?: string;
  }>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const fetchCategories = async () => {
      setIsCategoriesLoading(true);
      setCategoriesError(null);
      try {
        const data = await categoriesApi.listCategories();
        if (isMounted) {
          setCategories(data);
          if (data.length > 0) {
            setCategoryId((prev) => prev || data[0].id);
          }
        }
      } catch (err: unknown) {
        if (isMounted) {
          const msg =
            err instanceof Error ? err.message : 'Failed to load facility categories.';
          setCategoriesError(msg);
        }
      } finally {
        if (isMounted) {
          setIsCategoriesLoading(false);
        }
      }
    };

    fetchCategories();

    return () => {
      isMounted = false;
    };
  }, []);

  const validate = (): boolean => {
    const errors: {
      title?: string;
      description?: string;
      categoryId?: string;
      location?: string;
    } = {};

    const cleanTitle = title.trim();
    if (!cleanTitle) {
      errors.title = 'Title is required.';
    } else if (cleanTitle.length < 5) {
      errors.title = 'Title must be at least 5 characters in length.';
    } else if (cleanTitle.length > 120) {
      errors.title = 'Title cannot exceed 120 characters.';
    }

    const cleanDesc = description.trim();
    if (!cleanDesc) {
      errors.description = 'Description is required.';
    } else if (cleanDesc.length < 10) {
      errors.description = 'Description must be at least 10 characters detailing the incident.';
    } else if (cleanDesc.length > 2000) {
      errors.description = 'Description cannot exceed 2000 characters.';
    }

    const cleanLoc = location.trim();
    if (!cleanLoc) {
      errors.location = 'Campus location is required.';
    } else if (cleanLoc.length < 3) {
      errors.location = 'Location must be at least 3 characters (e.g. "Science Block A, Rm 402").';
    } else if (cleanLoc.length > 100) {
      errors.location = 'Location cannot exceed 100 characters.';
    }

    if (!categoryId) {
      errors.categoryId = 'Please select a facility category.';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiError(null);

    if (!validate()) {
      return;
    }

    setIsSubmitting(true);
    try {
      const createdTicket = await ticketsApi.createTicket({
        title: title.trim(),
        description: description.trim(),
        category_id: categoryId,
        location: location.trim(),
        priority,
      });

      // Redirect directly to the newly created ticket's detail view using its UUID
      navigate(`/tickets/${createdTicket.id}`, { state: { justCreated: true } });
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : 'Failed to submit incident ticket. Please verify your input.';
      setApiError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const priorityOptions = [
    { value: 'LOW', label: 'Low — Routine maintenance or cosmetic blemish' },
    { value: 'MEDIUM', label: 'Medium — Impaired fixture, workaround available (Default)' },
    { value: 'HIGH', label: 'High — Disrupting classroom, lab or facility operations' },
    { value: 'CRITICAL', label: 'Critical — Safety hazard or severe operational stoppage' },
  ];

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Back link & Header */}
      <div>
        <Link
          to="/student/tickets"
          className="inline-flex items-center gap-1 text-xs font-medium text-neutral-600 hover:text-neutral-900 mb-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
        >
          <ChevronLeftIcon className="w-3.5 h-3.5" />
          <span>Back to My Tickets</span>
        </Link>
        <h1 className="text-2xl font-bold text-neutral-900 tracking-tight">
          Report Facility Issue
        </h1>
        <p className="text-sm text-neutral-600 mt-1">
          Submit a new campus maintenance request. Facilities operations staff will review and dispatch a technician.
        </p>
      </div>

      {/* Global Category Fetch Error Alert */}
      {categoriesError && (
        <AlertBanner variant="error" title="Unable to Load Facility Categories">
          {categoriesError}
        </AlertBanner>
      )}

      {/* Global API Submission Error Alert */}
      {apiError && (
        <AlertBanner
          variant="error"
          title="Submission Failed"
          onDismiss={() => setApiError(null)}
        >
          {apiError}
        </AlertBanner>
      )}

      {/* Ticket Filing Form */}
      <div className="bg-white rounded-lg border border-neutral-200 p-6 sm:p-8 shadow-xs">
        <form onSubmit={handleSubmit} noValidate className="space-y-5">
          {/* Category Dropdown */}
          <Select
            id="ticket-category"
            label="Issue Category"
            required
            disabled={isCategoriesLoading || categories.length === 0}
            value={categoryId}
            error={fieldErrors.categoryId}
            helperText={
              isCategoriesLoading
                ? 'Loading categories from server...'
                : 'Select the operational category best matching this malfunction.'
            }
            onChange={(e) => {
              setCategoryId(e.target.value);
              if (fieldErrors.categoryId) {
                setFieldErrors({ ...fieldErrors, categoryId: undefined });
              }
            }}
          >
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>

          {/* Location Input */}
          <Input
            id="ticket-location"
            type="text"
            label="Campus Location"
            placeholder="e.g. Science Block A, Lecture Room 402"
            required
            value={location}
            error={fieldErrors.location}
            helperText="Specify the building, floor, room number, or outdoor landmark."
            onChange={(e) => {
              setLocation(e.target.value);
              if (fieldErrors.location) {
                setFieldErrors({ ...fieldErrors, location: undefined });
              }
            }}
          />

          {/* Priority Tier Selector */}
          <Select
            id="ticket-priority"
            label="Priority / Urgency Tier"
            required
            options={priorityOptions}
            value={priority}
            helperText="Default is Medium. Choose Critical only for active safety hazards."
            onChange={(e) => setPriority(e.target.value as TicketPriority)}
          />

          {/* Headline / Title */}
          <Input
            id="ticket-title"
            type="text"
            label="Issue Headline (Title)"
            placeholder="e.g. Projector HDMI Port Damaged in Room 402"
            required
            value={title}
            error={fieldErrors.title}
            helperText="Brief summary of the physical problem (minimum 5 characters)."
            onChange={(e) => {
              setTitle(e.target.value);
              if (fieldErrors.title) {
                setFieldErrors({ ...fieldErrors, title: undefined });
              }
            }}
          />

          {/* Detailed Context Breakdown */}
          <Textarea
            id="ticket-description"
            label="Detailed Description"
            placeholder="Describe the failure mode, symptoms, or any temporary workarounds attempted..."
            rows={5}
            required
            showCount
            minChars={10}
            maxLength={2000}
            value={description}
            error={fieldErrors.description}
            helperText="Provide specific details to help the maintenance technician diagnose the repair."
            onChange={(e) => {
              setDescription(e.target.value);
              if (fieldErrors.description) {
                setFieldErrors({ ...fieldErrors, description: undefined });
              }
            }}
          />

          {/* Form Actions */}
          <div className="flex flex-col-reverse sm:flex-row items-center justify-end gap-3 pt-4 border-t border-neutral-100">
            <Link to="/student/tickets" className="w-full sm:w-auto">
              <Button variant="secondary" className="w-full sm:w-auto">
                Cancel
              </Button>
            </Link>

            <Button
              type="submit"
              className="w-full sm:w-auto"
              isLoading={isSubmitting}
              loadingText="Submitting Work Order..."
              disabled={isCategoriesLoading || categories.length === 0}
            >
              Submit Work Order
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default TicketCreatePage;
