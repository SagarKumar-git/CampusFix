/**
 * CampusFix Accessible Input Component
 *
 * Implements:
 * - Programmatic label association with htmlFor
 * - Accessible error messaging with aria-invalid and aria-describedby
 * - High-contrast focus state and error state rings
 */

import React, { forwardRef, useId } from 'react';

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
  error?: string;
  required?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      id: customId,
      label,
      helperText,
      error,
      required,
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
          <input
            ref={ref}
            id={id}
            disabled={disabled}
            aria-invalid={Boolean(error)}
            aria-describedby={describedBy}
            required={required}
            className={`w-full rounded-md border text-sm text-neutral-800 placeholder-neutral-400 bg-white px-3 py-2 min-h-[44px] transition-colors focus:outline-none focus:ring-2 ${
              error
                ? 'border-red-500 bg-red-50/20 focus:border-red-500 focus:ring-red-500'
                : 'border-neutral-300 focus:border-brand-500 focus:ring-brand-500'
            } disabled:bg-neutral-100 disabled:text-neutral-400 disabled:cursor-not-allowed ${className}`}
            {...props}
          />
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

Input.displayName = 'Input';
export default Input;
