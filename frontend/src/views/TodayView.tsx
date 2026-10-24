/**
 * src/views/TodayView.tsx
 * "Today" Home Dashboard (Route: /)
 * Built strictly from existing endpoints:
 * 1. Macro ProgressRing for the daily target (with grams and % legend)
 * 2. Next-Session Target card for last-used lift (with double progression reason)
 * 3. Mini Weekly Effective Volume summary (against 10-20 target band)
 * 4. "Ask the Coach" input (submits directly to /coach)
 * 5. Contextual empty states with clear CTAs
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProfile } from '../context/ProfileContext';
import {
  calculateMacros,
  getWeeklyVolume,
  getRecommendation,
  getExerciseHistory,
  getCatalogExercises,
} from '../api/client';
import {
  PageHeader,
  Card,
  StatCard,
  ProgressRing,
  Button,
  Badge,
  Skeleton,
  EmptyState,
} from '../design';
import {
  Sparkles,
  Target,
  Activity,
  MessageSquare,
  ArrowRight,
  TrendingUp,
  Dumbbell,
  Utensils,
  Play,
  Send,
  Calendar,
} from 'lucide-react';

export function TodayView() {
  const { profile } = useProfile();
  const navigate = useNavigate();

  // Macro Target State
  const [macros, setMacros] = useState<any>(null);
  const [isLoadingMacros, setIsLoadingMacros] = useState<boolean>(true);

  // Next Session Target State
  const [lastExerciseId, setLastExerciseId] = useState<string>('barbell-bench-press');
  const [lastExerciseName, setLastExerciseName] = useState<string>('Barbell Bench Press');
  const [recommendation, setRecommendation] = useState<any>(null);
  const [isLoadingRec, setIsLoadingRec] = useState<boolean>(true);

  // Weekly Volume State
  const [volumeSummary, setVolumeSummary] = useState<any>(null);
  const [isLoadingVolume, setIsLoadingVolume] = useState<boolean>(true);

  // Quick Ask Input
  const [quickQuestion, setQuickQuestion] = useState<string>('');

  useEffect(() => {
    loadDashboardData();
  }, [profile]);

  const loadDashboardData = async () => {
    // 1. Load Macros
    setIsLoadingMacros(true);
    try {
      const macroData = await calculateMacros({});
      setMacros(macroData);
    } catch (err) {
      console.error('Error loading today macros:', err);
    } finally {
      setIsLoadingMacros(false);
    }

    // 2. Load Volume
    setIsLoadingVolume(true);
    try {
      const volData = await getWeeklyVolume();
      setVolumeSummary(volData);
    } catch (err) {
      console.error('Error loading today volume:', err);
    } finally {
      setIsLoadingVolume(false);
    }

    // 3. Load Last Used Lift Recommendation
    setIsLoadingRec(true);
    try {
      const catalog = await getCatalogExercises();
      const defaultEx = catalog[0] || { id: 'barbell-bench-press', name: 'Barbell Bench Press' };
      setLastExerciseId(defaultEx.id);
      setLastExerciseName(defaultEx.name);

      const rec = await getRecommendation(defaultEx.id);
      setRecommendation(rec);
    } catch (err) {
      console.error('Error loading today recommendation:', err);
    } finally {
      setIsLoadingRec(false);
    }
  };

  const handleQuickAsk = (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickQuestion.trim()) return;
    navigate('/coach', { state: { initialPrompt: quickQuestion } });
  };

  const macroSegments = useMemo(() => {
    if (!macros) return [];
    const totalKcal = macros.target_kcal || 2000;
    const proteinKcal = macros.protein_g * 4;
    const carbsKcal = macros.carbs_g * 4;
    const fatKcal = macros.fat_g * 9;

    return [
      {
        label: 'Protein',
        value: macros.protein_g,
        color: 'var(--macro-protein)',
        percent: Math.round((proteinKcal / totalKcal) * 100),
      },
      {
        label: 'Carbs',
        value: macros.carbs_g,
        color: 'var(--macro-carbs)',
        percent: Math.round((carbsKcal / totalKcal) * 100),
      },
      {
        label: 'Fat',
        value: macros.fat_g,
        color: 'var(--macro-fat)',
        percent: Math.round((fatKcal / totalKcal) * 100),
      },
    ];
  }, [macros]);

  return (
    <div className="flex-1 overflow-y-auto bg-[var(--bg-app)] text-[var(--text-primary)] p-6 sm:p-10 transition-colors duration-200">
      <div className="max-w-[1200px] mx-auto space-y-8 pb-20">
        {/* Page Header */}
        <PageHeader
          title={`Welcome back, ${profile?.sex === 'female' ? 'Athlete ♀' : 'Athlete ♂'}`}
          description="Here is your daily training readiness snapshot: calibrated nutrition targets, upcoming overload objectives, and weekly volume tracking."
          badge={<Badge variant="accent">Today's Focus</Badge>}
          actionSlot={
            <Button
              variant="primary"
              size="md"
              onClick={() => navigate('/tracker')}
              leftIcon={<Play className="w-4 h-4" />}
            >
              Start Workout
            </Button>
          }
        />

        {/* Hero Grid: Daily Nutrition Ring + Next Session Target (2 Columns) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch">
          {/* Card 1: Daily Calorie & Macro Donut (6 cols) */}
          <div className="lg:col-span-6 flex flex-col">
            <Card
              title="Daily Fuel Target"
              subtitle="Energy target and macronutrient distribution calibrated for your goal."
              action={
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate('/nutrition')}
                  rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                >
                  View Plan
                </Button>
              }
              className="flex-1 flex flex-col justify-between"
            >
              {isLoadingMacros ? (
                <div className="py-8 flex justify-center">
                  <Skeleton variant="circular" width={180} height={180} />
                </div>
              ) : macros ? (
                <div className="flex flex-col sm:flex-row items-center justify-around gap-6 py-2">
                  <ProgressRing
                    size={190}
                    strokeWidth={16}
                    segments={macroSegments}
                    centerLabel="Daily Target"
                    centerValue={macros.target_kcal.toLocaleString()}
                    centerUnit="kcal"
                  />

                  <div className="space-y-2.5 w-full sm:max-w-[190px]">
                    <div className="p-2.5 rounded-xl bg-[var(--macro-protein-subtle)] border border-[var(--macro-protein-border)] flex items-center justify-between">
                      <span className="text-xs font-bold text-[var(--macro-protein-text)]">Protein</span>
                      <span className="text-sm font-black font-sans tabular-nums text-[var(--macro-protein-text)]">
                        {macros.protein_g.toFixed(0)}g
                      </span>
                    </div>

                    <div className="p-2.5 rounded-xl bg-[var(--macro-carbs-subtle)] border border-[var(--macro-carbs-border)] flex items-center justify-between">
                      <span className="text-xs font-bold text-[var(--macro-carbs-text)]">Carbs</span>
                      <span className="text-sm font-black font-sans tabular-nums text-[var(--macro-carbs-text)]">
                        {macros.carbs_g.toFixed(0)}g
                      </span>
                    </div>

                    <div className="p-2.5 rounded-xl bg-[var(--macro-fat-subtle)] border border-[var(--macro-fat-border)] flex items-center justify-between">
                      <span className="text-xs font-bold text-[var(--macro-fat-text)]">Fat</span>
                      <span className="text-sm font-black font-sans tabular-nums text-[var(--macro-fat-text)]">
                        {macros.fat_g.toFixed(0)}g
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="No Nutrition Data"
                  description="Set up your profile biometrics to calculate your daily energy targets."
                  action={{ label: 'Configure Profile', onClick: () => navigate('/profile') }}
                />
              )}
            </Card>
          </div>

          {/* Card 2: Next Session Target Objective (6 cols) */}
          <div className="lg:col-span-6 flex flex-col">
            <Card
              title="Next Session Objective"
              subtitle="Calculated double progression target for your primary lift."
              action={
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate('/tracker')}
                  rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                >
                  Log In Tracker
                </Button>
              }
              className="flex-1 flex flex-col justify-between"
            >
              {isLoadingRec ? (
                <div className="py-6 space-y-3">
                  <Skeleton variant="text" width="50%" />
                  <Skeleton variant="card" height={100} />
                </div>
              ) : recommendation ? (
                <div className="space-y-4 py-2">
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider text-[var(--accent-text)] flex items-center gap-1.5 mb-1">
                      <Target className="w-3.5 h-3.5" /> Next Overload Target
                    </span>
                    <h3 className="text-xl font-bold text-[var(--text-primary)]">
                      {lastExerciseName}
                    </h3>
                  </div>

                  <div className="p-4 rounded-2xl bg-[var(--bg-subtle)] border border-[var(--border-subtle)] flex items-baseline justify-between">
                    <div>
                      <span className="text-[10px] uppercase font-bold text-[var(--text-muted)] block">
                        Target Load
                      </span>
                      <span className="text-3xl sm:text-4xl font-black font-sans tabular-nums text-[var(--text-primary)] tracking-tight">
                        {recommendation.weight_kg}
                      </span>
                      <span className="text-sm font-semibold text-[var(--text-muted)] font-sans ml-1">
                        kg
                      </span>
                    </div>

                    <div className="text-right">
                      <span className="text-[10px] uppercase font-bold text-[var(--text-muted)] block">
                        Repetitions
                      </span>
                      <span className="text-xl font-bold font-sans text-[var(--accent-text)]">
                        {recommendation.rep_target}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    <strong className="text-[var(--text-primary)]">Rule: </strong>
                    {recommendation.reason}
                  </p>
                </div>
              ) : (
                <EmptyState
                  title="No Overload Targets Yet"
                  description="Complete a workout session in Overload Tracker to generate progression targets."
                  action={{ label: 'Open Tracker', onClick: () => navigate('/tracker') }}
                />
              )}
            </Card>
          </div>
        </div>

        {/* Middle Row: Mini Weekly Volume + Quick Coach Ask */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Mini Weekly Volume (7 cols) */}
          <div className="lg:col-span-7">
            <Card
              title="Weekly Hypertrophy Gauge"
              subtitle="Effective working sets (RPE ≥ 6.0) across target muscle groups this week."
              action={
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate('/tracker')}
                  rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                >
                  Volume Breakdown
                </Button>
              }
            >
              {isLoadingVolume ? (
                <div className="space-y-3 py-2">
                  <Skeleton variant="text" width="100%" />
                  <Skeleton variant="text" width="100%" />
                  <Skeleton variant="text" width="100%" />
                </div>
              ) : volumeSummary?.muscles ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-1">
                  {Object.entries(volumeSummary.muscles).slice(0, 6).map(([muscle, data]: [string, any]) => {
                    const count = data.count || 0;
                    const inRange = count >= 10 && count <= 20;

                    return (
                      <div
                        key={muscle}
                        className="p-3 rounded-xl bg-[var(--bg-subtle)]/50 border border-[var(--border-subtle)] space-y-1.5"
                      >
                        <div className="flex justify-between items-center text-xs">
                          <span className="font-bold capitalize text-[var(--text-primary)] truncate">
                            {muscle}
                          </span>
                          <span className="font-sans tabular-nums font-bold text-xs text-[var(--text-primary)]">
                            {count}
                          </span>
                        </div>
                        <div className="w-full bg-[var(--bg-card)] h-1.5 rounded-full overflow-hidden">
                          <div
                            style={{ width: `${Math.min(100, (count / 20) * 100)}%` }}
                            className={`h-full rounded-full ${
                              inRange ? 'bg-emerald-500' : count > 20 ? 'bg-amber-500' : 'bg-[var(--accent-primary)]'
                            }`}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="p-6 text-center text-xs text-[var(--text-muted)]">
                  Log working sets in Tracker to populate your weekly muscle volume matrix.
                </div>
              )}
            </Card>
          </div>

          {/* Quick Coach Ask Card (5 cols) */}
          <div className="lg:col-span-5">
            <Card
              title="Ask Evidence Coach"
              subtitle="Query verified exercise technique or nutrition science in real time."
            >
              <form onSubmit={handleQuickAsk} className="space-y-3 pt-1">
                <textarea
                  rows={3}
                  value={quickQuestion}
                  onChange={(e) => setQuickQuestion(e.target.value)}
                  placeholder="Ask a question or describe your workout to log sets..."
                  className="w-full bg-[var(--bg-subtle)] border border-[var(--border-subtle)] rounded-xl p-3 text-xs sm:text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)] resize-none"
                />
                <div className="flex justify-between items-center">
                  <span className="text-[11px] text-[var(--text-muted)]">
                    Direct RAG response
                  </span>
                  <Button
                    variant="primary"
                    size="sm"
                    type="submit"
                    leftIcon={<Send className="w-3.5 h-3.5" />}
                  >
                    Ask Coach
                  </Button>
                </div>
              </form>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
