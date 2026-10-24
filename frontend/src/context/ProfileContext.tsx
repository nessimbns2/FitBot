/**
 * src/context/ProfileContext.tsx
 * Global context providing the active UserProfile, unit conversions, and update actions.
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import { getProfile, updateProfile as apiUpdateProfile } from '../api/client';

export interface UserProfile {
  id?: number;
  age: number;
  sex: 'male' | 'female';
  height_cm: number;
  weight_kg: number;
  body_fat_pct?: number | null;
  experience_level: 'beginner' | 'intermediate' | 'advanced';
  goal: 'hypertrophy' | 'fat_loss' | 'strength' | 'athletic_performance';
  somatotype: 'mesomorph' | 'endomorph' | 'ectomorph' | 'unknown';
  activity_level: 'sedentary' | 'light' | 'moderate' | 'very_active' | 'extreme';
  unit_system: 'metric' | 'imperial';
}

interface ProfileContextType {
  profile: UserProfile | null;
  isLoading: boolean;
  error: string | null;
  update: (changes: Partial<UserProfile>) => Promise<{ success: boolean; profile?: UserProfile; error?: string }>;
  refresh: () => Promise<void>;
  needsOnboarding: boolean;
}

const ProfileContext = createContext<ProfileContextType | null>(null);

export function ProfileProvider({ children }: { children: React.ReactNode }) {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProfile = async () => {
    try {
      setIsLoading(true);
      const data = await getProfile();
      setProfile(data);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching profile:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const update = async (changes: Partial<UserProfile>) => {
    try {
      const updated = await apiUpdateProfile(changes);
      setProfile(updated);
      return { success: true, profile: updated };
    } catch (err: any) {
      return { success: false, error: err.message };
    }
  };

  const needsOnboarding = Boolean(profile && (!profile.weight_kg || !profile.height_cm));

  return (
    <ProfileContext.Provider value={{ profile, isLoading, error, update, refresh: fetchProfile, needsOnboarding }}>
      {children}
    </ProfileContext.Provider>
  );
}

export function useProfile() {
  const ctx = useContext(ProfileContext);
  if (!ctx) {
    throw new Error('useProfile must be used within a ProfileProvider');
  }
  return ctx;
}
