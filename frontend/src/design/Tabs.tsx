/**
 * src/design/Tabs.tsx
 * Accessible tabs built on Radix UI Tabs primitive.
 */

import React from 'react';
import * as RadixTabs from '@radix-ui/react-tabs';

export interface TabItem {
  id: string;
  label: React.ReactNode;
  icon?: React.ReactNode;
  badge?: React.ReactNode;
}

export interface TabsProps {
  tabs: TabItem[];
  value: string;
  onChange: (value: string) => void;
  children?: React.ReactNode;
  className?: string;
}

export function Tabs({
  tabs,
  value,
  onChange,
  children,
  className = '',
}: TabsProps) {
  return (
    <RadixTabs.Root value={value} onValueChange={onChange} className={`w-full ${className}`}>
      <RadixTabs.List className="flex items-center gap-2 border-b border-[var(--border-subtle)] pb-px overflow-x-auto select-none">
        {tabs.map((tab) => {
          const isActive = tab.id === value;
          return (
            <RadixTabs.Trigger
              key={tab.id}
              value={tab.id}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs sm:text-sm font-semibold rounded-t-xl transition-all cursor-pointer relative focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focused)] ${
                isActive
                  ? 'text-[var(--accent-text)]'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)]'
              }`}
            >
              {tab.icon && <span className="shrink-0">{tab.icon}</span>}
              <span>{tab.label}</span>
              {tab.badge && <span className="shrink-0">{tab.badge}</span>}
              {isActive && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--accent-primary)] rounded-full" />
              )}
            </RadixTabs.Trigger>
          );
        })}
      </RadixTabs.List>
      {children}
    </RadixTabs.Root>
  );
}

export const TabContent = RadixTabs.Content;
