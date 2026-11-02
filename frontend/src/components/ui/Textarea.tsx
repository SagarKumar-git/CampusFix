/**
 * CampusFix Accessible Textarea Component
 *
 * Implements:
 * - Programmatic label and error associations
 * - Character count display and min/max length indicators
 * - Screen-reader error announcements with role="alert"
 */

import React, { forwardRef, useId } from 'react';

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  helperText?: string;
  error?: string;
  required?: boolean;
  showCount?: boolean;
  minChars?: number;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      id: customId,
      label,
      helperText,
      error,
      required,
      showCount = false,
      minChars,
      maxLength,
      value,
      defaultValue,
      className = '',
      disabled,
      rows = 4,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const id = customId || generatedId;
    const errorId = `${id}-error`;
    const helperId = `${id}-helper`;
    const counterId = `${id}-counter`;

    const describedBy = [
      error ? errorId : null,
      helperText ? helperId : null,
      showCount ? counterId : null,
    ]
      .filter(Boolean)
      .join(' ') || undefined;

    const currentLength = typeof value === 'string'
      ? value.length
      : typeof defaultValue === 'string'
      ? defaultValue.length
      : 0;

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
          <textarea
            ref={ref}
            id={id}
            rows={rows}
            disabled={disabled}
            aria-invalid={Boolean(error)}
            aria-describedby={describedBy}
            required={required}
            maxLength={maxLength}
            value={value}
            defaultValue={defaultValue}
            className={`w-full rounded-md border text-sm text-neutral-800 placeholder-neutral-400 bg-white p-3 transition-colors focus:outline-none focus:ring-2 ${
              error
                ? 'border-red-500 bg-red-50/20 focus:border-red-500 focus:ring-red-500'
                : 'border-neutral-300 focus:border-brand-500 focus:ring-brand-500'
            } disabled:bg-neutral-100 disabled:text-neutral-400 disabled:cursor-not-allowed ${className}`}
            {...props}
          />
        </div>

        <div className="flex items-center justify-between gap-2 mt-1">
          <div className="flex-1">
            {error ? (
              <p
                id={errorId}
                className="flex items-center gap-1 text-xs text-red-600 font-medium"
                role="alert"
              >
                {error}
              </p>
            ) : helperText ? (
              <p id={helperId} className="text-xs text-neutral-500">
                {helperText}
              </p>
            ) : null}
          </div>

          {showCount && (
            <span
              id={counterId}
              className={`text-[11px] font-mono shrink-0 ${
                minChars && currentLength < minChars
                  ? 'text-amber-700'
                  : 'text-neutral-500'
              }`}
              aria-live="polite"
            >
              {currentLength}
              {minChars ? ` (min ${minChars})` : ''}
              {maxLength ? ` / ${maxLength}` : ''}
            </span>
          )}
        </div>
      </div>
    );
  }
);

Textarea.displayName = 'Textarea';
export default Textarea;
