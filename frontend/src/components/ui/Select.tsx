/**
 * CampusFix Accessible Select Component
 *
 * Implements:
 * - Programmatic label association
 * - Screen-reader error announcements with aria-invalid & aria-describedby
 * - Semantic chevron dropdown affordance
 */

import React, { forwardRef, useId } from 'react';
import { ChevronDownIcon } from './icons';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  helperText?: string;
  error?: string;
  required?: boolean;
  options?: SelectOption[];
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      id: customId,
      label,
      helperText,
      error,
      required,
      options,
      children,
      className = '',
      disabled,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const id = customId || generatedId;
    const errorId = `${id}-error`;
    const helperId = `${id}-helper`;

    const describedBy = [
      error ? errorId : null,
      helperText ? helperId : null,
    ]
      .filter(Boolean)
      .join(' ') || undefined;

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={id}
            className="block text-xs font-semibold text-neutral-700 uppercase tracking-wider mb-1"
          >
            {label}
            {required && (
              <span className="text-red-500 ml-1" aria-hidden="true">
                *
              </span>
            )}
          </label>
        )}

        <div className="relative">
          <select
            ref={ref}
            id={id}
            disabled={disabled}
            aria-invalid={Boolean(error)}
            aria-describedby={describedBy}
            required={required}
            className={`w-full appearance-none rounded-md border text-sm text-neutral-800 bg-white px-3 py-2 pr-10 min-h-[44px] transition-colors focus:outline-none focus:ring-2 ${
              error
                ? 'border-red-500 bg-red-50/20 focus:border-red-500 focus:ring-red-500'
                : 'border-neutral-300 focus:border-brand-500 focus:ring-brand-500'
            } disabled:bg-neutral-100 disabled:text-neutral-400 disabled:cursor-not-allowed ${className}`}
            {...props}
          >
            {options
              ? options.map((opt) => (
                  <option
                    key={opt.value}
                    value={opt.value}
                    disabled={opt.disabled}
                  >
                    {opt.label}
                  </option>
                ))
              : children}
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-neutral-500">
            <ChevronDownIcon className="w-4 h-4" />
          </div>
        </div>

        {error ? (
          <p
            id={errorId}
            className="flex items-center gap-1 text-xs text-red-600 mt-1 font-medium"
            role="alert"
          >
            {error}
          </p>
        ) : helperText ? (
          <p id={helperId} className="text-xs text-neutral-500 mt-1">
            {helperText}
          </p>
        ) : null}
      </div>
    );
  }
);

Select.displayName = 'Select';
export default Select;
