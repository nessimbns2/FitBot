/**
 * src/design/Tooltip.tsx & Toast.tsx
 * Accessible tooltips and status toasts.
 */

import React, { useEffect } from 'react';
import * as RadixTooltip from '@radix-ui/react-tooltip';
import { CheckCircle2, AlertTriangle, AlertCircle, Info, X } from 'lucide-react';

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: 'top' | 'right' | 'bottom' | 'left';
  align?: 'start' | 'center' | 'end';
}

export function Tooltip({
  content,
  children,
  side = 'top',
  align = 'center',
}: TooltipProps) {
  return (
    <RadixTooltip.Provider delayDuration={150}>
      <RadixTooltip.Root>
        <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
        <RadixTooltip.Portal>
          <RadixTooltip.Content
            side={side}
            align={align}
            className="z-50 max-w-xs px-3 py-1.5 text-xs text-[var(--text-primary)] bg-[var(--bg-card)] border border-[var(--border-prominent)] rounded-xl shadow-[var(--shadow-lg)] leading-relaxed animate-in fade-in-0 zoom-in-95"
          >
            {content}
            <RadixTooltip.Arrow className="fill-[var(--border-prominent)]" />
          </RadixTooltip.Content>
        </RadixTooltip.Portal>
      </RadixTooltip.Root>
    </RadixTooltip.Provider>
  );
}

export interface ToastProps {
  type?: 'success' | 'error' | 'warning' | 'info';
  message: React.ReactNode;
  onClose: () => void;
  duration?: number;
}

export function Toast({
  type = 'info',
  message,
  onClose,
  duration = 4000,
}: ToastProps) {
  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(onClose, duration);
      return () => clearTimeout(timer);
    }
  }, [duration, onClose]);

  const typeStyles = {
    success: {
      border: 'border-emerald-500/40',
      icon: <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />,
      bg: 'bg-[var(--bg-card)]',
    },
    error: {
      border: 'border-rose-500/40',
      icon: <AlertCircle className="w-5 h-5 text-rose-500 shrink-0" />,
      bg: 'bg-[var(--bg-card)]',
    },
    warning: {
      border: 'border-amber-500/40',
      icon: <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0" />,
      bg: 'bg-[var(--bg-card)]',
    },
    info: {
      border: 'border-[var(--border-focused)]',
      icon: <Info className="w-5 h-5 text-[var(--accent-primary)] shrink-0" />,
      bg: 'bg-[var(--bg-card)]',
    },
  };

  const current = typeStyles[type];

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed bottom-20 md:bottom-8 right-6 z-50 flex items-center gap-3 p-4 max-w-md rounded-2xl border ${current.border} ${current.bg} shadow-[var(--shadow-xl)] animate-in slide-in-from-bottom-5 duration-200`}
    >
      {current.icon}
      <div className="text-xs sm:text-sm font-medium text-[var(--text-primary)] leading-snug">
        {message}
      </div>
      <button
        type="button"
        onClick={onClose}
        aria-label="Dismiss notification"
        className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 rounded-lg transition-colors ml-auto cursor-pointer"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
