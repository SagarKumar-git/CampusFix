/**
 * CampusFix Button Component
 *
 * Implements:
 * - WCAG 2.1 AA contrast compliance
 * - High-visibility focus indicators
 * - Accessible loading spinner state with aria-busy="true"
 * - Semantic variants: primary, secondary, danger, ghost
 */

import React, { forwardRef } from 'react';
import { SpinnerIcon } from './icons';

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  loadingText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      loadingText,
      leftIcon,
      rightIcon,
      disabled,
      className = '',
      type = 'button',
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || isLoading;

    // Base layout & keyboard focus rings
    const baseClasses =
      'inline-flex items-center justify-center font-medium rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 select-none disabled:cursor-not-allowed';

    // Size variants
    const sizeClasses = {
      sm: 'px-3 py-1.5 text-xs min-h-[36px]',
      md: 'px-4 py-2 text-sm min-h-[44px]',
      lg: 'px-5 py-2.5 text-base min-h-[48px]',
    }[size];

    // Color variants
    const variantClasses = {
      primary:
        'bg-brand-600 text-white hover:bg-brand-700 active:bg-brand-800 focus-visible:ring-brand-500 disabled:bg-neutral-200 disabled:text-neutral-400 shadow-sm',
      secondary:
        'bg-white text-neutral-700 border border-neutral-300 hover:bg-neutral-50 active:bg-neutral-100 focus-visible:ring-brand-500 disabled:bg-neutral-100 disabled:text-neutral-400 disabled:border-neutral-200 shadow-sm',
      danger:
        'bg-red-600 text-white hover:bg-red-700 active:bg-red-800 focus-visible:ring-red-500 disabled:bg-neutral-200 disabled:text-neutral-400 shadow-sm',
      ghost:
        'bg-transparent text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100 active:bg-neutral-200 focus-visible:ring-brand-500 disabled:text-neutral-300 disabled:hover:bg-transparent',
    }[variant];

    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        aria-busy={isLoading ? 'true' : undefined}
        className={`${baseClasses} ${sizeClasses} ${variantClasses} ${className}`}
        {...props}
      >
        {isLoading ? (
          <>
            <SpinnerIcon className="w-4 h-4 mr-2" />
            <span>{loadingText || children}</span>
          </>
        ) : (
          <>
            {leftIcon && <span className="mr-2 inline-flex" aria-hidden="true">{leftIcon}</span>}
            <span>{children}</span>
            {rightIcon && <span className="ml-2 inline-flex" aria-hidden="true">{rightIcon}</span>}
          </>
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';
export default Button;
