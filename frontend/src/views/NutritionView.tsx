/**
 * src/views/NutritionView.tsx
 * Complete redesign of Nutrition & Metabolic Targets:
 * - Hero Card: Largest daily calorie target + multi-segment macro ProgressRing (Protein, Carbs, Fat)
 * - StatCards Row: TDEE, BMR with formula name, Hydration (with tooltips)
 * - Meal Plan: 2-stage resilient loader:
 *   Stage 1: Fetch /api/nutrition/plan without guidance (6s timeout, skeleton, retry)
 *   Stage 2: Fetch guidance separately with its own skeleton and 30-60s timeout
 * - SegmentedControl for meals per day (3 to 6) + training-time picker
 * - Print meal plan button
 * - "Ask the Guides" right-side Drawer with suggested prompts and RAG sources
 */

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useProfile } from '../context/ProfileContext';
import { calculateMacros, getMealPlan, askNutrition } from '../api/client';
import {
  PageHeader,
  Card,
  StatCard,
  SegmentedControl,
  Button,
  Badge,
  Drawer,
  Skeleton,
  ErrorState,
  ProgressRing,
  Toast,
} from '../design';
import {
  Utensils,
  Flame,
  Droplet,
  Clock,
  Printer,
  Sparkles,
  HelpCircle,
  BookOpen,
  ArrowRight,
  RefreshCw,
  Send,
  Loader2,
  CheckCircle2,
} from 'lucide-react';

interface MealItem {
  label: string;
  time_hint: string;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  kcal: number;
}

interface MacroResponse {
  bmr: number;
  bmr_formula: string;
  tdee: number;
  target_kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  floor_applied?: boolean;
  warnings?: string[];
}

interface MealPlanResponse {
  macros: MacroResponse;
  meals: MealItem[];
  hydration_ml: number;
  guidance?: {
    meal_timing?: { text: string; sources: Array<{ source: string; page: number }> };
    hydration?: { text: string; sources: Array<{ source: string; page: number }> };
    supplements?: { text: string; sources: Array<{ source: string; page: number }> };
  };
}

