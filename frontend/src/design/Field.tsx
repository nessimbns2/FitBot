/**
 * src/design/Field.tsx & Select.tsx
 * Accessible form controls with visible labels and clear hierarchy.
 */

import React, { useId } from 'react';
import { ChevronDown, AlertCircle } from 'lucide-react';

export interface FieldProps {
  label: string;
  helper?: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
  htmlFor?: string;
}

export function Field({
  label,
  helper,
  error,
  required,
  children,
  className = '',
  htmlFor,
}: FieldProps) {
  const generatedId = useId();
  const id = htmlFor || generatedId;

  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <div className="flex items-baseline justify-between gap-2">
        <label
          htmlFor={id}
          className="text-xs sm:text-sm font-semibold text-[var(--text-primary)] select-none flex items-center gap-1"
        >
          <span>{label}</span>
          {required && <span className="text-rose-500 font-bold">*</span>}
        </label>
      </div>

      {helper && (
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          {helper}
        </p>
      )}

      <div className="relative mt-0.5">{children}</div>

      {error && (
        <p className="text-xs text-rose-500 flex items-center gap-1 mt-0.5 font-medium">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{error}</span>
        </p>
      )}
    </div>
  );
}

export interface SelectOption {
  value: string | number;
  label: string;
  hint?: string;
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  options: SelectOption[];
  helper?: string;
  error?: string;
  containerClassName?: string;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      label,
      options,
      helper,
      error,
      containerClassName = '',
      className = '',
      id: customId,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const id = customId || generatedId;

    return (
      <Field label={label} helper={helper} error={error} htmlFor={id} className={containerClassName}>
        <div className="relative">
          <select
            ref={ref}
            id={id}
            className={`w-full appearance-none bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-primary)] text-sm rounded-xl px-3.5 py-2.5 pr-10 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)] focus:border-transparent transition-all shadow-xs cursor-pointer ${
              error ? 'border-rose-500 focus:ring-rose-500' : ''
            } ${className}`}
            {...props}
          >
            {options.map((opt) => (
              <option
                key={String(opt.value)}
                value={opt.value}
                className="bg-[var(--bg-card)] text-[var(--text-primary)] py-1"
              >
                {opt.label} {opt.hint ? `(${opt.hint})` : ''}
              </option>
            ))}
          </select>
          <ChevronDown className="w-4 h-4 text-[var(--text-muted)] absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
        </div>
      </Field>
    );
  }
);

Select.displayName = 'Select';
