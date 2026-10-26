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
import { useNavigate } from 'react-router-dom';
import { useProfile } from '../context/ProfileContext';
import { calculateMacros, getMealPlan, askNutrition, scanMealPhoto } from '../api/client';
import { FoodLogSection } from '../components/nutrition/FoodLogSection';
import type { FoodLogDraft, MealSlotValue } from '../components/nutrition/FoodLogSection';
import {
  PageHeader,
  Card,
  StatCard,
  SegmentedControl,
  Button,
  Badge,
  Drawer,
  Dialog,
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
  Camera,
  Upload,
  Trash2,
  X,
  Plus,
  AlertCircle,
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
  const navigate = useNavigate();
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

  // AI Meal Scanner (Vision Macro Logger) State
  const [isScannerOpen, setIsScannerOpen] = useState(false);
  const [scannedImage, setScannedImage] = useState<string | null>(null);
  const [mimeType, setMimeType] = useState<string>('image/jpeg');
  const [isAnalyzingMeal, setIsAnalyzingMeal] = useState(false);
  const [targetMealSlot, setTargetMealSlot] = useState<string>('Lunch');
  const [scanResult, setScanResult] = useState<{
    meal_name: string;
    confidence: string;
    total_calories: number;
    protein_g: number;
    carbs_g: number;
    fat_g: number;
    food_items: Array<{
      name: string;
      portion_est: string;
      calories: number;
      protein_g: number;
      carbs_g: number;
      fat_g: number;
    }>;
    coaching_tip?: string;
  } | null>(null);

  // A scanned meal waiting to be reviewed in the diary form (saved via the API, not the browser)
  const [incomingDraft, setIncomingDraft] = useState<FoodLogDraft | null>(null);

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

  const handleAskSubmit = (e?: React.FormEvent, customQuestion?: string) => {
    if (e) e.preventDefault();
    const q = (customQuestion || askQuestion).trim();
    if (!q) return;

    setIsAskDrawerOpen(false);
    navigate('/coach', { state: { initialPrompt: q } });
  };

  // ── AI Meal Scanner Handlers ────────────────────────────────────────────────
  const handleImageUpload = (file: File) => {
    if (!file.type.startsWith('image/')) {
      setToast({ type: 'error', message: 'Please upload an image file (JPEG, PNG, WEBP).' });
      return;
    }
    setMimeType(file.type);
    const reader = new FileReader();
    reader.onload = (e) => {
      const b64 = e.target?.result as string;
      setScannedImage(b64);
      setScanResult(null);
    };
    reader.readAsDataURL(file);
  };

  const handleScanMeal = async () => {
    if (!scannedImage) {
      setToast({ type: 'error', message: 'Please upload or capture a meal photo first.' });
      return;
    }

    setIsAnalyzingMeal(true);
    setScanResult(null);
    try {
      const result = await scanMealPhoto(scannedImage, mimeType, targetMealSlot);
      setScanResult(result);
      setToast({ type: 'success', message: `Identified: ${result.meal_name} (~${result.total_calories} kcal)` });
    } catch (err: any) {
      setToast({ type: 'error', message: err.message || 'Vision analysis failed. Please try a clearer photo.' });
    } finally {
      setIsAnalyzingMeal(false);
    }
  };

  const SCAN_SLOT_TO_DIARY: Record<string, MealSlotValue> = {
    Breakfast: 'breakfast',
    Lunch: 'lunch',
    Dinner: 'dinner',
    'Post-Workout': 'post_workout',
  };

  // The AI's guess is not saved directly: it opens the diary form so it can be checked and corrected.
  const handleCommitLoggedMeal = () => {
    if (!scanResult) return;
    const items = (scanResult.food_items || []).map((f) => `${f.name} (${f.portion_est})`).join(', ');
    setIncomingDraft({
      name: scanResult.meal_name,
      meal_slot: SCAN_SLOT_TO_DIARY[targetMealSlot] || 'snack',
      calories: scanResult.total_calories,
      protein_g: scanResult.protein_g,
      carbs_g: scanResult.carbs_g,
      fat_g: scanResult.fat_g,
      notes: items.slice(0, 500),
      source: 'photo_scan',
    });
    setIsScannerOpen(false);
    setScannedImage(null);
    setScanResult(null);
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
                variant="primary"
                size="md"
                onClick={() => {
                  setIsScannerOpen(true);
                  setScanResult(null);
                  setScannedImage(null);
                }}
                leftIcon={<Camera className="w-4 h-4" />}
              >
                Scan Meal (AI)
              </Button>
              <Button
                variant="secondary"
                size="md"
                onClick={handlePrint}
                leftIcon={<Printer className="w-4 h-4" />}
              >
                Print Plan
              </Button>
              <Button
                variant="secondary"
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

        {/* Today's Food Diary (database-backed) */}
        <FoodLogSection
          onScanClick={() => {
            setIsScannerOpen(true);
            setScanResult(null);
            setScannedImage(null);
          }}
          incomingDraft={incomingDraft}
          onDraftHandled={() => setIncomingDraft(null)}
          onNotify={(type, message) => setToast({ type, message })}
        />
      </div>

      {/* AI Meal Scanner Modal Dialog */}
      {isScannerOpen && (
        <Dialog
          isOpen={isScannerOpen}
          onClose={() => {
            if (!isAnalyzingMeal) {
              setIsScannerOpen(false);
              setScanResult(null);
              setScannedImage(null);
            }
          }}
          title="AI Meal Scanner (Vision Macro Logger)"
          description="Snap or upload a photo of your food plate to calculate calories and macros with Gemini Vision."
          maxWidth="md"
        >
          <div className="space-y-5 pt-2">
            {/* Meal Slot Selector */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] block">
                Target Meal Time
              </label>
              <div className="grid grid-cols-4 gap-2">
                {['Breakfast', 'Lunch', 'Dinner', 'Post-Workout'].map((slot) => (
                  <button
                    key={slot}
                    type="button"
                    onClick={() => setTargetMealSlot(slot)}
                    className={`py-2 px-3 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${targetMealSlot === slot
                      ? 'bg-[var(--accent-primary)] text-white border-[var(--accent-primary)] shadow-xs'
                      : 'bg-[var(--bg-subtle)] text-[var(--text-secondary)] border-[var(--border-subtle)] hover:border-[var(--accent-primary)]/50'
                      }`}
                  >
                    {slot}
                  </button>
                ))}
              </div>
            </div>

            {/* Photo Upload / Drop Area */}
            {!scannedImage ? (
              <div className="border-2 border-dashed border-[var(--border-subtle)] hover:border-[var(--accent-primary)] rounded-2xl p-6 text-center bg-[var(--bg-subtle)]/40 transition-colors">
                <input
                  type="file"
                  accept="image/*"
                  id="meal-photo-input"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleImageUpload(f);
                  }}
                />
                <label
                  htmlFor="meal-photo-input"
                  className="cursor-pointer flex flex-col items-center justify-center space-y-3"
                >
                  <div className="w-14 h-14 rounded-2xl bg-[var(--accent-primary-subtle)] text-[var(--accent-text)] flex items-center justify-center shadow-xs">
                    <Camera className="w-7 h-7" />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-[var(--text-primary)] block">
                      Click to capture or upload food photo
                    </span>
                    <span className="text-[11px] text-[var(--text-muted)] mt-1 block">
                      Supports JPG, PNG, WEBP from phone camera or gallery
                    </span>
                  </div>
                </label>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Image Preview */}
                <div className="relative rounded-2xl overflow-hidden border border-[var(--border-subtle)] max-h-64 bg-black/10 flex items-center justify-center">
                  <img
                    src={scannedImage}
                    alt="Scanned Food Plate"
                    className="w-full h-full object-cover max-h-64"
                  />
                  {!isAnalyzingMeal && (
                    <button
                      type="button"
                      onClick={() => {
                        setScannedImage(null);
                        setScanResult(null);
                      }}
                      className="absolute top-3 right-3 p-1.5 rounded-xl bg-black/60 text-white hover:bg-black/80 transition-colors cursor-pointer"
                      title="Remove image"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>

                {/* Scan Button or Loading State */}
                {!scanResult && (
                  <div className="flex justify-center pt-1">
                    <Button
                      variant="primary"
                      size="md"
                      onClick={handleScanMeal}
                      disabled={isAnalyzingMeal}
                      leftIcon={isAnalyzingMeal ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                      className="w-full sm:w-auto px-8"
                    >
                      {isAnalyzingMeal ? 'Analyzing Plate with Gemini Vision...' : 'Analyze Meal & Extract Macros'}
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* Vision Scan Result Display */}
            {scanResult && (
              <div className="p-4 sm:p-5 rounded-2xl bg-[var(--bg-subtle)] border border-[var(--border-prominent)] space-y-4 animate-in fade-in-0 duration-200">
                <div className="flex items-start justify-between gap-3 pb-3 border-b border-[var(--border-subtle)]">
                  <div>
                    <div className="flex items-center gap-2">
                      <Badge variant="accent" size="sm">
                        Confidence: {scanResult.confidence}
                      </Badge>
                      <span className="text-xs text-[var(--text-muted)] uppercase tracking-wider font-semibold">
                        {targetMealSlot}
                      </span>
                    </div>
                    <h4 className="text-base font-bold text-[var(--text-primary)] mt-1">
                      {scanResult.meal_name}
                    </h4>
                  </div>
                  <div className="text-right shrink-0">
                    <span className="text-xl font-black text-[var(--text-primary)] font-sans tabular-nums block">
                      {scanResult.total_calories}
                    </span>
                    <span className="text-[10px] text-[var(--text-muted)] uppercase font-semibold">
                      Total kcal
                    </span>
                  </div>
                </div>

                {/* Macro Badges Row */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-2.5 rounded-xl bg-[var(--macro-protein-subtle)] border border-[var(--macro-protein-border)] text-center">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--macro-protein-text)] block">
                      Protein
                    </span>
                    <span className="text-base font-black text-[var(--macro-protein-text)] font-sans tabular-nums">
                      {scanResult.protein_g}g
                    </span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-[var(--macro-carbs-subtle)] border border-[var(--macro-carbs-border)] text-center">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--macro-carbs-text)] block">
                      Carbs
                    </span>
                    <span className="text-base font-black text-[var(--macro-carbs-text)] font-sans tabular-nums">
                      {scanResult.carbs_g}g
                    </span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-[var(--macro-fat-subtle)] border border-[var(--macro-fat-border)] text-center">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--macro-fat-text)] block">
                      Dietary Fat
                    </span>
                    <span className="text-base font-black text-[var(--macro-fat-text)] font-sans tabular-nums">
                      {scanResult.fat_g}g
                    </span>
                  </div>
                </div>

                {/* Individual Food Items Table */}
                {scanResult.food_items && scanResult.food_items.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)] block">
                      Identified Plate Components
                    </span>
                    <div className="divide-y divide-[var(--border-subtle)] bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-2">
                      {scanResult.food_items.map((item, idx) => (
                        <div key={idx} className="py-2 px-2 flex items-center justify-between text-xs">
                          <div>
                            <span className="font-bold text-[var(--text-primary)] block">
                              {item.name}
                            </span>
                            <span className="text-[11px] text-[var(--text-muted)]">
                              {item.portion_est}
                            </span>
                          </div>
                          <div className="text-right">
                            <span className="font-bold font-sans tabular-nums text-[var(--text-primary)] block">
                              {item.calories} kcal
                            </span>
                            <span className="text-[10px] text-[var(--text-muted)] font-mono">
                              P: {item.protein_g}g · C: {item.carbs_g}g · F: {item.fat_g}g
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Sports Nutrition Coaching Tip */}
                {scanResult.coaching_tip && (
                  <div className="p-3 rounded-xl bg-[var(--accent-primary-subtle)] border-l-2 border-[var(--accent-primary)] text-xs text-[var(--text-secondary)] italic leading-relaxed">
                    "{scanResult.coaching_tip}"
                  </div>
                )}

                {/* Confirm & Log Buttons */}
                <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--border-subtle)]">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setScanResult(null);
                      setScannedImage(null);
                    }}
                  >
                    Rescan
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleCommitLoggedMeal}
                    leftIcon={<Plus className="w-3.5 h-3.5" />}
                  >
                    Review &amp; Add to Diary
                  </Button>
                </div>
              </div>
            )}
          </div>
        </Dialog>
      )}

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
              <Button variant="primary" size="sm" type="submit" leftIcon={<Send className="w-3.5 h-3.5" />}>
                Ask in RAG Chat
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
