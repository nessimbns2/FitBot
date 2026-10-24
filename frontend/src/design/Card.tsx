/**
 * src/design/Card.tsx & StatCard.tsx
 * Standardized elevated containers with 16-24px padding and accessible KPI displays.
 */

import React from 'react';
import { Info } from 'lucide-react';
import * as TooltipPrimitive from '@radix-ui/react-tooltip';

export interface CardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  variant?: 'default' | 'glass' | 'interactive';
  padding?: 'sm' | 'md' | 'lg' | 'none';
}


export function Card({
  title,
  subtitle,
  action,
  variant = 'default',
  padding = 'md',
  children,
  className = '',
  ...props
}: CardProps) {
  const paddingStyles = {
    none: 'p-0',
    sm: 'p-4',
    md: 'p-5 sm:p-6',
    lg: 'p-6 sm:p-8',
  };

  const variantStyles = {
    default:
      'bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-[var(--shadow-sm)] hover:border-[var(--border-prominent)]',
    glass:
      'bg-[var(--bg-card)]/80 backdrop-blur-md border border-[var(--border-subtle)] shadow-[var(--shadow-md)]',
    interactive:
      'bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-[var(--shadow-sm)] hover:border-[var(--border-prominent)] hover:shadow-[var(--shadow-md)] cursor-pointer active:scale-[0.99] transition-all duration-150',
  };

  return (
    <div
      className={`rounded-2xl transition-colors duration-150 ${variantStyles[variant]} ${paddingStyles[padding]} ${className}`}
      {...props}
    >
      {(title || subtitle || action) && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 mb-4 border-b border-[var(--border-subtle)]">
          <div>
            {title && (
              <h3 className="text-base sm:text-lg font-bold text-[var(--text-primary)] tracking-tight">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="text-xs sm:text-sm text-[var(--text-secondary)] mt-0.5 leading-relaxed">
                {subtitle}
              </p>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

export interface StatCardProps {
  label: string;
  value: React.ReactNode;
  unit?: string;
  subValue?: string;
  infoTooltip?: string;
  color?: 'accent' | 'protein' | 'carbs' | 'fat' | 'neutral';
  className?: string;
}

export function StatCard({
  label,
  value,
  unit,
  subValue,
  infoTooltip,
  color = 'neutral',
  className = '',
}: StatCardProps) {
  const colorStyles = {
    neutral: 'text-[var(--text-primary)]',
    accent: 'text-[var(--accent-text)]',
    protein: 'text-[var(--macro-protein-text)]',
    carbs: 'text-[var(--macro-carbs-text)]',
    fat: 'text-[var(--macro-fat-text)]',
  };

  const badgeBgStyles = {
    neutral: 'bg-[var(--bg-subtle)] border-[var(--border-subtle)]',
    accent: 'bg-[var(--accent-primary-subtle)] border-[var(--accent-primary-border)]',
    protein: 'bg-[var(--macro-protein-subtle)] border-[var(--macro-protein-border)]',
    carbs: 'bg-[var(--macro-carbs-subtle)] border-[var(--macro-carbs-border)]',
    fat: 'bg-[var(--macro-fat-subtle)] border-[var(--macro-fat-border)]',
  };

  return (
    <div
      className={`bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-2xl p-5 shadow-[var(--shadow-sm)] hover:border-[var(--border-prominent)] transition-colors duration-150 flex flex-col justify-between ${className}`}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          {label}
        </span>
        {infoTooltip && (
          <TooltipPrimitive.Provider delayDuration={150}>
            <TooltipPrimitive.Root>
              <TooltipPrimitive.Trigger asChild>
                <button
                  type="button"
                  aria-label={`Info about ${label}`}
                  className="text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-help p-0.5 rounded transition-colors"
                >
                  <Info className="w-3.5 h-3.5" />
                </button>
              </TooltipPrimitive.Trigger>
              <TooltipPrimitive.Portal>
                <TooltipPrimitive.Content
                  side="top"
                  align="end"
                  className="z-50 max-w-xs px-3 py-1.5 text-xs text-[var(--text-primary)] bg-[var(--bg-card)] border border-[var(--border-prominent)] rounded-xl shadow-[var(--shadow-lg)] leading-relaxed animate-in fade-in-0 zoom-in-95"
                >
                  {infoTooltip}
                  <TooltipPrimitive.Arrow className="fill-[var(--border-prominent)]" />
                </TooltipPrimitive.Content>
              </TooltipPrimitive.Portal>
            </TooltipPrimitive.Root>
          </TooltipPrimitive.Provider>
        )}
      </div>

      <div className="flex items-baseline gap-1.5 my-1">
        <span
          className={`text-2xl sm:text-3xl font-black font-sans tabular-nums tracking-tight ${colorStyles[color]}`}
        >
          {value}
        </span>
        {unit && (
          <span className="text-xs sm:text-sm font-medium text-[var(--text-secondary)] font-sans">
            {unit}
          </span>
        )}
      </div>

      {subValue && (
        <div className="mt-2 pt-2 border-t border-[var(--border-subtle)] flex items-center justify-between text-xs text-[var(--text-muted)] font-sans">
          <span>{subValue}</span>
        </div>
      )}
    </div>
  );
}
