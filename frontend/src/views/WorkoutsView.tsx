/**
 * src/views/WorkoutsView.tsx
 * Complete redesign of Workout Planner & Exercise Library:
 * - Two top-level tabs: "My routine" & "Exercise library" (solves Problem #9)
 * - My routine: Sticky left split config + right day cards with "Start in Tracker" button
 * - Weekly sets per muscle chart with shaded 10-20 target hypertrophy range
 * - Generator warnings banner
 * - Exercise Library: Search, muscle/equipment filter chips, 3-col card grid, difficulty badges
 * - Deep-dive Exercise Drawer: setup steps, form cues, common mistakes, injury prevention, Q&A
 * - Dismissible somatotype guidance tip card with CTA if unknown
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProfile } from '../context/ProfileContext';
import {
  getCatalogExercises,
  generateRoutine,
  getFormCue,
  getBodyTypeGuidance,
  getAISuggestExercise,
} from '../api/client';
import {
  PageHeader,
  Card,
  Tabs,
  TabContent,
  SegmentedControl,
  Button,
  Badge,
  Drawer,
  Dialog,
  Field,
  Select,
  Skeleton,
  Toast,
} from '../design';
import {
  Dumbbell,
  Search,
  Filter,
  Sparkles,
  ChevronRight,
  AlertTriangle,
  Play,
  X,
  BookOpen,
  Info,
  Calendar,
  Layers,
  Send,
  Loader2,
  CheckCircle2,
  ShieldAlert,
  ArrowLeftRight,
  Plus,
  Trash2,
  RotateCcw,
  Check,
  Edit3,
} from 'lucide-react';


const MUSCLE_GROUPS = ['all', 'chest', 'back', 'quads', 'hamstrings', 'delts', 'arms', 'core'];
const EQUIPMENT_TYPES = ['all', 'barbell', 'dumbbell', 'cables', 'bodyweight'];

interface ExerciseCatalogItem {
  id: string;
  name: string;
  primary_muscle: string;
  secondary_muscles: string[];
  equipment: string;
  movement_pattern: string;
  difficulty: 'beginner' | 'intermediate' | 'advanced';
}

interface RoutineDayExercise {
  exercise_id: string;
  exercise_name: string;
  name?: string;
  primary_muscle: string;
  sets: number;
  rep_range: string;
  rpe_target: number;
  rest_sec: number;
  rest_seconds?: number;
}


interface RoutineDay {
  day_number: number;
  name: string;
  focus: string;
  exercises: RoutineDayExercise[];
}

interface RoutineResult {
  split_type: string;
  days_per_week: number;
  days: RoutineDay[];
  weekly_volume_per_muscle: Record<string, number>;
  warnings?: string[];
}

export function WorkoutsView() {
  const { profile } = useProfile();
  const navigate = useNavigate();

  // Top Tab: "My routine" or "Exercise library"
  const [activeTab, setActiveTab] = useState<'routine' | 'library'>('routine');

  // Exercise Catalog State
  const [exercises, setExercises] = useState<ExerciseCatalogItem[]>([]);
  const [selectedMuscle, setSelectedMuscle] = useState<string>('all');
  const [selectedEquipment, setSelectedEquipment] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isLoadingCatalog, setIsLoadingCatalog] = useState<boolean>(false);

  // Exercise Drawer State
  const [activeExercise, setActiveExercise] = useState<ExerciseCatalogItem | null>(null);
  const [formCueQuestion, setFormCueQuestion] = useState<string>('');
  const [cueResult, setCueResult] = useState<any>(null);
  const [isLoadingCues, setIsLoadingCues] = useState<boolean>(false);

  // Routine Generator State (persisted via localStorage)
  const [split, setSplit] = useState<string>(() => {
    return localStorage.getItem('fitbot_routine_split') || 'push_pull_legs';
  });
  const [daysPerWeek, setDaysPerWeek] = useState<number>(() => {
    const saved = localStorage.getItem('fitbot_routine_days_per_week');
    return saved ? Number(saved) : 4;
  });
  const [routineResult, setRoutineResult] = useState<RoutineResult | null>(() => {
    const saved = localStorage.getItem('fitbot_saved_routine');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        return null;
      }
    }
    return null;
  });
  const [isGenerating, setIsGenerating] = useState<boolean>(false);

  // Swap / Add Exercise Modal State
  const [swapModal, setSwapModal] = useState<{
    isOpen: boolean;
    mode: 'swap' | 'add';
    dayIndex: number;
    exerciseIndex?: number;
    currentExercise?: any;
  } | null>(null);

  const [modalSearch, setModalSearch] = useState<string>('');
  const [modalMuscle, setModalMuscle] = useState<string>('all');
  const [modalEquipment, setModalEquipment] = useState<string>('all');

  // Edit Sets & Reps Modal State
  const [editSetsModal, setEditSetsModal] = useState<{
    isOpen: boolean;
    dayIndex: number;
    exerciseIndex: number;
    exerciseName: string;
    muscle: string;
    sets: number;
    repRange: string;
    restSec: number;
  } | null>(null);

  // AI Suggest Routine State
  const [isAnalyzingRoutine, setIsAnalyzingRoutine] = useState<boolean>(false);
  const [aiSuggestResult, setAiSuggestResult] = useState<{
    isOpen: boolean;
    isAllGood: boolean;
    message: string;
    suggestedExercise?: {
      exercise_id: string;
      name: string;
      primary_muscle: string;
      equipment: string;
      day_index: number;
      day_name: string;
      sets: number;
      rep_range: string;
      reason: string;
    } | null;
    volumeAnalysis?: any;
  } | null>(null);

  // Somatotype Tip State
  const [bodyTypeGuidance, setBodyTypeGuidance] = useState<{ somatotype: string; guidance: string } | null>(null);
  const [isTipDismissed, setIsTipDismissed] = useState<boolean>(false);

  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const loadExercises = async () => {
    setIsLoadingCatalog(true);
    try {
      const filters: any = {};
      if (selectedMuscle !== 'all') filters.muscle = selectedMuscle;
      if (selectedEquipment !== 'all') filters.equipment = selectedEquipment;
      if (searchQuery.trim()) filters.q = searchQuery.trim();

      const data = await getCatalogExercises(filters);
      setExercises(data);
    } catch (err: any) {
      setToast({ type: 'error', message: err.message || 'Failed to load exercises' });
    } finally {
      setIsLoadingCatalog(false);
    }
  };

  const loadBodyType = async () => {
    try {
      const data = await getBodyTypeGuidance();
      setBodyTypeGuidance(data);
    } catch (err) {
      console.error('Failed to load body type guidance:', err);
    }
  };

  useEffect(() => {
    loadExercises();
    loadBodyType();
    // Only generate if no saved routine in storage
    const saved = localStorage.getItem('fitbot_saved_routine');
    if (!saved) {
      handleGenerateRoutine();
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadExercises();
    }, 200);
    return () => clearTimeout(timer);
  }, [selectedMuscle, selectedEquipment, searchQuery]);


  const recalculateVolume = (days: RoutineDay[]): Record<string, number> => {
    const map: Record<string, number> = {};
    for (const d of days) {
      for (const ex of d.exercises) {
        const m = ex.primary_muscle || 'other';
        map[m] = (map[m] || 0) + (Number(ex.sets) || 0);
      }
    }
    return map;
  };

  const saveRoutine = (updatedRoutine: RoutineResult) => {
    setRoutineResult(updatedRoutine);
    localStorage.setItem('fitbot_saved_routine', JSON.stringify(updatedRoutine));
  };

  const handleGenerateRoutine = async (splitParam?: string, daysParam?: number) => {
    const targetSplit = splitParam || split;
    const targetDays = daysParam || daysPerWeek;
    setIsGenerating(true);
    try {
      const data = await generateRoutine({
        split: targetSplit,
        days_per_week: Number(targetDays),
        experience_level: profile?.experience_level || 'intermediate',
        goal: profile?.goal || 'hypertrophy',
        available_equipment: ['barbell', 'dumbbell', 'cables', 'bodyweight'],
      });
      setRoutineResult(data);
      localStorage.setItem('fitbot_routine_split', targetSplit);
      localStorage.setItem('fitbot_routine_days_per_week', String(targetDays));
      localStorage.setItem('fitbot_saved_routine', JSON.stringify(data));
      setToast({ type: 'success', message: 'New routine generated and saved to your profile!' });
    } catch (err: any) {
      setToast({ type: 'error', message: err.message || 'Failed to generate routine' });
    } finally {
      setIsGenerating(false);
    }
  };

  const openSwapModal = (mode: 'swap' | 'add', dayIndex: number, exerciseIndex?: number, currentExercise?: any) => {
    setModalSearch('');
    setModalEquipment('all');
    setModalMuscle(currentExercise?.primary_muscle || 'all');
    setSwapModal({
      isOpen: true,
      mode,
      dayIndex,
      exerciseIndex,
      currentExercise,
    });
  };

  const handleSelectAlternativeExercise = (newEx: ExerciseCatalogItem) => {
    if (!routineResult || !swapModal) return;

    const days = [...routineResult.days];
    const targetDay = { ...days[swapModal.dayIndex] };
    const exercisesList = [...targetDay.exercises];

    if (swapModal.mode === 'swap' && typeof swapModal.exerciseIndex === 'number') {
      const curr = exercisesList[swapModal.exerciseIndex];
      exercisesList[swapModal.exerciseIndex] = {
        exercise_id: newEx.id,
        exercise_name: newEx.name,
        name: newEx.name,
        primary_muscle: newEx.primary_muscle,
        sets: curr?.sets || 3,
        rep_range: curr?.rep_range || '8-12',
        rpe_target: curr?.rpe_target || 8,
        rest_sec: curr?.rest_sec || 90,
        rest_seconds: curr?.rest_seconds || 90,
      };
      setToast({ type: 'success', message: `Swapped to ${newEx.name}` });
    } else if (swapModal.mode === 'add') {
      exercisesList.push({
        exercise_id: newEx.id,
        exercise_name: newEx.name,
        name: newEx.name,
        primary_muscle: newEx.primary_muscle,
        sets: 3,
        rep_range: '8-12',
        rpe_target: 8,
        rest_sec: 90,
        rest_seconds: 90,
      });
      setToast({ type: 'success', message: `Added ${newEx.name} to Day ${swapModal.dayIndex + 1}` });
    }

    targetDay.exercises = exercisesList;
    days[swapModal.dayIndex] = targetDay;

    const updatedVolume = recalculateVolume(days);
    const updatedRoutine: RoutineResult = {
      ...routineResult,
      days,
      weekly_volume_per_muscle: updatedVolume,
    };

    saveRoutine(updatedRoutine);
    setSwapModal(null);
  };

  const handleRemoveExercise = (dayIdx: number, exIdx: number) => {
    if (!routineResult) return;
    const days = [...routineResult.days];
    const targetDay = { ...days[dayIdx] };
    const exercisesList = [...targetDay.exercises];
    const removed = exercisesList.splice(exIdx, 1)[0];
    targetDay.exercises = exercisesList;
    days[dayIdx] = targetDay;

    const updatedVolume = recalculateVolume(days);
    const updatedRoutine: RoutineResult = {
      ...routineResult,
      days,
      weekly_volume_per_muscle: updatedVolume,
    };

    saveRoutine(updatedRoutine);
    setToast({
      type: 'success',
      message: `Removed ${removed?.name || (removed as any)?.exercise_name || 'exercise'}`,
    });
  };

  const openEditSetsModal = (dayIndex: number, exerciseIndex: number, ex: any) => {
    setEditSetsModal({
      isOpen: true,
      dayIndex,
      exerciseIndex,
      exerciseName: ex.name || ex.exercise_name || 'Exercise',
      muscle: ex.primary_muscle || '',
      sets: Number(ex.sets) || 3,
      repRange: ex.rep_range || '8-12',
      restSec: Number(ex.rest_seconds || ex.rest_sec) || 90,
    });
  };

  const handleSaveCustomSetsReps = () => {
    if (!routineResult || !editSetsModal) return;

    const days = [...routineResult.days];
    const targetDay = { ...days[editSetsModal.dayIndex] };
    const exercisesList = [...targetDay.exercises];
    const curr = { ...exercisesList[editSetsModal.exerciseIndex] };

    curr.sets = editSetsModal.sets;
    curr.rep_range = editSetsModal.repRange;
    curr.rest_sec = editSetsModal.restSec;
    curr.rest_seconds = editSetsModal.restSec;

    exercisesList[editSetsModal.exerciseIndex] = curr;
    targetDay.exercises = exercisesList;
    days[editSetsModal.dayIndex] = targetDay;

    const updatedVolume = recalculateVolume(days);
    const updatedRoutine: RoutineResult = {
      ...routineResult,
      days,
      weekly_volume_per_muscle: updatedVolume,
    };

    saveRoutine(updatedRoutine);
    setToast({
      type: 'success',
      message: `Updated ${curr.name || curr.exercise_name}: ${editSetsModal.sets} sets × ${editSetsModal.repRange}`,
    });
    setEditSetsModal(null);
  };

  const handleAISuggestExercise = async () => {
    if (!routineResult) {
      setToast({ type: 'error', message: 'Please generate or load a routine first.' });
      return;
    }
    setIsAnalyzingRoutine(true);
    try {
      const res = await getAISuggestExercise(
        routineResult,
        profile?.goal || 'hypertrophy',
        profile?.experience_level || 'intermediate'
      );
      setAiSuggestResult({
        isOpen: true,
        isAllGood: res.is_all_good,
        message: res.message,
        suggestedExercise: res.suggested_exercise,
        volumeAnalysis: res.volume_analysis,
      });
    } catch (err: any) {
      setToast({ type: 'error', message: err.message || 'Failed to analyze routine' });
    } finally {
      setIsAnalyzingRoutine(false);
    }
  };

  const handleApplyAISuggestion = () => {
    if (!routineResult || !aiSuggestResult?.suggestedExercise) return;
    const sug = aiSuggestResult.suggestedExercise;

    const days = [...routineResult.days];
    const targetDayIdx = Math.min(sug.day_index, days.length - 1);
    const targetDay = { ...days[targetDayIdx] };
    const exercisesList = [...targetDay.exercises];

    exercisesList.push({
      exercise_id: sug.exercise_id,
      exercise_name: sug.name,
      name: sug.name,
      primary_muscle: sug.primary_muscle,
      sets: sug.sets || 3,
      rep_range: sug.rep_range || '8-12',
      rpe_target: 8,
      rest_sec: 90,
      rest_seconds: 90,
    });

    targetDay.exercises = exercisesList;
    days[targetDayIdx] = targetDay;

    const updatedVolume = recalculateVolume(days);
    const updatedRoutine: RoutineResult = {
      ...routineResult,
      days,
      weekly_volume_per_muscle: updatedVolume,
    };

    saveRoutine(updatedRoutine);
    setToast({
      type: 'success',
      message: `Added ${sug.name} to Day ${targetDayIdx + 1}!`,
    });
    setAiSuggestResult(null);
  };

  const openExerciseDrawer = async (ex: ExerciseCatalogItem) => {
    setActiveExercise(ex);
    setFormCueQuestion('');
    setCueResult(null);
    setIsLoadingCues(true);
    try {
      const res = await getFormCue(ex.id);
      setCueResult(res);
    } catch (err) {
      console.error('Failed to get form cues:', err);
    } finally {
      setIsLoadingCues(false);
    }
  };

  const handleAskFormCue = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!activeExercise) return;
    const q = formCueQuestion.trim()
      ? `${activeExercise.name}: ${formCueQuestion.trim()}`
      : `What are the proper technique cues, active execution steps, and common mistakes to avoid for ${activeExercise.name}?`;

    setActiveExercise(null);
    navigate('/coach', { state: { initialPrompt: q } });
  };

  const handleStartInTracker = (day: RoutineDay) => {
    navigate('/tracker', {
      state: { preloadedExercises: day.exercises.map((e) => e.exercise_id) },
    });
  };

  return (
    <div className="flex-1 overflow-y-auto bg-[var(--bg-app)] text-[var(--text-primary)] p-6 sm:p-10 transition-colors duration-200">
      <div className="max-w-[1200px] mx-auto space-y-8 pb-20">
        {/* Page Header with Top Tabs */}
        <PageHeader
          title="Workout Planner & Exercise Catalog"
          description="Deterministic hypertrophy routines calibrated by muscle group volume and verified biomechanical form cues."
          badge={<Badge variant="accent">Volume Periodization</Badge>}
        />

        {/* Top Two Tabs: "My routine" & "Exercise library" */}
        <Tabs
          value={activeTab}
          onChange={(val) => setActiveTab(val as 'routine' | 'library')}
          tabs={[
            { id: 'routine', label: 'My Routine', icon: <Layers className="w-4 h-4" /> },
            { id: 'library', label: 'Exercise Library', icon: <Dumbbell className="w-4 h-4" /> },
          ]}
        />

        {/* Tab 1: My Routine */}
        {activeTab === 'routine' && (
          <div className="space-y-6">
            {/* Somatotype Tip Card (Dismissible) */}
            {!isTipDismissed && bodyTypeGuidance && (
              <div className="p-4 rounded-2xl bg-[var(--accent-primary-subtle)] border border-[var(--accent-primary-border)] flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <Sparkles className="w-5 h-5 text-[var(--accent-primary)] shrink-0 mt-0.5" />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-[var(--accent-text)]">
                        Somatotype Guidance: {bodyTypeGuidance.somatotype}
                      </span>
                      {bodyTypeGuidance.somatotype === 'unknown' && (
                        <button
                          type="button"
                          onClick={() => navigate('/profile')}
                          className="text-[11px] font-semibold text-[var(--accent-primary)] hover:underline ml-2"
                        >
                          Set your body type in Profile →
                        </button>
                      )}
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
                      {bodyTypeGuidance.guidance}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setIsTipDismissed(true)}
                  aria-label="Dismiss tip"
                  className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 rounded-lg"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}

            {/* Generator Warnings Banner */}
            {routineResult?.warnings && routineResult.warnings.length > 0 && (
              <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                <div>
                  <span className="text-xs font-bold uppercase tracking-wider text-amber-500">
                    Generator Notice
                  </span>
                  <div className="space-y-1 mt-1 text-xs text-[var(--text-secondary)]">
                    {routineResult.warnings.map((w, idx) => (
                      <p key={idx}>{w}</p>
                    ))}
                  </div>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              {/* Left Column: Sticky Split Configuration Panel (4 cols) */}
              <div className="lg:col-span-4 lg:sticky lg:top-6 space-y-6">
                <Card
                  title="Split Configuration"
                  subtitle="Choose your weekly frequency and training archetype."
                >
                  <div className="space-y-5">
                    <Select
                      label="Training Split"
                      value={split}
                      onChange={(e) => setSplit(e.target.value)}
                      options={[
                        { value: 'push_pull_legs', label: 'Push / Pull / Legs', hint: 'Hypertrophy optimal' },
                        { value: 'upper_lower', label: 'Upper / Lower', hint: 'Balanced 4-day' },
                        { value: 'full_body', label: 'Full Body', hint: '3-day efficiency' },
                      ]}
                    />

                    <div>
                      <label className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] block mb-2">
                        Frequency (Days / Week)
                      </label>
                      <SegmentedControl
                        value={daysPerWeek}
                        onChange={(v) => setDaysPerWeek(Number(v))}
                        options={[
                          { value: 3, label: '3 Days' },
                          { value: 4, label: '4 Days' },
                          { value: 5, label: '5 Days' },
                          { value: 6, label: '6 Days' },
                        ]}
                      />
                    </div>

                    <div className="pt-2 flex items-center gap-2">
                      <Button
                        variant="primary"
                        size="md"
                        onClick={() => handleGenerateRoutine()}
                        isLoading={isGenerating}
                        className="flex-1"
                        leftIcon={<Sparkles className="w-4 h-4" />}
                      >
                        Generate Routine
                      </Button>
                      <Button
                        variant="secondary"
                        size="md"
                        onClick={() => {
                          localStorage.removeItem('fitbot_saved_routine');
                          handleGenerateRoutine();
                        }}
                        title="Reset to algorithmic defaults"
                        leftIcon={<RotateCcw className="w-4 h-4" />}
                      >
                        Reset
                      </Button>
                    </div>
                  </div>
                </Card>

                {/* Weekly Sets Per Muscle Distribution Chart */}
                {routineResult?.weekly_volume_per_muscle && (
                  <Card
                    title="Hypertrophy Volume Matrix"
                    subtitle="Weekly effective sets per muscle group. Target: 10–20 sets."
                  >
                    <div className="space-y-3">
                      {Object.entries(routineResult.weekly_volume_per_muscle).map(([muscle, sets]) => {
                        const inRange = sets >= 10 && sets <= 20;
                        const pct = Math.min(100, Math.round((sets / 20) * 100));

                        return (
                          <div key={muscle} className="space-y-1 text-xs">
                            <div className="flex justify-between items-center">
                              <span className="font-semibold capitalize text-[var(--text-primary)]">
                                {muscle}
                              </span>
                              <div className="flex items-center gap-2">
                                <span className="font-sans tabular-nums font-bold text-[var(--text-primary)]">
                                  {sets} sets
                                </span>
                                <Badge variant={inRange ? 'success' : sets > 20 ? 'warning' : 'neutral'} size="sm">
                                  {inRange ? 'Optimal' : sets > 20 ? 'High' : 'Under 10'}
                                </Badge>
                              </div>
                            </div>
                            <div className="w-full bg-[var(--bg-subtle)] h-2 rounded-full overflow-hidden">
                              <div
                                style={{ width: `${pct}%` }}
                                className={`h-full rounded-full transition-all duration-300 ${
                                  inRange ? 'bg-emerald-500' : sets > 20 ? 'bg-amber-500' : 'bg-[var(--accent-primary)]'
                                }`}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </Card>
                )}
              </div>

              {/* Right Column: Routine Day Cards (8 cols) */}
              <div className="lg:col-span-8 space-y-6">
                {/* AI Routine Assistant Card / Action */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[var(--bg-card)] p-4 rounded-2xl border border-[var(--border-subtle)] shadow-xs">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-[var(--accent-primary-subtle)] text-[var(--accent-text)] flex items-center justify-center font-bold">
                      <Sparkles className="w-4 h-4" />
                    </div>
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                        AI Routine Assistant
                      </h4>
                      <p className="text-[11px] text-[var(--text-muted)]">
                        Analyze muscle volume balance and discover missing exercises
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleAISuggestExercise}
                    disabled={isAnalyzingRoutine || !routineResult}
                    leftIcon={isAnalyzingRoutine ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                  >
                    {isAnalyzingRoutine ? 'Analyzing Routine...' : 'AI Suggest Exercise'}
                  </Button>
                </div>

                {isGenerating ? (
                  <div className="space-y-4">
                    <Skeleton variant="card" height={160} />
                    <Skeleton variant="card" height={160} />
                    <Skeleton variant="card" height={160} />
                  </div>
                ) : routineResult?.days ? (
                  <div className="space-y-6">
                    {routineResult.days.map((day, dIdx) => (
                      <Card
                        key={dIdx}
                        title={`Day ${dIdx + 1}: ${day.name}`}
                        subtitle={day.focus}
                        action={
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => handleStartInTracker(day)}
                            leftIcon={<Play className="w-3.5 h-3.5" />}
                          >
                            Start in Tracker
                          </Button>
                        }
                      >
                        <div className="space-y-3">
                          <div className="divide-y divide-[var(--border-subtle)]">
                            {day.exercises.map((ex: any, exIdx: number) => (
                              <div
                                key={exIdx}
                                onClick={() => {
                                  const found = exercises.find((e) => e.id === ex.exercise_id);
                                  if (found) openExerciseDrawer(found);
                                }}
                                className="py-3 sm:py-3.5 flex items-center justify-between gap-3 group cursor-pointer hover:bg-[var(--bg-subtle)]/40 px-2 rounded-xl transition-colors"
                              >
                                <div className="min-w-0 flex-1">
                                  <span className="text-sm font-bold text-[var(--text-primary)] group-hover:text-[var(--accent-text)] transition-colors truncate block">
                                    {ex.name || ex.exercise_name}
                                  </span>
                                  <div className="flex items-center gap-2 mt-1">
                                    <Badge variant="neutral" size="sm">
                                      {ex.primary_muscle}
                                    </Badge>
                                    <span className="text-xs text-[var(--text-muted)]">
                                      Rest: {ex.rest_seconds || ex.rest_sec || 90}s
                                    </span>
                                  </div>
                                </div>

                                <div className="flex items-center gap-2 shrink-0">
                                  {/* Clickable Sets & Reps badge with direct customization dialog */}
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      openEditSetsModal(dIdx, exIdx, ex);
                                    }}
                                    title="Click to customize sets and reps"
                                    className="group/badge inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[var(--accent-primary-subtle)] hover:bg-[var(--accent-primary)]/20 border border-[var(--accent-primary)]/30 text-[var(--accent-text)] font-mono text-xs font-bold transition-all cursor-pointer"
                                  >
                                    <span>{ex.sets} × {ex.rep_range}</span>
                                    <Edit3 className="w-3 h-3 opacity-60 group-hover/badge:opacity-100 transition-opacity" />
                                  </button>
                                  <Button
                                    variant="secondary"
                                    size="xs"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      openSwapModal('swap', dIdx, exIdx, ex);
                                    }}
                                    leftIcon={<ArrowLeftRight className="w-3 h-3" />}
                                  >
                                    Swap
                                  </Button>
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleRemoveExercise(dIdx, exIdx);
                                    }}
                                    title="Remove exercise from day"
                                    className="p-1.5 text-[var(--text-muted)] hover:text-red-500 hover:bg-red-500/10 rounded-lg transition-colors cursor-pointer"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                  <ChevronRight className="w-4 h-4 text-[var(--text-muted)] group-hover:text-[var(--text-primary)] group-hover:translate-x-0.5 transition-transform" />
                                </div>
                              </div>
                            ))}
                          </div>

                          <div className="pt-2 border-t border-[var(--border-subtle)]">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openSwapModal('add', dIdx)}
                              leftIcon={<Plus className="w-3.5 h-3.5" />}
                              className="w-full border border-dashed border-[var(--border-subtle)] hover:border-[var(--accent-primary)] hover:bg-[var(--accent-primary-subtle)] text-xs font-semibold py-2"
                            >
                              Add Exercise to Day {dIdx + 1}
                            </Button>
                          </div>
                        </div>
                      </Card>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Exercise Library */}
        {activeTab === 'library' && (
          <div className="space-y-6">
            {/* Search and Filter Chips */}
            <Card>
              <div className="space-y-4">
                {/* Search Input */}
                <div className="relative">
                  <Search className="w-4 h-4 text-[var(--text-muted)] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search exercise by name or movement pattern..."
                    className="w-full bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-primary)] text-sm rounded-xl pl-10 pr-4 py-2.5 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)]"
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={() => setSearchQuery('')}
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>

                {/* Muscle Group Filter Chips */}
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] block mb-2">
                    Filter by Muscle Group
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {MUSCLE_GROUPS.map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setSelectedMuscle(m)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-semibold capitalize transition-all cursor-pointer ${
                          selectedMuscle === m
                            ? 'bg-[var(--accent-primary)] text-white shadow-xs'
                            : 'bg-[var(--bg-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-subtle)]'
                        }`}
                      >
                        {m}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Equipment Filter Chips */}
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] block mb-2">
                    Filter by Equipment
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {EQUIPMENT_TYPES.map((eq) => (
                      <button
                        key={eq}
                        type="button"
                        onClick={() => setSelectedEquipment(eq)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-semibold capitalize transition-all cursor-pointer ${
                          selectedEquipment === eq
                            ? 'bg-[var(--accent-primary)] text-white shadow-xs'
                            : 'bg-[var(--bg-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-subtle)]'
                        }`}
                      >
                        {eq}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </Card>

            {/* Exercise 3-Column Grid */}
            {isLoadingCatalog ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} variant="card" height={140} />
                ))}
              </div>
            ) : exercises.length === 0 ? (
              <div className="p-12 text-center text-sm text-[var(--text-muted)]">
                No exercises found matching your search and filter criteria.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {exercises.map((ex) => (
                  <div
                    key={ex.id}
                    onClick={() => openExerciseDrawer(ex)}
                    className="p-4 sm:p-5 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] hover:border-[var(--border-prominent)] shadow-xs hover:shadow-md transition-all cursor-pointer flex flex-col justify-between group"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <Badge variant="protein" size="sm">
                          {ex.primary_muscle}
                        </Badge>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] capitalize">
                          {ex.difficulty}
                        </span>
                      </div>
                      <h4 className="text-sm sm:text-base font-bold text-[var(--text-primary)] group-hover:text-[var(--accent-text)] transition-colors">
                        {ex.name}
                      </h4>
                      <p className="text-xs text-[var(--text-secondary)] mt-1 capitalize">
                        {ex.equipment} · {ex.movement_pattern.replace('_', ' ')}
                      </p>
                    </div>

                    <div className="pt-3 mt-3 border-t border-[var(--border-subtle)] flex items-center justify-between text-xs text-[var(--accent-text)] font-semibold">
                      <span>View Technique Cues</span>
                      <ChevronRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Exercise Swap / Add Modal */}
      {swapModal?.isOpen && (

        <Dialog
          isOpen={swapModal.isOpen}
          onClose={() => setSwapModal(null)}
          title={
            swapModal.mode === 'swap'
              ? `Swap: ${swapModal.currentExercise?.name || swapModal.currentExercise?.exercise_name || 'Exercise'}`
              : `Add Exercise: Day ${swapModal.dayIndex + 1}`
          }
          description={
            swapModal.mode === 'swap'
              ? `Select an alternative exercise for ${swapModal.currentExercise?.primary_muscle || 'this target muscle'}.`
              : 'Choose an exercise from the library to add to this workout session.'
          }
          maxWidth="lg"
        >
          <div className="space-y-4">
            {/* Search Input */}
            <div className="relative">
              <Search className="w-4 h-4 text-[var(--text-muted)] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                value={modalSearch}
                onChange={(e) => setModalSearch(e.target.value)}
                placeholder="Search exercise by name..."
                className="w-full bg-[var(--bg-subtle)] border border-[var(--border-subtle)] rounded-xl pl-10 pr-4 py-2.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)]"
              />
            </div>

            {/* Muscle Filter Chips */}
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] block mb-1.5">
                Target Muscle
              </span>
              <div className="flex flex-wrap gap-1.5">
                {MUSCLE_GROUPS.map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setModalMuscle(m)}
                    className={`px-2.5 py-1 text-xs font-semibold rounded-lg capitalize transition-colors cursor-pointer ${
                      modalMuscle === m
                        ? 'bg-[var(--accent-primary)] text-white'
                        : 'bg-[var(--bg-subtle)] text-[var(--text-secondary)] hover:bg-[var(--bg-card-hover)]'
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>

            {/* Equipment Filter Chips */}
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] block mb-1.5">
                Equipment
              </span>
              <div className="flex flex-wrap gap-1.5">
                {EQUIPMENT_TYPES.map((eq) => (
                  <button
                    key={eq}
                    type="button"
                    onClick={() => setModalEquipment(eq)}
                    className={`px-2.5 py-1 text-xs font-semibold rounded-lg capitalize transition-colors cursor-pointer ${
                      modalEquipment === eq
                        ? 'bg-[var(--accent-primary)] text-white'
                        : 'bg-[var(--bg-subtle)] text-[var(--text-secondary)] hover:bg-[var(--bg-card-hover)]'
                    }`}
                  >
                    {eq}
                  </button>
                ))}
              </div>
            </div>

            {/* Matching Exercises List */}
            <div className="max-h-72 overflow-y-auto divide-y divide-[var(--border-subtle)] pr-1">
              {exercises
                .filter((ex) => {
                  if (modalMuscle !== 'all' && ex.primary_muscle !== modalMuscle) return false;
                  if (modalEquipment !== 'all' && ex.equipment !== modalEquipment) return false;
                  if (modalSearch.trim()) {
                    return ex.name.toLowerCase().includes(modalSearch.toLowerCase());
                  }
                  return true;
                })
                .map((ex) => {
                  const isCurrent =
                    swapModal.mode === 'swap' &&
                    swapModal.currentExercise?.exercise_id === ex.id;

                  return (
                    <div
                      key={ex.id}
                      onClick={() => !isCurrent && handleSelectAlternativeExercise(ex)}
                      className={`py-3 px-3 rounded-xl flex items-center justify-between gap-4 transition-colors ${
                        isCurrent
                          ? 'bg-[var(--accent-primary-subtle)]/50 cursor-default opacity-80'
                          : 'hover:bg-[var(--bg-subtle)] cursor-pointer'
                      }`}
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-[var(--text-primary)]">
                            {ex.name}
                          </span>
                          {isCurrent && (
                            <Badge variant="accent" size="sm">
                              Current
                            </Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant="neutral" size="sm">
                            {ex.primary_muscle}
                          </Badge>
                          <span className="text-[11px] text-[var(--text-muted)] capitalize">
                            {ex.equipment}
                          </span>
                        </div>
                      </div>

                      <div>
                        {isCurrent ? (
                          <span className="text-xs text-[var(--text-muted)] font-medium">Selected</span>
                        ) : (
                          <Button variant="secondary" size="xs">
                            Select
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </Dialog>
      )}

      {/* Customize Sets & Reps Modal */}
      {editSetsModal && (
        <Dialog
          isOpen={editSetsModal.isOpen}
          onClose={() => setEditSetsModal(null)}
          title={`Customize ${editSetsModal.exerciseName}`}
          description={
            <span className="capitalize text-xs text-[var(--accent-text)] font-semibold">
              {editSetsModal.muscle} target · Adjust volume and repetition range
            </span>
          }
          maxWidth="sm"
        >
          <div className="space-y-5 pt-2">
            {/* Sets Stepper */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                  Working Sets
                </label>
                <span className="text-xs font-mono font-bold text-[var(--accent-text)]">
                  {editSetsModal.sets} {editSetsModal.sets === 1 ? 'set' : 'sets'}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setEditSetsModal(prev => prev ? { ...prev, sets: Math.max(1, prev.sets - 1) } : null)}
                  disabled={editSetsModal.sets <= 1}
                  className="w-10 h-10 rounded-xl bg-[var(--bg-subtle)] hover:bg-[var(--accent-primary-subtle)] border border-[var(--border-subtle)] flex items-center justify-center text-[var(--text-primary)] hover:text-[var(--accent-text)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-bold text-lg cursor-pointer"
                >
                  -
                </button>
                <div className="flex-1 py-2 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)] text-center font-bold text-lg text-[var(--text-primary)] font-mono">
                  {editSetsModal.sets}
                </div>
                <button
                  type="button"
                  onClick={() => setEditSetsModal(prev => prev ? { ...prev, sets: Math.min(10, prev.sets + 1) } : null)}
                  disabled={editSetsModal.sets >= 10}
                  className="w-10 h-10 rounded-xl bg-[var(--bg-subtle)] hover:bg-[var(--accent-primary-subtle)] border border-[var(--border-subtle)] flex items-center justify-center text-[var(--text-primary)] hover:text-[var(--accent-text)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-bold text-lg cursor-pointer"
                >
                  +
                </button>
              </div>
            </div>

            {/* Rep Range Selection */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                  Target Rep Range
                </label>
                <span className="text-xs font-mono font-bold text-[var(--text-primary)]">
                  {editSetsModal.repRange} reps
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                {['5', '6-8', '8-12', '10-12', '12-15', '15-20'].map((range) => (
                  <button
                    key={range}
                    type="button"
                    onClick={() => setEditSetsModal(prev => prev ? { ...prev, repRange: range } : null)}
                    className={`py-2 px-2 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${
                      editSetsModal.repRange === range
                        ? 'bg-[var(--accent-primary)] text-white border-[var(--accent-primary)] shadow-xs'
                        : 'bg-[var(--bg-subtle)] text-[var(--text-secondary)] border-[var(--border-subtle)] hover:border-[var(--accent-primary)]/50'
                    }`}
                  >
                    {range}
                  </button>
                ))}
              </div>
              <input
                type="text"
                value={editSetsModal.repRange}
                onChange={(e) => setEditSetsModal(prev => prev ? { ...prev, repRange: e.target.value } : null)}
                placeholder="Custom rep range (e.g. 5x5, 10-12)"
                className="w-full mt-1 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-xl px-3 py-2 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)]"
              />
            </div>

            {/* Rest Seconds */}
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] block">
                Rest Between Sets
              </label>
              <div className="grid grid-cols-4 gap-2">
                {[60, 90, 120, 180].map((sec) => (
                  <button
                    key={sec}
                    type="button"
                    onClick={() => setEditSetsModal(prev => prev ? { ...prev, restSec: sec } : null)}
                    className={`py-2 px-2 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${
                      editSetsModal.restSec === sec
                        ? 'bg-[var(--accent-primary)] text-white border-[var(--accent-primary)] shadow-xs'
                        : 'bg-[var(--bg-subtle)] text-[var(--text-secondary)] border-[var(--border-subtle)] hover:border-[var(--accent-primary)]/50'
                    }`}
                  >
                    {sec}s
                  </button>
                ))}
              </div>
            </div>

            {/* Dialog Footer Actions */}
            <div className="flex justify-end gap-2 pt-4 border-t border-[var(--border-subtle)]">
              <Button variant="ghost" size="sm" onClick={() => setEditSetsModal(null)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleSaveCustomSetsReps}
                leftIcon={<Check className="w-3.5 h-3.5" />}
              >
                Save Changes
              </Button>
            </div>
          </div>
        </Dialog>
      )}

      {/* AI Suggest Routine Dialog */}
      {aiSuggestResult && (
        <Dialog
          isOpen={aiSuggestResult.isOpen}
          onClose={() => setAiSuggestResult(null)}
          title="AI Routine Coach Analysis"
          description="Evidence-based weekly volume & exercise balance evaluation"
          maxWidth="md"
        >
          <div className="space-y-5 pt-2">
            {aiSuggestResult.isAllGood ? (
              <div className="p-6 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-center space-y-3">
                <div className="w-12 h-12 rounded-full bg-emerald-500/20 text-emerald-400 mx-auto flex items-center justify-center">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <div>
                  <h4 className="text-base font-bold text-emerald-400">Everything Looks Great!</h4>
                  <p className="text-xs text-[var(--text-secondary)] mt-1.5 leading-relaxed max-w-md mx-auto">
                    {aiSuggestResult.message}
                  </p>
                </div>
                <div className="pt-2">
                  <Button variant="primary" size="sm" onClick={() => setAiSuggestResult(null)}>
                    Keep Current Routine
                  </Button>
                </div>
              </div>
            ) : aiSuggestResult.suggestedExercise ? (
              <div className="space-y-4">
                {/* Coach Alert */}
                <div className="p-4 rounded-xl bg-[var(--accent-primary-subtle)] border border-[var(--accent-primary)]/20 space-y-1">
                  <div className="flex items-center gap-2 text-xs font-bold text-[var(--accent-text)] uppercase tracking-wider">
                    <Sparkles className="w-4 h-4" /> Recommended Addition
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    {aiSuggestResult.message}
                  </p>
                </div>

                {/* Exercise Card Preview */}
                <div className="p-4 rounded-2xl bg-[var(--bg-subtle)] border border-[var(--border-subtle)] space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h4 className="text-base font-bold text-[var(--text-primary)]">
                        {aiSuggestResult.suggestedExercise.name}
                      </h4>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="accent" size="sm">
                          {aiSuggestResult.suggestedExercise.primary_muscle}
                        </Badge>
                        <Badge variant="neutral" size="sm">
                          {aiSuggestResult.suggestedExercise.equipment}
                        </Badge>
                        <span className="text-xs text-[var(--text-muted)] font-mono">
                          Add to: Day {aiSuggestResult.suggestedExercise.day_index + 1} ({aiSuggestResult.suggestedExercise.day_name})
                        </span>
                      </div>
                    </div>
                    <Badge variant="accent" size="md">
                      {aiSuggestResult.suggestedExercise.sets} sets × {aiSuggestResult.suggestedExercise.rep_range}
                    </Badge>
                  </div>

                  {/* Coach's Reasoning */}
                  <div className="p-3 rounded-xl bg-[var(--bg-card)] border-l-2 border-[var(--accent-primary)] text-xs text-[var(--text-secondary)] italic leading-relaxed">
                    "{aiSuggestResult.suggestedExercise.reason}"
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--border-subtle)]">
                  <Button variant="ghost" size="sm" onClick={() => setAiSuggestResult(null)}>
                    Not Now
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleApplyAISuggestion}
                    leftIcon={<Plus className="w-3.5 h-3.5" />}
                  >
                    Add to Day {aiSuggestResult.suggestedExercise.day_index + 1}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="p-4 text-center text-xs text-[var(--text-secondary)]">
                {aiSuggestResult.message}
              </div>
            )}
          </div>
        </Dialog>
      )}

      {/* Deep-Dive Exercise Drawer */}
      <Drawer

        isOpen={Boolean(activeExercise)}
        onClose={() => setActiveExercise(null)}
        title={activeExercise?.name || 'Exercise Details'}
        description={
          activeExercise ? (
            <span className="capitalize">
              {activeExercise.primary_muscle} · {activeExercise.equipment} · {activeExercise.movement_pattern}
            </span>
          ) : undefined
        }
      >
        {activeExercise && (
          <div className="space-y-6">
            {isLoadingCues && !cueResult ? (
              <div className="space-y-3">
                <Skeleton variant="card" height={100} />
                <Skeleton variant="card" height={100} />
              </div>
            ) : cueResult ? (
              <div className="space-y-5">
                {/* Setup & Execution */}
                {cueResult.setup && (
                  <div className="p-4 rounded-xl bg-[var(--bg-subtle)] space-y-2">
                    <h5 className="text-xs font-bold uppercase tracking-wider text-[var(--accent-text)] flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4" /> Setup & Biomechanics
                    </h5>
                    <p className="text-xs text-[var(--text-primary)] leading-relaxed whitespace-pre-wrap">
                      {cueResult.setup}
                    </p>
                  </div>
                )}

                {/* Form Cues */}
                {cueResult.form_cues && (
                  <div className="p-4 rounded-xl bg-[var(--bg-subtle)] space-y-2">
                    <h5 className="text-xs font-bold uppercase tracking-wider text-emerald-500 flex items-center gap-1.5">
                      <Sparkles className="w-4 h-4" /> Key Execution Cues
                    </h5>
                    <p className="text-xs text-[var(--text-primary)] leading-relaxed whitespace-pre-wrap">
                      {cueResult.form_cues}
                    </p>
                  </div>
                )}

                {/* Common Mistakes */}
                {cueResult.common_mistakes && (
                  <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 space-y-2">
                    <h5 className="text-xs font-bold uppercase tracking-wider text-amber-500 flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4" /> Common Mistakes
                    </h5>
                    <p className="text-xs text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap">
                      {cueResult.common_mistakes}
                    </p>
                  </div>
                )}

                {/* Injury Prevention */}
                {cueResult.injury_prevention && (
                  <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 space-y-2">
                    <h5 className="text-xs font-bold uppercase tracking-wider text-rose-500 flex items-center gap-1.5">
                      <ShieldAlert className="w-4 h-4" /> Injury Prevention
                    </h5>
                    <p className="text-xs text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap">
                      {cueResult.injury_prevention}
                    </p>
                  </div>
                )}
              </div>
            ) : null}

            {/* "Ask for more detail" form */}
            <form onSubmit={handleAskFormCue} className="space-y-3 pt-4 border-t border-[var(--border-subtle)]">
              <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] block">
                Ask specific question about this movement
              </label>
              <textarea
                rows={2}
                value={formCueQuestion}
                onChange={(e) => setFormCueQuestion(e.target.value)}
                placeholder="e.g. How to prevent shoulder impingement at the bottom of the movement?"
                className="w-full bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-xl p-3 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)] resize-none"
              />
              <div className="flex justify-end">
                <Button
                  variant="primary"
                  size="sm"
                  type="submit"
                  leftIcon={<Send className="w-3.5 h-3.5" />}
                >
                  Ask in RAG Chat
                </Button>
              </div>
            </form>
          </div>
        )}
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
