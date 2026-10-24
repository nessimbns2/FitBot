/**
 * src/design/Badge.tsx
 * Semantic tags and chips matching macro and functional status tokens.
 */

import React from 'react';
import { X } from 'lucide-react';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'neutral' | 'accent' | 'protein' | 'carbs' | 'fat' | 'warning' | 'success' | 'danger';
  size?: 'sm' | 'md';
  icon?: React.ReactNode;
  onRemove?: () => void;
}

export function Badge({
  children,
  variant = 'neutral',
  size = 'md',
  icon,
  onRemove,
  className = '',
  ...props
}: BadgeProps) {
  const sizeStyles = {
    sm: 'text-[10px] px-2 py-0.5 gap-1 min-h-[22px]',
    md: 'text-xs px-2.5 py-1 gap-1.5 min-h-[26px]',
  };

  const variantStyles = {
    neutral:
      'bg-[var(--bg-subtle)] text-[var(--text-secondary)] border border-[var(--border-subtle)]',
    accent:
      'bg-[var(--accent-primary-subtle)] text-[var(--accent-text)] border border-[var(--accent-primary-border)] font-semibold',
    protein:
      'bg-[var(--macro-protein-subtle)] text-[var(--macro-protein-text)] border border-[var(--macro-protein-border)] font-semibold',
    carbs:
      'bg-[var(--macro-carbs-subtle)] text-[var(--macro-carbs-text)] border border-[var(--macro-carbs-border)] font-semibold',
    fat:
      'bg-[var(--macro-fat-subtle)] text-[var(--macro-fat-text)] border border-[var(--macro-fat-border)] font-semibold',
    warning:
      'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30 font-semibold',
    success:
      'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 font-semibold',
    danger:
      'bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/30 font-semibold',
  };

  return (
    <span
      className={`inline-flex items-center font-medium rounded-lg select-none whitespace-nowrap transition-colors ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      <span>{children}</span>
      {onRemove && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          aria-label="Remove badge"
          className="hover:opacity-75 p-0.5 rounded cursor-pointer"
        >
          <X className="w-3 h-3" />
        </button>
      )}
    </span>
  );
}
