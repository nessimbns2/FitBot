/**
 * src/design/SegmentedControl.tsx & Stepper.tsx
 * Accessible toggles and numeric steppers with 40-44px touch targets.
 */

import React, { useRef } from 'react';
import { Minus, Plus } from 'lucide-react';

export interface SegmentedOption<T extends string | number> {
  value: T;
  label: React.ReactNode;
  icon?: React.ReactNode;
  badge?: React.ReactNode;
}

export interface SegmentedControlProps<T extends string | number> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  size?: 'sm' | 'md';
  className?: string;
  name?: string;
}

export function SegmentedControl<T extends string | number>({
  options,
  value,
  onChange,
  size = 'md',
  className = '',
  name,
}: SegmentedControlProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    let nextIndex = index;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      nextIndex = (index + 1) % options.length;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      nextIndex = (index - 1 + options.length) % options.length;
    }

    if (nextIndex !== index) {
      e.preventDefault();
      onChange(options[nextIndex].value);
      const buttons = containerRef.current?.querySelectorAll<HTMLButtonElement>('button[role="radio"]');
      buttons?.[nextIndex]?.focus();
    }
  };

  const sizeClasses = {
    sm: 'p-0.5 text-xs min-h-[36px]',
    md: 'p-1 text-xs sm:text-sm min-h-[44px]',
  };

  const itemSizeClasses = {
    sm: 'px-2.5 py-1 min-h-[32px]',
    md: 'px-3.5 py-2 min-h-[38px]',
  };

  return (
    <div
      ref={containerRef}
      role="radiogroup"
      aria-label={name || 'Segmented control'}
      className={`inline-flex items-center bg-[var(--bg-subtle)] border border-[var(--border-subtle)] rounded-xl gap-1 select-none ${sizeClasses[size]} ${className}`}
    >
      {options.map((opt, idx) => {
        const isSelected = opt.value === value;
        return (
          <button
            key={String(opt.value)}
            type="button"
            role="radio"
            aria-checked={isSelected}
            tabIndex={isSelected ? 0 : -1}
            onClick={() => onChange(opt.value)}
            onKeyDown={(e) => handleKeyDown(e, idx)}
            className={`flex items-center justify-center gap-1.5 font-medium rounded-lg transition-all duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focused)] ${
              itemSizeClasses[size]
            } ${
              isSelected
                ? 'bg-[var(--bg-card)] text-[var(--text-primary)] shadow-[var(--shadow-sm)] border border-[var(--border-prominent)]'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)]/50'
            }`}
          >
            {opt.icon && <span className="shrink-0">{opt.icon}</span>}
            <span>{opt.label}</span>
            {opt.badge && <span className="ml-1 shrink-0">{opt.badge}</span>}
          </button>
        );
      })}
    </div>
  );
}

export interface StepperProps {
  value: number;
  onChange: (val: number) => void;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  className?: string;
  disabled?: boolean;
}

export function Stepper({
  value,
  onChange,
  min = 0,
  max = 999,
  step = 1,
  unit,
  className = '',
  disabled = false,
}: StepperProps) {
  const handleDecrement = () => {
    const next = Math.max(min, Number((value - step).toFixed(2)));
    onChange(next);
  };

  const handleIncrement = () => {
    const next = Math.min(max, Number((value + step).toFixed(2)));
    onChange(next);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    if (!isNaN(val)) {
      onChange(Math.max(min, Math.min(max, val)));
    }
  };

  return (
    <div
      className={`inline-flex items-center bg-[var(--bg-subtle)] border border-[var(--border-subtle)] rounded-xl p-1 gap-1 ${className}`}
    >
      <button
        type="button"
        disabled={disabled || value <= min}
        onClick={handleDecrement}
        aria-label="Decrease value"
        className="w-9 h-9 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center bg-[var(--bg-card)] text-[var(--text-primary)] border border-[var(--border-subtle)] hover:bg-[var(--bg-card-hover)] active:scale-95 disabled:opacity-40 disabled:pointer-events-none transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focused)]"
      >
        <Minus className="w-3.5 h-3.5" />
      </button>

      <div className="flex items-center justify-center px-2 min-w-[56px]">
        <input
          type="number"
          step={step}
          min={min}
          max={max}
          value={value}
          onChange={handleInputChange}
          disabled={disabled}
          className="w-14 text-center bg-transparent text-sm font-sans tabular-nums font-bold text-[var(--text-primary)] focus:outline-none"
        />
        {unit && (
          <span className="text-xs text-[var(--text-muted)] font-sans ml-0.5">
            {unit}
          </span>
        )}
      </div>

      <button
        type="button"
        disabled={disabled || value >= max}
        onClick={handleIncrement}
        aria-label="Increase value"
        className="w-9 h-9 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center bg-[var(--bg-card)] text-[var(--text-primary)] border border-[var(--border-subtle)] hover:bg-[var(--bg-card-hover)] active:scale-95 disabled:opacity-40 disabled:pointer-events-none transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focused)]"
      >
        <Plus className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
