/**
 * src/components/Navigation.tsx
 * Production App Shell Navigation:
 * - Desktop: Collapsible left rail (240px expanded / 72px icon-only) with grouped nav
 * - Bottom Profile Card with unclipped goal and weight tags
 * - Theme Switcher (Dark / Light)
 * - Mobile Top Header + Mobile Bottom Tab Bar (5 items, 44px min touch targets)
 */

import React, { useState, useEffect } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  Sparkles,
  MessageSquare,
  Utensils,
  Dumbbell,
  TrendingUp,
  User,
  PanelLeftClose,
  PanelLeft,
  Sun,
  Moon,
  ChevronRight,
  LogOut,
} from 'lucide-react';
import { useProfile } from '../context/ProfileContext';
import { useAuth } from '../context/AuthContext';
import { useTheme, Tooltip } from '../design';

interface NavGroup {
  label?: string;
  items: {
    to: string;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    badge?: string;
  }[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Overview',
    items: [
      { to: '/dashboard', label: 'Today', icon: Sparkles },
      { to: '/coach', label: 'Coach Chat', icon: MessageSquare },
    ],
  },
  {
    label: 'Training & Fuel',
    items: [
      { to: '/nutrition', label: 'Nutrition & Macros', icon: Utensils },
      { to: '/workouts', label: 'Workout Planner', icon: Dumbbell },
      { to: '/tracker', label: 'Overload Tracker', icon: TrendingUp },
    ],
  },
  {
    label: 'Settings',
    items: [
      { to: '/profile', label: 'Athlete Profile', icon: User },
    ],
  },
];

function initialsOf(name?: string | null) {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
}