export function NutritionView() {
  const { profile } = useProfile();

  // Macro calculation state
  const [macroResult, setMacroResult] = useState<MacroResponse | null>(null);
  const [isLoadingMacros, setIsLoadingMacros] = useState(false);

  // Meal plan state (Stage 1: Deterministic Plan)
  const [mealsPerDay, setMealsPerDay] = useState<number>(4);
  const [trainingTime, setTrainingTime] = useState<string>('17:00');
  const [mealPlan, setMealPlan] = useState<MealPlanResponse | null>(null);
  const [isLoadingPlan, setIsLoadingPlan] = useState<boolean>(true);
  const [planError, setPlanError] = useState<string | null>(null);

  // Guidance state (Stage 2: Asynchronous RAG Guidance)
  const [guidance, setGuidance] = useState<MealPlanResponse['guidance'] | null>(null);
  const [isLoadingGuidance, setIsLoadingGuidance] = useState<boolean>(false);

  // "Ask the Guides" Drawer state
  const [isAskDrawerOpen, setIsAskDrawerOpen] = useState(false);
  const [askQuestion, setAskQuestion] = useState('');
  const [askAnswer, setAskAnswer] = useState<{ answer: string; sources: Array<{ source: string; page: number }> } | null>(null);
  const [isAsking, setIsAsking] = useState(false);
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    if (profile) {
      loadInitialData();
    }
  }, [profile]);

  const loadInitialData = async () => {
    setIsLoadingMacros(true);
    try {
      const data = await calculateMacros({});
      setMacroResult(data);
      loadDeterministicPlan(mealsPerDay, trainingTime);
    } catch (err: any) {
      setToast({ type: 'error', message: err.message || 'Failed to calculate macros' });
    } finally {
      setIsLoadingMacros(false);
    }
  };

  /**
   * Stage 1: Load deterministic meal plan WITHOUT guidance
   * Guaranteed to complete in <10ms from backend formula. 6s timeout protection.
   */
  const loadDeterministicPlan = async (mealsCount: number, time: string) => {
    setIsLoadingPlan(true);
    setPlanError(null);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 6000);

    try {
      const planData = await getMealPlan(
        {
          meals_per_day: mealsCount,
          training_time: time,
          include_guidance: false,
        },
        false // Do NOT request guidance in stage 1
      );
      setMealPlan(planData);

      // Now kick off Stage 2: Guidance loading in background
      loadRAGGuidance(mealsCount, time);
    } catch (err: any) {
      console.error('Error fetching meal plan:', err);
      setPlanError(err.name === 'AbortError' ? 'Meal plan request timed out. Click retry below.' : (err.message || 'Failed to generate meal plan.'));
    } finally {
      clearTimeout(timeoutId);
      setIsLoadingPlan(false);
    }
  };

  /**
   * Stage 2: Load RAG guidance separately with its own skeleton and 30-60s timeout
   */
  const loadRAGGuidance = async (mealsCount: number, time: string) => {
    setIsLoadingGuidance(true);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 45000);

    try {
      const guidanceData = await getMealPlan(
        {
          meals_per_day: mealsCount,
          training_time: time,
          include_guidance: true,
        },
        true
      );
      if (guidanceData?.guidance) {
        setGuidance(guidanceData.guidance);
      }
    } catch (err) {
      console.warn('Optional guidance fetch did not complete:', err);
    } finally {
      clearTimeout(timeoutId);
      setIsLoadingGuidance(false);
    }
  };

  const handleMealsChange = (count: number) => {
    setMealsPerDay(count);
    loadDeterministicPlan(count, trainingTime);
  };

  const handleTimeChange = (time: string) => {
    setTrainingTime(time);
    loadDeterministicPlan(mealsPerDay, time);
  };

  const handlePrint = () => {
    window.print();
  };

  const handleAskSubmit = async (e?: React.FormEvent, customQuestion?: string) => {
    if (e) e.preventDefault();
    const q = customQuestion || askQuestion;
    if (!q.trim() || isAsking) return;

    setIsAsking(true);
    setAskAnswer(null);
    try {
      const res = await askNutrition(q);
      setAskAnswer(res);
    } catch (err: any) {
      setToast({ type: 'error', message: err.message || 'Failed to get nutrition answer.' });
    } finally {
      setIsAsking(false);
    }
  };

  // Macro Donut Segments
  const macroSegments = useMemo(() => {
    if (!macroResult) return [];
    const totalKcal = macroResult.target_kcal || 2000;
    const proteinKcal = macroResult.protein_g * 4;
    const carbsKcal = macroResult.carbs_g * 4;
    const fatKcal = macroResult.fat_g * 9;

    return [
      {
        label: 'Protein',
        value: macroResult.protein_g,
        color: 'var(--macro-protein)',
        percent: Math.round((proteinKcal / totalKcal) * 100),
      },
      {
        label: 'Carbohydrates',
        value: macroResult.carbs_g,
        color: 'var(--macro-carbs)',
        percent: Math.round((carbsKcal / totalKcal) * 100),
      },
      {
        label: 'Dietary Fat',
        value: macroResult.fat_g,
        color: 'var(--macro-fat)',
        percent: Math.round((fatKcal / totalKcal) * 100),
      },
    ];
  }, [macroResult]);

  return (
    <div className="flex-1 overflow-y-auto bg-[var(--bg-app)] text-[var(--text-primary)] p-6 sm:p-10 transition-colors duration-200">
      <div className="max-w-[1200px] mx-auto space-y-8 pb-20">
        {/* Page Header */}
        <PageHeader
          title="Nutrition & Energy Targets"
          description="Evidence-based macronutrient periodization and daily energy targets calibrated deterministically around your training schedule."
          badge={<Badge variant="protein">Metabolic Engine</Badge>}
          actionSlot={
            <div className="flex items-center gap-3">
              <Button
                variant="secondary"
                size="md"
                onClick={handlePrint}
                leftIcon={<Printer className="w-4 h-4" />}
              >
                Print Plan
              </Button>
              <Button
                variant="primary"
                size="md"
                onClick={() => setIsAskDrawerOpen(true)}
                leftIcon={<Sparkles className="w-4 h-4" />}
              >
                Ask Guides
              </Button>
            </div>
          }
        />

        {/* Hero Card: Calorie Target + Donut Chart + Fixed Macro Color Legend */}
        {macroResult && (
          <Card
            title="Daily Caloric Balance & Macro Distribution"
            subtitle="Calculated from your resting metabolic baseline and selected body composition goal."
          >
            <div className="flex flex-col lg:flex-row items-center justify-between gap-8 py-2">
              {/* Donut Chart (ProgressRing) */}
              <div className="shrink-0 flex justify-center">
                <ProgressRing
                  size={240}
                  strokeWidth={18}
                  segments={macroSegments}
                  centerLabel="Target Intake"
                  centerValue={macroResult.target_kcal.toLocaleString()}
                  centerUnit="kcal / day"
                />
              </div>

              {/* Three Fixed Macro Breakdown Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 flex-1 w-full">
                {/* Protein Card (Fixed Cobalt Blue) */}
                <div className="p-4 sm:p-5 rounded-2xl bg-[var(--macro-protein-subtle)] border border-[var(--macro-protein-border)] flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-[var(--macro-protein-text)]">
                      Protein
                    </span>
                    <Badge variant="protein" size="sm">
                      {macroSegments[0]?.percent}% kcal
                    </Badge>
                  </div>
                  <div className="my-3">
                    <span className="text-3xl sm:text-4xl font-black font-sans tabular-nums text-[var(--macro-protein-text)]">
                      {macroResult.protein_g.toFixed(1)}
                    </span>
                    <span className="text-xs text-[var(--text-secondary)] font-sans ml-1 font-medium">
                      grams
                    </span>
                  </div>
                  <div className="text-xs text-[var(--text-secondary)] pt-2 border-t border-[var(--macro-protein-border)]/60 flex justify-between">
                    <span>Energy share</span>
                    <span className="font-sans tabular-nums font-semibold">
                      {Math.round(macroResult.protein_g * 4)} kcal
                    </span>
                  </div>
                </div>

                {/* Carbs Card (Fixed Amber Gold) */}
                <div className="p-4 sm:p-5 rounded-2xl bg-[var(--macro-carbs-subtle)] border border-[var(--macro-carbs-border)] flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-[var(--macro-carbs-text)]">
                      Carbohydrates
                    </span>
                    <Badge variant="carbs" size="sm">
                      {macroSegments[1]?.percent}% kcal
                    </Badge>
                  </div>
                  <div className="my-3">
                    <span className="text-3xl sm:text-4xl font-black font-sans tabular-nums text-[var(--macro-carbs-text)]">
                      {macroResult.carbs_g.toFixed(1)}
                    </span>
                    <span className="text-xs text-[var(--text-secondary)] font-sans ml-1 font-medium">
                      grams
                    </span>
                  </div>
                  <div className="text-xs text-[var(--text-secondary)] pt-2 border-t border-[var(--macro-carbs-border)]/60 flex justify-between">
                    <span>Energy share</span>
                    <span className="font-sans tabular-nums font-semibold">
                      {Math.round(macroResult.carbs_g * 4)} kcal
                    </span>
                  </div>
                </div>

                {/* Fat Card (Fixed Emerald Green) */}
                <div className="p-4 sm:p-5 rounded-2xl bg-[var(--macro-fat-subtle)] border border-[var(--macro-fat-border)] flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-[var(--macro-fat-text)]">
                      Dietary Fats
                    </span>
                    <Badge variant="fat" size="sm">
                      {macroSegments[2]?.percent}% kcal
                    </Badge>
                  </div>
                  <div className="my-3">
                    <span className="text-3xl sm:text-4xl font-black font-sans tabular-nums text-[var(--macro-fat-text)]">
                      {macroResult.fat_g.toFixed(1)}
                    </span>
                    <span className="text-xs text-[var(--text-secondary)] font-sans ml-1 font-medium">
                      grams
                    </span>
                  </div>
                  <div className="text-xs text-[var(--text-secondary)] pt-2 border-t border-[var(--macro-fat-border)]/60 flex justify-between">
                    <span>Energy share</span>
                    <span className="font-sans tabular-nums font-semibold">
                      {Math.round(macroResult.fat_g * 9)} kcal
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        )}

        {/* Small StatCards Row: TDEE, BMR, Hydration */}
        {macroResult && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StatCard
              label="Total Daily Energy Expenditure"
              value={macroResult.tdee.toLocaleString()}
              unit="kcal"
              subValue="Maintenance energy burn"
              infoTooltip="Total Daily Energy Expenditure: Your baseline BMR scaled by daily physical activity multiplier."
              color="neutral"
            />
            <StatCard
              label="Basal Metabolic Rate"
              value={macroResult.bmr.toLocaleString()}
              unit="kcal"
              subValue={macroResult.bmr_formula}
              infoTooltip="BMR: Minimum caloric energy required to sustain life at absolute rest."
              color="accent"
            />
            <StatCard
              label="Recommended Daily Hydration"
              value={mealPlan ? (mealPlan.hydration_ml / 1000).toFixed(1) : '3.2'}
              unit="Liters"
              subValue="Baseline 40 ml / kg body mass"
              infoTooltip="Hydration target derived from clinical sports science guidelines."
              color="protein"
            />
          </div>
        )}

        {/* Meal Plan Timeline & Distribution (Stage 1 & 2) */}
        <Card
          title="Daily Meal Distribution & Timing"
          subtitle="Calibrated around your daily workout schedule to maximize glycogen replenishment and muscle protein synthesis."
          action={
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-[var(--text-muted)]">Meals:</span>
                <SegmentedControl
                  size="sm"
                  value={mealsPerDay}
                  onChange={(val) => handleMealsChange(Number(val))}
                  options={[
                    { value: 3, label: '3' },
                    { value: 4, label: '4' },
                    { value: 5, label: '5' },
                    { value: 6, label: '6' },
                  ]}
                />
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-[var(--text-muted)]">Workout at:</span>
                <input
                  type="time"
                  value={trainingTime}
                  onChange={(e) => handleTimeChange(e.target.value)}
                  className="bg-[var(--bg-subtle)] border border-[var(--border-subtle)] rounded-xl px-2.5 py-1 text-xs text-[var(--text-primary)] font-sans tabular-nums font-medium focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)]"
                />
              </div>
            </div>
          }
        >
          {isLoadingPlan ? (
            <div className="space-y-4 py-2">
              <Skeleton variant="card" height={80} />
              <Skeleton variant="card" height={80} />
              <Skeleton variant="card" height={80} />
              <Skeleton variant="card" height={80} />
            </div>
          ) : planError ? (
            <ErrorState
              title="Failed to Load Meal Plan"
              message={planError}
              onRetry={() => loadDeterministicPlan(mealsPerDay, trainingTime)}
            />
          ) : mealPlan && mealPlan.meals ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {mealPlan.meals.map((meal, idx) => (
                  <div
                    key={idx}
                    className="p-4 sm:p-5 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] hover:border-[var(--border-prominent)] shadow-xs transition-all space-y-3"
                  >
                    <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)]">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-lg bg-[var(--bg-subtle)] flex items-center justify-center text-[var(--accent-text)]">
                          <Clock className="w-3.5 h-3.5" />
                        </div>
                        <span className="text-sm font-bold text-[var(--text-primary)]">
                          {meal.label}
                        </span>
                      </div>
                      <span className="text-xs font-semibold text-[var(--text-muted)] font-sans tabular-nums">
                        {meal.time_hint}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs pt-1">
                      <span className="text-base font-black font-sans tabular-nums text-[var(--text-primary)]">
                        {meal.kcal} <span className="text-xs font-normal text-[var(--text-muted)]">kcal</span>
                      </span>

                      <div className="flex items-center gap-2">
                        <Badge variant="protein" size="sm">
                          P: {meal.protein_g}g
                        </Badge>
                        <Badge variant="carbs" size="sm">
                          C: {meal.carbs_g}g
                        </Badge>
                        <Badge variant="fat" size="sm">
                          F: {meal.fat_g}g
                        </Badge>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Stage 2 Guidance Block */}
              {isLoadingGuidance ? (
                <div className="p-4 rounded-xl bg-[var(--bg-subtle)]/50 border border-[var(--border-subtle)] space-y-2 mt-4">
                  <div className="flex items-center gap-2 text-xs font-semibold text-[var(--accent-text)]">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Retrieving nutrient timing literature...
                  </div>
                  <Skeleton variant="text" width="80%" />
                </div>
              ) : guidance && (
                <div className="mt-6 p-4 sm:p-5 rounded-2xl bg-[var(--accent-primary-subtle)] border border-[var(--accent-primary-border)] space-y-3">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[var(--accent-text)]">
                    <BookOpen className="w-4 h-4" />
                    Verified Nutrient Timing Guidance
                  </div>
                  {guidance.meal_timing && (
                    <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                      {guidance.meal_timing.text}
                    </p>
                  )}
                  {guidance.hydration && (
                    <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                      {guidance.hydration.text}
                    </p>
                  )}
                </div>
              )}
            </div>
          ) : null}
        </Card>
      </div>

      {/* "Ask the Guides" Drawer */}
      <Drawer
        isOpen={isAskDrawerOpen}
        onClose={() => setIsAskDrawerOpen(false)}
        title="Nutrition Knowledge Base"
        description="Ask specific questions answered directly from verified evidence manuals."
      >
        <div className="space-y-6">
          <form onSubmit={handleAskSubmit} className="space-y-3">
            <textarea
              rows={3}
              value={askQuestion}
              onChange={(e) => setAskQuestion(e.target.value)}
              placeholder="e.g. When should I take creatine, and does meal timing matter for muscle growth?"
              className="w-full bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-xl p-3 text-xs sm:text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)] resize-none"
            />
            <div className="flex justify-between items-center">
              <span className="text-[11px] text-[var(--text-muted)]">
                Isolated to Nutrition category index
              </span>
              <Button variant="primary" size="sm" type="submit" isLoading={isAsking} leftIcon={<Send className="w-3.5 h-3.5" />}>
                Ask Guide
              </Button>
            </div>
          </form>

          {/* Suggested Prompts */}
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] block mb-2.5">
              Suggested Questions
            </span>
            <div className="space-y-2">
              {[
                'How much protein can the body absorb in one meal?',
                'Should I consume fast carbohydrates immediately post-workout?',
                'What are optimal fluid intake recommendations during training?',
              ].map((prompt, pIdx) => (
                <button
                  key={pIdx}
                  type="button"
                  onClick={() => {
                    setAskQuestion(prompt);
                    handleAskSubmit(undefined, prompt);
                  }}
                  className="w-full text-left p-3 rounded-xl bg-[var(--bg-subtle)] hover:bg-[var(--bg-card)] border border-[var(--border-subtle)] hover:border-[var(--border-prominent)] text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all cursor-pointer flex items-center justify-between group"
                >
                  <span>{prompt}</span>
                  <ArrowRight className="w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-[var(--accent-primary)] group-hover:translate-x-0.5 transition-transform" />
                </button>
              ))}
            </div>
          </div>

          {/* Streamed Answer Card */}
          {isAsking && (
            <div className="p-4 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-subtle)] flex items-center gap-3 text-xs text-[var(--text-secondary)]">
              <Loader2 className="w-4 h-4 animate-spin text-[var(--accent-primary)]" />
              <span>Querying verified sports nutrition manuals...</span>
            </div>
          )}

          {askAnswer && (
            <div className="p-4 sm:p-5 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-prominent)] space-y-4 shadow-sm animate-in fade-in-0 duration-200">
              <div className="flex items-center gap-2 text-xs font-bold text-[var(--accent-text)]">
                <CheckCircle2 className="w-4 h-4" />
                Verified Answer
              </div>
              <p className="text-xs sm:text-sm text-[var(--text-primary)] leading-relaxed whitespace-pre-wrap">
                {askAnswer.answer}
              </p>

              {askAnswer.sources && askAnswer.sources.length > 0 && (
                <div className="pt-3 border-t border-[var(--border-subtle)] space-y-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] block">
                    Source Citations
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {askAnswer.sources.map((s, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 rounded-md text-[10px] bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-secondary)] font-mono"
                      >
                        {s.source} (p. {s.page})
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </Drawer>

      {toast && (
        <Toast
          type={toast.type}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}
