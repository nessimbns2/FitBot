/**
 * src/design/Button.tsx & IconButton.tsx
 * Accessible buttons with visible focus rings, 44px min touch targets on mobile, and loading state.
 */

import React from 'react';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'xs' | 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      leftIcon,
      rightIcon,
      className = '',
      disabled,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center font-medium rounded-xl transition-all duration-150 select-none cursor-pointer disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focused)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-app)] active:scale-[0.98]';

    const sizeStyles = {
      xs: 'text-xs px-2.5 py-1 min-h-[28px] gap-1',
      sm: 'text-xs px-3 py-1.5 min-h-[36px] sm:min-h-[32px] gap-1.5',
      md: 'text-sm px-4 py-2 min-h-[44px] sm:min-h-[40px] gap-2',
      lg: 'text-base px-5 py-2.5 min-h-[48px] gap-2.5 shadow-sm',
    };


    const variantStyles = {
      primary:
        'bg-[var(--accent-primary)] text-white hover:bg-[var(--accent-primary-hover)] shadow-sm hover:shadow active:bg-[var(--accent-primary-hover)]',
      secondary:
        'bg-[var(--bg-card)] text-[var(--text-primary)] border border-[var(--border-subtle)] hover:bg-[var(--bg-card-hover)] hover:border-[var(--border-prominent)] shadow-xs',
      ghost:
        'bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)]',
      danger:
        'bg-rose-600 text-white hover:bg-rose-700 active:bg-rose-800 shadow-xs',
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
        {...props}
      >
        {isLoading ? (
          <Loader2 className="w-4 h-4 animate-spin text-current" />
        ) : (
          leftIcon && <span className="shrink-0">{leftIcon}</span>
        )}
        <span>{children}</span>
        {!isLoading && rightIcon && <span className="shrink-0">{rightIcon}</span>}
      </button>
    );
  }
);

Button.displayName = 'Button';

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: React.ReactNode;
  'aria-label': string;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
}

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  (
    {
      icon,
      'aria-label': ariaLabel,
      variant = 'ghost',
      size = 'md',
      className = '',
      ...props
    },
    ref
  ) => {
    const sizeStyles = {
      sm: 'w-9 h-9 sm:w-8 sm:h-8 p-1.5 text-xs',
      md: 'w-11 h-11 sm:w-10 sm:h-10 p-2 text-sm',
      lg: 'w-12 h-12 p-2.5 text-base',
    };

    const variantStyles = {
      primary:
        'bg-[var(--accent-primary)] text-white hover:bg-[var(--accent-primary-hover)] shadow-sm',
      secondary:
        'bg-[var(--bg-card)] text-[var(--text-primary)] border border-[var(--border-subtle)] hover:bg-[var(--bg-card-hover)] hover:border-[var(--border-prominent)]',
      ghost:
        'bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)]',
      danger:
        'bg-rose-600/10 text-rose-500 hover:bg-rose-600/20 active:bg-rose-600/30',
    };

    return (
      <button
        ref={ref}
        aria-label={ariaLabel}
        className={`inline-flex items-center justify-center rounded-xl transition-all duration-150 select-none cursor-pointer disabled:opacity-40 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focused)] active:scale-95 ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
        {...props}
      >
        {icon}
      </button>
    );
  }
);

IconButton.displayName = 'IconButton';
