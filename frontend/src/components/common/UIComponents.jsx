/**
 * src/components/common/UIComponents.jsx
 * Spacious, accessible, refined modern app primitives.
 */

import React from 'react';
import { Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';

export function Button({
  children,
  variant = 'primary', // 'primary', 'secondary', 'accent', 'danger', 'ghost'
  size = 'md',        // 'sm', 'md', 'lg'
  isLoading = false,
  disabled = false,
  className = '',
  ...props
}) {
  const baseStyles =
    "inline-flex items-center justify-center font-medium rounded-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:ring-offset-1 focus:ring-offset-[#090a0f] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer select-none active:scale-[0.98]";

  const sizeStyles = {
    sm: "px-3 py-1.5 text-xs gap-1.5 h-8",
    md: "px-4 py-2 text-xs font-semibold gap-2 h-10",
    lg: "px-6 py-3 text-sm font-semibold gap-2.5 h-12",
  }[size];

  const variantStyles = {
    primary:
      "bg-blue-600 hover:bg-blue-500 text-white shadow-sm shadow-blue-600/20 border border-blue-500/30",
    accent:
      "bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm shadow-emerald-600/20 border border-emerald-500/30",
    secondary:
      "bg-[#141824] hover:bg-[#1a2030] text-slate-200 border border-[#22293e]",
    danger:
      "bg-rose-950/40 hover:bg-rose-950/60 text-rose-300 border border-rose-800/40",
    ghost:
      "bg-transparent hover:bg-[#141824] text-slate-400 hover:text-slate-100",
  }[variant];

  return (
    <button
      className={`${baseStyles} ${sizeStyles} ${variantStyles} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && <Loader2 className="w-3.5 h-3.5 animate-spin-smooth" />}
      {children}
    </button>
  );
}

export function Card({ children, title, subtitle, action, className = '' }) {
  return (
    <div
      className={`bg-[#10131d] border border-[#1b2133] rounded-2xl p-6 transition-all duration-200 hover:border-[#232b42] ${className}`}
    >
      {(title || action) && (
        <div className="flex items-center justify-between pb-4 mb-5 border-b border-[#181e30]">
          <div>
            {title && (
              <h3 className="text-sm font-semibold tracking-tight text-slate-100">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="text-xs text-slate-400 mt-1">{subtitle}</p>
            )}
          </div>
          {action && <div className="flex items-center gap-2">{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

export function Field({ label, error, helper, required, children, className = '' }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {label && (
        <label className="block text-xs font-medium text-slate-300">
          {label} {required && <span className="text-blue-400">*</span>}
        </label>
      )}
      {children}
      {helper && !error && <p className="text-[11px] text-slate-500">{helper}</p>}
      {error && <p className="text-[11px] text-rose-400">{error}</p>}
    </div>
  );
}

export function Input({ className = '', ...props }) {
  return (
    <input
      className={`w-full bg-[#0a0c13] border border-[#1f263b] focus:border-blue-500/80 focus:ring-2 focus:ring-blue-500/20 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-600 outline-none transition-all duration-150 tabular-nums ${className}`}
      {...props}
    />
  );
}

export function Select({ options = [], className = '', ...props }) {
  return (
    <select
      className={`w-full bg-[#0a0c13] border border-[#1f263b] focus:border-blue-500/80 focus:ring-2 focus:ring-blue-500/20 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 outline-none transition-all duration-150 cursor-pointer ${className}`}
      {...props}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value} className="bg-[#10131d] text-slate-200">
          {opt.label}
        </option>
      ))}
    </select>
  );
}

export function Badge({ children, variant = 'neutral', className = '' }) {
  const styles = {
    neutral: 'bg-[#141926] text-slate-300 border border-[#20273d]',
    accent: 'bg-blue-950/40 text-blue-400 border border-blue-800/40',
    success: 'bg-emerald-950/40 text-emerald-400 border border-emerald-800/40',
    warning: 'bg-amber-950/40 text-amber-400 border border-amber-800/40',
    danger: 'bg-rose-950/40 text-rose-400 border border-rose-800/40',
  }[variant];

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium tracking-tight ${styles} ${className}`}
    >
      {children}
    </span>
  );
}

export function Spinner({ size = 'md' }) {
  const sizes = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-8 h-8' }[size];
  return (
    <div className="flex items-center justify-center p-6">
      <Loader2 className={`${sizes} animate-spin-smooth text-blue-500`} />
    </div>
  );
}

export function ErrorBanner({ message, onRetry }) {
  return (
    <div className="bg-rose-950/30 border border-rose-900/40 rounded-xl p-4 flex items-center justify-between text-xs text-rose-300">
      <div className="flex items-center gap-3">
        <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-400" />
        <span>{message}</span>
      </div>
      {onRetry && (
        <Button size="sm" variant="danger" onClick={onRetry}>
          Try Again
        </Button>
      )}
    </div>
  );
}

export function Toast({ type = 'success', message, onClose }) {
  return (
    <div className="fixed bottom-6 right-6 z-50 animate-slide-up flex items-center gap-3 bg-[#131722] border border-[#242c44] px-4 py-3 rounded-xl shadow-2xl text-xs text-slate-100">
      {type === 'success' ? (
        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
      ) : (
        <AlertCircle className="w-4 h-4 text-rose-400" />
      )}
      <span className="font-medium">{message}</span>
      {onClose && (
        <button
          onClick={onClose}
          className="ml-2 text-slate-400 hover:text-white cursor-pointer"
        >
          ✕
        </button>
      )}
    </div>
  );
}
