/**
 * src/design/Drawer.tsx & Dialog.tsx
 * Accessible overlay primitives with focus trapping, backdrop blur, and smooth entrance.
 */

import React from 'react';
import * as RadixDialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';

export interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  position?: 'right' | 'bottom';
  size?: 'sm' | 'md' | 'lg';
}

export function Drawer({
  isOpen,
  onClose,
  title,
  description,
  children,
  position = 'right',
  size = 'md',
}: DrawerProps) {
  const sizeStyles = {
    sm: 'max-w-md',
    md: 'max-w-xl',
    lg: 'max-w-2xl',
  };

  const positionStyles = {
    right:
      'top-0 right-0 h-full w-full sm:w-auto border-l border-[var(--border-prominent)] animate-in slide-in-from-right duration-250',
    bottom:
      'bottom-0 left-0 right-0 max-h-[85vh] rounded-t-3xl border-t border-[var(--border-prominent)] animate-in slide-in-from-bottom duration-250',
  };

  return (
    <RadixDialog.Root open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-50 bg-[var(--bg-overlay)] backdrop-blur-xs animate-in fade-in-0 duration-200" />
        <RadixDialog.Content
          className={`fixed z-50 bg-[var(--bg-card)] shadow-[var(--shadow-xl)] flex flex-col focus:outline-none ${positionStyles[position]} ${sizeStyles[size]}`}
        >
          <div className="flex items-center justify-between p-5 sm:p-6 border-b border-[var(--border-subtle)] shrink-0">
            <div>
              <RadixDialog.Title className="text-lg font-bold text-[var(--text-primary)] tracking-tight">
                {title}
              </RadixDialog.Title>
              {description && (
                <RadixDialog.Description className="text-xs text-[var(--text-secondary)] mt-0.5 leading-relaxed">
                  {description}
                </RadixDialog.Description>
              )}
            </div>
            <RadixDialog.Close asChild>
              <button
                type="button"
                aria-label="Close drawer"
                className="w-9 h-9 rounded-xl flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focused)]"
              >
                <X className="w-5 h-5" />
              </button>
            </RadixDialog.Close>
          </div>

          <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6">
            {children}
          </div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

export interface DialogProps {
  isOpen: boolean;
  onClose: () => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg';
}

export function Dialog({
  isOpen,
  onClose,
  title,
  description,
  children,
  maxWidth = 'md',
}: DialogProps) {
  const maxWStyles = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
  };

  return (
    <RadixDialog.Root open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-50 bg-[var(--bg-overlay)] backdrop-blur-xs animate-in fade-in-0 duration-200" />
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <RadixDialog.Content
            className={`w-full bg-[var(--bg-card)] border border-[var(--border-prominent)] rounded-2xl shadow-[var(--shadow-xl)] flex flex-col overflow-hidden focus:outline-none animate-in fade-in-0 zoom-in-95 duration-200 ${maxWStyles[maxWidth]}`}
          >
            <div className="flex items-center justify-between p-5 sm:p-6 border-b border-[var(--border-subtle)] shrink-0">
              <div>
                <RadixDialog.Title className="text-lg font-bold text-[var(--text-primary)] tracking-tight">
                  {title}
                </RadixDialog.Title>
                {description && (
                  <RadixDialog.Description className="text-xs text-[var(--text-secondary)] mt-0.5 leading-relaxed">
                    {description}
                  </RadixDialog.Description>
                )}
              </div>
              <RadixDialog.Close asChild>
                <button
                  type="button"
                  aria-label="Close dialog"
                  className="w-9 h-9 rounded-xl flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focused)]"
                >
                  <X className="w-5 h-5" />
                </button>
              </RadixDialog.Close>
            </div>

            <div className="p-5 sm:p-6 overflow-y-auto max-h-[75vh]">
              {children}
            </div>
          </RadixDialog.Content>
        </div>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
