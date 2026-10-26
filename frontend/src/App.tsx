/**
 * src/App.tsx
 * Top-level application shell: ThemeProvider, AuthProvider, Router.
 * Public routes: /login, /register. Everything else requires an authenticated account
 * and is rendered inside the app shell with the user's ProfileProvider.
 */

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { ThemeProvider } from './design';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ProfileProvider } from './context/ProfileContext';
import { Sidebar, MobileTabBar, MobileTopBar } from './components/Navigation';
import { TodayView } from './views/TodayView';
import { ChatView } from './views/ChatView';
import { NutritionView } from './views/NutritionView';
import { WorkoutsView } from './views/WorkoutsView';
import { TrackerView } from './views/TrackerView';
import { ProfileView } from './views/ProfileView';
import { DesignGalleryView } from './views/DesignGalleryView';
import { LoginView, RegisterView } from './views/AuthViews';

function FullScreenLoader() {
  return (
    <div className="h-screen w-screen flex items-center justify-center bg-[var(--bg-app)] text-[var(--text-secondary)]">
      <Loader2 className="w-6 h-6 animate-spin" aria-label="Loading" />
    </div>
  );
}

/** Redirects anonymous visitors to /login, remembering where they wanted to go. */
function RequireAuth() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();
  if (isLoading) return <FullScreenLoader />;
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

/** Authenticated app shell: navigation + routed content, scoped to the user's profile. */
function AppShell() {
  const { user } = useAuth();
  return (
    // key: remount (and refetch everything) when another account logs in
    <ProfileProvider key={user?.id}>
      <div className="flex h-screen w-screen overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)]">
        {/* Desktop Left Sidebar / Rail */}
        <Sidebar />

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col h-full overflow-hidden relative pb-16 md:pb-0">
          {/* Mobile Top Header */}
          <MobileTopBar />
          <Outlet />
        </main>

        {/* Mobile Bottom Navigation Bar */}
        <MobileTabBar />
      </div>
    </ProfileProvider>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginView />} />
            <Route path="/register" element={<RegisterView />} />

            <Route element={<RequireAuth />}>
              <Route element={<AppShell />}>
                {/* Home route '/' = "Today" dashboard */}
                <Route path="/" element={<TodayView />} />
                <Route path="/coach" element={<ChatView />} />
                <Route path="/nutrition" element={<NutritionView />} />
                <Route path="/workouts" element={<WorkoutsView />} />
                <Route path="/tracker" element={<TrackerView />} />
                <Route path="/profile" element={<ProfileView />} />
                <Route path="/design" element={<DesignGalleryView />} />
              </Route>
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}