export function Sidebar() {
  const { profile } = useProfile();
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();

  // Collapsible state: default collapsed on tablet (window < 1024), expanded on desktop
  const [isCollapsed, setIsCollapsed] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('fitbot_rail_collapsed');
      if (stored !== null) return stored === 'true';
      return window.innerWidth < 1024;
    }
    return false;
  });

  useEffect(() => {
    localStorage.setItem('fitbot_rail_collapsed', String(isCollapsed));
  }, [isCollapsed]);

  const toggleRail = () => setIsCollapsed(!isCollapsed);

  return (
    <aside
      className={`hidden md:flex flex-col bg-[var(--bg-sidebar)] border-r border-[var(--border-subtle)] transition-all duration-200 select-none z-30 shrink-0 ${
        isCollapsed ? 'w-[72px]' : 'w-60'
      }`}
    >
      {/* Brand Header & Rail Toggle */}
      <div className="flex items-center justify-between p-4 border-b border-[var(--border-subtle)] min-h-[64px]">
        {!isCollapsed && (
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded-xl bg-[var(--accent-primary)] flex items-center justify-center text-[var(--text-on-accent)] shadow-xs shrink-0">
              <Dumbbell className="w-4 h-4" />
            </div>
            <div className="truncate">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-bold tracking-tight text-[var(--text-primary)]">
                  FitBot
                </span>
                <span className="text-[10px] font-bold px-1.5 py-0.2 rounded-full bg-[var(--accent-primary-subtle)] text-[var(--accent-text)] border border-[var(--accent-primary-border)]">
                  AI
                </span>
              </div>
              <p className="text-[11px] text-[var(--text-muted)] truncate">Evidence Coach</p>
            </div>
          </div>
        )}

        {isCollapsed && (
          <div className="w-full flex justify-center">
            <div className="w-8 h-8 rounded-xl bg-[var(--accent-primary)] flex items-center justify-center text-[var(--text-on-accent)] shadow-xs">
              <Dumbbell className="w-4 h-4" />
            </div>
          </div>
        )}

        <button
          type="button"
          onClick={toggleRail}
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-subtle)] transition-colors cursor-pointer"
        >
          {isCollapsed ? <PanelLeft className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation Groups */}
      <nav className="flex-1 overflow-y-auto p-3 space-y-6">
        {NAV_GROUPS.map((group, gIdx) => (
          <div key={gIdx} className="space-y-1">
            {!isCollapsed && group.label && (
              <div className="px-3 text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                {group.label}
              </div>
            )}
            {group.items.map(({ to, label, icon: Icon, badge }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/dashboard'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition-all duration-150 ${
                    isCollapsed ? 'justify-center' : ''
                  } ${
                    isActive
                      ? 'bg-[var(--accent-primary-subtle)] text-[var(--accent-text)] border border-[var(--accent-primary-border)] shadow-xs font-bold'
                      : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-subtle)]'
                  }`
                }
              >
                {({ isActive }) => {
                  const content = (
                    <>
                      <Icon
                        className={`w-4 h-4 shrink-0 transition-colors ${
                          isActive ? 'text-[var(--accent-primary)]' : 'text-[var(--text-muted)]'
                        }`}
                      />
                      {!isCollapsed && <span className="truncate">{label}</span>}
                      {!isCollapsed && badge && (
                        <span className="ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-[var(--accent-primary)] text-[var(--text-on-accent)]">
                          {badge}
                        </span>
                      )}
                    </>
                  );

                  return isCollapsed ? (
                    <Tooltip content={label} side="right">
                      <div className="flex items-center justify-center w-full">{content}</div>
                    </Tooltip>
                  ) : (
                    content
                  );
                }}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Footer: Theme Toggle & Unclipped Profile Card */}
      <div className="p-3 border-t border-[var(--border-subtle)] space-y-2">
        {/* Theme Switcher Button */}
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-subtle)] transition-colors cursor-pointer ${
            isCollapsed ? 'justify-center' : ''
          }`}
        >
          {theme === 'dark' ? (
            <Sun className="w-4 h-4 text-amber-400 shrink-0" />
          ) : (
            <Moon className="w-4 h-4 text-indigo-500 shrink-0" />
          )}
          {!isCollapsed && (
            <span>{theme === 'dark' ? 'Light Theme' : 'Dark Theme'}</span>
          )}
        </button>

        {/* Profile Card (Solves Problem #3: Unclipped, links to /profile) */}
        {!isCollapsed ? (
          <div
            onClick={() => navigate('/profile')}
            className="group flex items-center justify-between p-2.5 rounded-xl bg-[var(--bg-subtle)]/70 hover:bg-[var(--bg-subtle)] border border-[var(--border-subtle)] hover:border-[var(--border-prominent)] transition-all cursor-pointer shadow-xs"
          >
            <div className="flex items-center gap-2.5 min-w-0 pr-1">
              <div className="w-8 h-8 rounded-full bg-[var(--accent-primary-subtle)] border border-[var(--accent-primary-border)] text-[var(--accent-text)] flex items-center justify-center font-bold text-xs shrink-0">
                {initialsOf(user?.full_name)}
              </div>
              <div className="min-w-0">
                <span className="block text-xs font-bold text-[var(--text-primary)] truncate" title={user?.email}>
                  {user?.full_name || 'Athlete'}
                </span>
                <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-secondary)]">
                  <span className="capitalize truncate max-w-[80px]">
                    {profile?.goal?.replace(/_/g, ' ') || 'Hypertrophy'}
                  </span>
                  <span>·</span>
                  <span className="font-sans tabular-nums font-semibold shrink-0">
                    {profile?.weight_kg || 75} kg
                  </span>
                </div>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-[var(--text-muted)] group-hover:text-[var(--text-primary)] shrink-0 transition-transform group-hover:translate-x-0.5" />
          </div>
        ) : (
          <Tooltip content={`Profile: ${profile?.goal || 'Athlete'} · ${profile?.weight_kg || 75}kg`} side="right">
            <button
              type="button"
              onClick={() => navigate('/profile')}
              aria-label="View Profile"
              className="w-full flex justify-center p-2 rounded-xl bg-[var(--bg-subtle)] hover:bg-[var(--bg-subtle)]/80 border border-[var(--border-subtle)] cursor-pointer"
            >
              <div className="w-7 h-7 rounded-full bg-[var(--accent-primary-subtle)] text-[var(--accent-text)] flex items-center justify-center font-bold text-xs">
                {initialsOf(user?.full_name)}
              </div>
            </button>
          </Tooltip>
        )}

        {/* Logout */}
        <button
          type="button"
          onClick={() => {
            logout();
            navigate('/login', { replace: true });
          }}
          aria-label="Log out"
          title="Log out"
          className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-[var(--text-secondary)] hover:text-rose-500 hover:bg-rose-500/10 transition-colors cursor-pointer ${
            isCollapsed ? 'justify-center' : ''
          }`}
        >
          <LogOut className="w-4 h-4 shrink-0" />
          {!isCollapsed && <span>Log out</span>}
        </button>
      </div>
    </aside>
  );
}

export function MobileTopBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const getPageTitle = (path: string) => {
    switch (path) {
      case '/dashboard': return 'Today';
      case '/coach': return 'Coach Chat';
      case '/nutrition': return 'Nutrition & Macros';
      case '/workouts': return 'Workout Planner';
      case '/tracker': return 'Overload Tracker';
      case '/profile': return 'Athlete Profile';
      case '/design': return 'Design System';
      default: return 'FitBot';
    }
  };

  return (
    <header className="md:hidden sticky top-0 z-40 bg-[var(--bg-card)]/90 backdrop-blur-md border-b border-[var(--border-subtle)] px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-lg bg-[var(--accent-primary)] flex items-center justify-center text-[var(--text-on-accent)] shadow-xs">
          <Dumbbell className="w-3.5 h-3.5" />
        </div>
        <span className="text-sm font-bold text-[var(--text-primary)] tracking-tight">
          {getPageTitle(location.pathname)}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={toggleTheme}
          aria-label="Toggle theme"
          className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-subtle)] transition-colors"
        >
          {theme === 'dark' ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-indigo-500" />
          )}
        </button>

        <button
          type="button"
          onClick={() => navigate('/profile')}
          aria-label="View Profile"
          className="w-8 h-8 rounded-full bg-[var(--accent-primary-subtle)] border border-[var(--accent-primary-border)] text-[var(--accent-text)] flex items-center justify-center font-bold text-xs"
        >
          <User className="w-4 h-4" />
        </button>

        <button
          type="button"
          onClick={() => {
            logout();
            navigate('/login', { replace: true });
          }}
          aria-label="Log out"
          className="p-2 rounded-lg text-[var(--text-muted)] hover:text-rose-500 hover:bg-rose-500/10 transition-colors"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}

const MOBILE_NAV_ITEMS = [
  { to: '/dashboard', label: 'Today', icon: Sparkles },
  { to: '/coach', label: 'Coach', icon: MessageSquare },
  { to: '/nutrition', label: 'Nutrition', icon: Utensils },
  { to: '/workouts', label: 'Workouts', icon: Dumbbell },
  { to: '/tracker', label: 'Tracker', icon: TrendingUp },
];

export function MobileTabBar() {
  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-[var(--bg-card)]/95 backdrop-blur-lg border-t border-[var(--border-subtle)] px-2 py-1.5 flex justify-around items-center h-16 shadow-[var(--shadow-lg)]">
      {MOBILE_NAV_ITEMS.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/dashboard'}
          className={({ isActive }) =>
            `flex flex-col items-center justify-center min-w-[56px] min-h-[44px] py-1 px-2 rounded-xl text-[10px] font-semibold transition-all active:scale-95 ${
              isActive
                ? 'text-[var(--accent-text)]'
                : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <Icon
                className={`w-5 h-5 mb-0.5 transition-transform ${
                  isActive ? 'scale-110 text-[var(--accent-primary)]' : ''
                }`}
              />
              <span className="tracking-tight">{label}</span>
              {isActive && (
                <span className="w-1 h-1 rounded-full bg-[var(--accent-primary)] mt-0.5" />
              )}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
