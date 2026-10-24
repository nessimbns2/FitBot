/**
 * src/design/Skeleton.tsx, EmptyState.tsx & ErrorState.tsx
 * Resilient UI states for loading, zero data, and API failure recovery.
 */

import React from 'react';
import { AlertCircle, RefreshCw, FolderSearch } from 'lucide-react';
import { Button } from './Button';

export interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'card' | 'circular' | 'rect';
  width?: string | number;
  height?: string | number;
}

export function Skeleton({
  className = '',
  variant = 'rect',
  width,
  height,
}: SkeletonProps) {
  const variantStyles = {
    text: 'rounded-md h-4 w-3/4',
    card: 'rounded-2xl h-40 w-full',
    circular: 'rounded-full h-12 w-12',
    rect: 'rounded-xl h-10 w-full',
  };

  const style: React.CSSProperties = {
    width: width,
    height: height,
  };

  return (
    <div
      style={style}
      className={`animate-pulse bg-[var(--bg-subtle)] border border-[var(--border-subtle)]/50 ${variantStyles[variant]} ${className}`}
    />
  );
}

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
    icon?: React.ReactNode;
  };
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className = '',
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center p-8 sm:p-12 rounded-2xl border border-dashed border-[var(--border-prominent)] bg-[var(--bg-subtle)]/30 ${className}`}
    >
      <div className="w-12 h-12 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] flex items-center justify-center text-[var(--accent-text)] mb-4 shadow-xs">
        {icon || <FolderSearch className="w-6 h-6" />}
      </div>
      <h4 className="text-base font-bold text-[var(--text-primary)] tracking-tight mb-1">
        {title}
      </h4>
      <p className="text-xs sm:text-sm text-[var(--text-secondary)] max-w-sm mb-6 leading-relaxed">
        {description}
      </p>
      {action && (
        <Button variant="primary" size="md" onClick={action.onClick} leftIcon={action.icon}>
          {action.label}
        </Button>
      )}
    </div>
  );
}

export interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = 'Unable to Load Data',
  message,
  onRetry,
  className = '',
}: ErrorStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center p-8 sm:p-10 rounded-2xl border border-rose-500/20 bg-rose-500/5 ${className}`}
    >
      <div className="w-12 h-12 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-500 mb-4 shadow-xs">
        <AlertCircle className="w-6 h-6" />
      </div>
      <h4 className="text-base font-bold text-[var(--text-primary)] tracking-tight mb-1">
        {title}
      </h4>
      <p className="text-xs sm:text-sm text-[var(--text-secondary)] max-w-md mb-6 leading-relaxed">
        {message}
      </p>
      {onRetry && (
        <Button variant="secondary" size="md" onClick={onRetry} leftIcon={<RefreshCw className="w-4 h-4" />}>
          Retry Request
        </Button>
      )}
    </div>
  );
}
