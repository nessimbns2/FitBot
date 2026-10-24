/**
 * src/App.tsx
 * Top-level application shell with ThemeProvider, ProfileProvider, Router, and routes.
 */

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './design';
import { ProfileProvider } from './context/ProfileContext';
import { Sidebar, MobileTabBar, MobileTopBar } from './components/Navigation';
import { TodayView } from './views/TodayView';
import { ChatView } from './views/ChatView';
import { NutritionView } from './views/NutritionView';
import { WorkoutsView } from './views/WorkoutsView';
import { TrackerView } from './views/TrackerView';
import { ProfileView } from './views/ProfileView';
import { DesignGalleryView } from './views/DesignGalleryView';

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <ProfileProvider>
          <div className="flex h-screen w-screen overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)]">
            {/* Desktop Left Sidebar / Rail */}
            <Sidebar />

            {/* Main Content Area */}
            <main className="flex-1 flex flex-col h-full overflow-hidden relative pb-16 md:pb-0">
              {/* Mobile Top Header */}
              <MobileTopBar />

              <Routes>
                {/* Home route '/' = "Today" dashboard */}
                <Route path="/" element={<TodayView />} />
                {/* Coach Chat moved to '/coach' */}
                <Route path="/coach" element={<ChatView />} />
                <Route path="/nutrition" element={<NutritionView />} />
                <Route path="/workouts" element={<WorkoutsView />} />
                <Route path="/tracker" element={<TrackerView />} />
                <Route path="/profile" element={<ProfileView />} />
                <Route path="/design" element={<DesignGalleryView />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </main>

            {/* Mobile Bottom Navigation Bar */}
            <MobileTabBar />
          </div>
        </ProfileProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}
