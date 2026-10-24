/**
 * src/design/ProgressRing.tsx & PageHeader.tsx
 * Visual calorie/macro gauge and standardized page header shell.
 */

import React from 'react';

export interface MacroRingSegment {
  label: string;
  value: number; // e.g. grams or calories
  color: string; // CSS color string or var
  percent: number; // 0 to 100
}

export interface ProgressRingProps {
  size?: number;
  strokeWidth?: number;
  segments?: MacroRingSegment[];
  centerLabel?: React.ReactNode;
  centerValue?: React.ReactNode;
  centerUnit?: React.ReactNode;
  className?: string;
}

export function ProgressRing({
  size = 200,
  strokeWidth = 14,
  segments = [],
  centerLabel,
  centerValue,
  centerUnit,
  className = '',
}: ProgressRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  // Compute stroke-dasharray and stroke-dashoffset for segments
  let accumulatedPercent = 0;

  return (
    <div
      style={{ width: size, height: size }}
      className={`relative inline-flex items-center justify-center select-none ${className}`}
    >
      <svg width={size} height={size} className="transform -rotate-90">
        {/* Background Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--bg-subtle)"
          strokeWidth={strokeWidth}
        />

        {/* Dynamic Segments */}
        {segments.map((seg, idx) => {
          const strokeDasharray = `${(seg.percent / 100) * circumference} ${circumference}`;
          const strokeDashoffset = -((accumulatedPercent / 100) * circumference);
          accumulatedPercent += seg.percent;

          return (
            <circle
              key={idx}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={seg.color}
              strokeWidth={strokeWidth}
              strokeDasharray={strokeDasharray}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              className="transition-all duration-500 ease-out"
            />
          );
        })}
      </svg>

      {/* Centered KPI Display */}
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-4">
        {centerLabel && (
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
            {centerLabel}
          </span>
        )}
        {centerValue && (
          <span className="text-3xl sm:text-4xl font-black font-sans tabular-nums text-[var(--text-primary)] tracking-tight my-0.5">
            {centerValue}
          </span>
        )}
        {centerUnit && (
          <span className="text-xs font-semibold text-[var(--text-secondary)] font-sans">
            {centerUnit}
          </span>
        )}
      </div>
    </div>
  );
}

export interface PageHeaderProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  actionSlot?: React.ReactNode;
  badge?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  description,
  actionSlot,
  badge,
  className = '',
}: PageHeaderProps) {
  return (
    <div
      className={`flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 mb-8 border-b border-[var(--border-subtle)] ${className}`}
    >
      <div>
        <div className="flex items-center gap-2.5">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-[var(--text-primary)] tracking-tight">
            {title}
          </h1>
          {badge && <span className="shrink-0">{badge}</span>}
        </div>
        {description && (
          <p className="text-xs sm:text-sm text-[var(--text-secondary)] mt-1.5 max-w-2xl leading-relaxed">
            {description}
          </p>
        )}
      </div>

      {actionSlot && <div className="shrink-0 flex items-center gap-3">{actionSlot}</div>}
    </div>
  );
}
