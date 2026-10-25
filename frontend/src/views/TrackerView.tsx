/**
 * src/views/TrackerView.tsx
 * Complete redesign of Overload Tracker:
 * - Top bar: Searchable Combobox + kg/lb SegmentedControl
 * - Left column (Today's session): Target recommendation card, set logger with steppers & RPE chips (6-10 in 0.5 steps with RIR), deviation warning, sticky finish bar (safe from mobile tab bar)
 * - Right column:
 *   - "Progress" tab: Estimated-1RM / top-set line chart (via Recharts) above chronological history table
 *   - "Weekly volume" tab: Bars per muscle group with shaded 10-20 target range, only counting committed sets
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts';
import {
  getCatalogExercises,
  getExerciseHistory,
  getPlateauDiagnosis,
  getRecommendation,
  getWeeklyVolume,
  logWorkoutSet,
} from '../api/client';
import {
  PageHeader,
  Card,
  Tabs,
  TabContent,
  SegmentedControl,
  Stepper,
  Combobox,
  Button,
  Badge,
  Skeleton,
  EmptyState,
  Toast,
} from '../design';
import {
  TrendingUp,
  Target,
  Plus,
  Copy,
  Trash2,
  Calendar,
  CheckCircle2,
  AlertTriangle,
  Flame,
  Activity,
  Zap,
  ChevronRight,
  Info,
  Dumbbell,
} from 'lucide-react';

interface CatalogExercise {
  id: string;
  name: string;
  primary_muscle: string;
  equipment: string;
}

interface DraftSet {
  set_number: number;
  reps: number;
  weight: number;
  rpe: number;
  rir: number;
}

interface ProgressionRec {
  weight_kg: number;
  rep_target: string;
  reason: string;
  alternative?: string;
  plateau_flag?: boolean;
  deload_suggested?: boolean;
}

interface SessionHistoryItem {
  date: string;
  session_label?: string;
  sets: Array<{
    id: number;
    set_number: number;
    weight_kg: number;
    reps: number;
    rpe: number;
  }>;
}

export function TrackerView() {
  const location = useLocation();
  const preloadedExercises: string[] = useMemo(() => {
    if (location.state?.preloadedExercises && location.state.preloadedExercises.length > 0) {
      return location.state.preloadedExercises;
    }
    try {
      const saved = localStorage.getItem('fitbot_saved_routine');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.days && parsed.days[0]?.exercises) {
          return parsed.days[0].exercises.map((e: any) => e.exercise_id);
        }
      }
    } catch (e) { }
    return [];
  }, [location.state]);

  const [exercises, setExercises] = useState<CatalogExercise[]>([]);
  const [selectedExerciseId, setSelectedExerciseId] = useState<string>(
    () => preloadedExercises[0] || 'barbell-bench-press'
  );
  const [unit, setUnit] = useState<'kg' | 'lb'>('kg');


  // Active Draft Session Sets (starts with 0 sets to solve Problem #7)
  const [sessionSets, setSessionSets] = useState<DraftSet[]>([]);

  // Right column tabs: "progress" or "volume"
  const [activeTab, setActiveTab] = useState<'progress' | 'volume'>('progress');

  // Recommendation & History State
  const [recommendation, setRecommendation] = useState<ProgressionRec | null>(null);
  const [diagnosisData, setDiagnosisData] = useState<any>(null);
  const [history, setHistory] = useState<SessionHistoryItem[]>([]);
  const [volumeSummary, setVolumeSummary] = useState<any>(null);

  const [isLoadingRec, setIsLoadingRec] = useState<boolean>(false);
  const [isLogging, setIsLogging] = useState<boolean>(false);
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    loadCatalog();
    loadVolume();
  }, []);

  useEffect(() => {
    if (selectedExerciseId) {
      loadExerciseDetails(selectedExerciseId);
    }
  }, [selectedExerciseId, unit]);

  const loadCatalog = async () => {
    try {
      const data = await getCatalogExercises();
      setExercises(data);
    } catch (err) {
      console.error('Failed to load exercises catalog:', err);
    }
  };

  const loadVolume = async () => {
    try {
      const data = await getWeeklyVolume();
      setVolumeSummary(data);
    } catch (err) {
      console.error('Failed to load weekly volume:', err);
    }
  };

  const loadExerciseDetails = async (exId: string) => {
    setIsLoadingRec(true);
    try {
      const [recData, histData, diagData] = await Promise.all([
        getRecommendation(exId),
        getExerciseHistory(exId),
        getPlateauDiagnosis(exId, { unit }).catch(() => null),
      ]);
      setRecommendation(recData);
      setHistory(histData || []);
      setDiagnosisData(diagData);
    } catch (err) {
      console.error('Error loading overload data:', err);
    } finally {
      setIsLoadingRec(false);
    }
  };

  const handleApplyDeloadPrefill = () => {
    const target = diagnosisData?.diagnosis?.deload_target;
    if (!target || target.target_weight_kg == null) return;

    const targetSetsCount = target.target_sets || 2;
    const targetWeight = unit === 'lb'
      ? Number((target.target_weight_kg * 2.20462).toFixed(1))
      : target.target_weight_kg;

    let targetReps = 8;
    if (target.target_reps_range) {
      const parts = target.target_reps_range.split('-');
      if (parts.length > 0) {
        targetReps = parseInt(parts[0].trim(), 10) || 8;
      }
    }
    const targetRpe = target.target_rpe_ceiling || 7.0;

    const prefilled = Array.from({ length: targetSetsCount }, (_, i) => ({
      set_number: i + 1,
      reps: targetReps,
      weight: targetWeight,
      rpe: targetRpe,
      rir: Math.max(0, Math.round(10 - targetRpe)),
    }));
    setSessionSets(prefilled);
    setToast({ type: 'success', message: 'Deload target prefilled into session sets (draft only).' });
  };

  const currentExercise = exercises.find((e) => e.id === selectedExerciseId);

  // Set management
  const handleAddSet = () => {
    const last = sessionSets[sessionSets.length - 1];
    const defaultWeight = recommendation?.weight_kg || 80;
    const initialWeight = unit === 'lb' ? Number((defaultWeight * 2.20462).toFixed(1)) : defaultWeight;

    setSessionSets((prev) => [
      ...prev,
      {
        set_number: prev.length + 1,
        reps: last ? last.reps : 8,
        weight: last ? last.weight : initialWeight,
        rpe: last ? last.rpe : 8.0,
        rir: last ? last.rir : 2,
      },
    ]);
  };

  const handleCopyLastSet = () => {
    if (sessionSets.length === 0) return;
    const last = sessionSets[sessionSets.length - 1];
    setSessionSets((prev) => [
      ...prev,
      {
        ...last,
        set_number: prev.length + 1,
      },
    ]);
  };

  const handleRemoveSet = (index: number) => {
    setSessionSets((prev) =>
      prev.filter((_, i) => i !== index).map((s, idx) => ({ ...s, set_number: idx + 1 }))
    );
  };

  const handleUpdateSet = (index: number, field: keyof DraftSet, val: number) => {
    setSessionSets((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: val };
      if (field === 'rpe') {
        next[index].rir = Math.max(0, Math.min(5, Math.round(10 - val)));
      } else if (field === 'rir') {
        next[index].rpe = Number((10 - val).toFixed(1));
      }
      return next;
    });
  };

  // Commit session sets
  const handleCommitSession = async () => {
    if (sessionSets.length === 0 || isLogging) return;
    setIsLogging(true);

    const payload = sessionSets.map((s) => {
      const weightInKg = unit === 'lb' ? Number((s.weight * 0.453592).toFixed(2)) : s.weight;
      return {
        exercise_id: selectedExerciseId,
        set_number: s.set_number,
        reps: s.reps,
        weight: weightInKg,
        unit: 'kg',
        rpe: s.rpe,
        rir: s.rir,
        performed_at: new Date().toISOString(),
      };
    });

    try {
      await logWorkoutSet(payload);
      setToast({ type: 'success', message: `Successfully committed ${sessionSets.length} sets to history!` });
      setSessionSets([]);
      loadExerciseDetails(selectedExerciseId);
      loadVolume();
    } catch (err: any) {
      setToast({ type: 'error', message: err.message || 'Failed to submit workout sets.' });
    } finally {
      setIsLogging(false);
    }
  };

  // Tonnage and Set Stats
  const sessionStats = useMemo(() => {
    const totalSets = sessionSets.length;
    const totalReps = sessionSets.reduce((sum, s) => sum + (s.reps || 0), 0);
    const totalTonnage = sessionSets.reduce((sum, s) => sum + (s.weight || 0) * (s.reps || 0), 0);
    return { totalSets, totalReps, totalTonnage: Math.round(totalTonnage) };
  }, [sessionSets]);

  // Transform history data for 1RM and Top-Set Line Chart
  const chartData = useMemo(() => {
    if (!history || history.length === 0) return [];

    // Chronological order (oldest to newest)
    const reversed = [...history].reverse();
    return reversed.map((sess) => {
      let topWeight = 0;
      let maxEst1RM = 0;

      sess.sets.forEach((st) => {
        const w = unit === 'lb' ? Number((st.weight_kg * 2.20462).toFixed(1)) : st.weight_kg;
        if (w > topWeight) topWeight = w;

        // Epley 1RM formula: w * (1 + reps / 30)
        const est1RM = w * (1 + st.reps / 30);
        if (est1RM > maxEst1RM) maxEst1RM = est1RM;
      });

      return {
        date: sess.date.split('T')[0],
        topWeight: Number(topWeight.toFixed(1)),
        est1RM: Number(maxEst1RM.toFixed(1)),
      };
    });
  }, [history, unit]);

  // Deviation check
  const hasDeviation = useMemo(() => {
    if (!recommendation || sessionSets.length === 0) return false;
    const targetW = unit === 'lb' ? recommendation.weight_kg * 2.20462 : recommendation.weight_kg;
    return sessionSets.some((s) => Math.abs(s.weight - targetW) / targetW > 0.25);
  }, [sessionSets, recommendation, unit]);

  return (
    <div className="flex-1 overflow-y-auto bg-[var(--bg-app)] text-[var(--text-primary)] p-6 sm:p-10 transition-colors duration-200">
      <div className="max-w-[1200px] mx-auto space-y-8 pb-32">
        {/* Page Header */}
        <PageHeader
          title="Progressive Overload & Volume Tracker"
          description="Log working sets and monitor effective hypertrophy stimulus. Double progression recommendations update deterministically upon completion."
          badge={<Badge variant="accent">Double Progression</Badge>}
        />

        {/* Top Control Bar: Searchable Combobox & kg/lb Toggle */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs">
          <div className="w-full sm:w-96">
            <Combobox
              label="Selected Movement"
              value={selectedExerciseId}
              onChange={setSelectedExerciseId}
              options={exercises.map((e) => ({
                value: e.id,
                label: e.name,
                sublabel: `${e.primary_muscle} · ${e.equipment}`,
              }))}
            />
          </div>

          <div className="flex items-center gap-2 self-start sm:self-end">
            <span className="text-xs font-semibold text-[var(--text-muted)]">Unit:</span>
            <SegmentedControl
              size="sm"
              value={unit}
              onChange={(u) => setUnit(u as 'kg' | 'lb')}
              options={[
                { value: 'kg', label: 'kg' },
                { value: 'lb', label: 'lb' },
              ]}
            />
          </div>
        </div>

        {/* Quick Routine Movement Chips */}
        {preloadedExercises.length > 0 && (
          <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
            <span className="text-[var(--text-muted)] font-semibold shrink-0">Today's Routine:</span>
            {preloadedExercises.map((exId) => {
              const matched = exercises.find((e) => e.id === exId);
              const name = matched ? matched.name : exId;
              const isSelected = selectedExerciseId === exId;
              return (
                <button
                  key={exId}
                  type="button"
                  onClick={() => setSelectedExerciseId(exId)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer shrink-0 ${isSelected
                      ? 'bg-[var(--accent-primary)] text-white shadow-xs'
                      : 'bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)]'
                    }`}
                >
                  {name}
                </button>
              );
            })}
          </div>
        )}

        {/* Target Recommendation Hero Card */}

        {isLoadingRec ? (
          <Skeleton variant="card" height={140} />
        ) : recommendation && (
          <div className="p-6 sm:p-8 rounded-2xl bg-gradient-to-br from-[var(--bg-card)] to-[var(--accent-primary-subtle)] border border-[var(--accent-primary-border)] shadow-md space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--accent-text)] flex items-center gap-1.5">
                    <Target className="w-4 h-4" /> Next Session Objective
                  </span>
                  {recommendation.plateau_flag && (
                    <Badge variant="warning" size="sm">
                      Plateau Flagged
                    </Badge>
                  )}
                  {recommendation.deload_suggested && (
                    <Badge variant="danger" size="sm">
                      Deload Recommended
                    </Badge>
                  )}
                </div>

                <h3 className="text-xl sm:text-2xl font-black text-[var(--text-primary)]">
                  {currentExercise?.name || 'Exercise'}
                </h3>

                <div className="flex items-baseline gap-4 mt-2">
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-4xl sm:text-5xl font-black font-sans tabular-nums text-[var(--text-primary)] tracking-tight">
                      {unit === 'lb'
                        ? (recommendation.weight_kg * 2.20462).toFixed(1)
                        : recommendation.weight_kg}
                    </span>
                    <span className="text-base font-semibold text-[var(--text-muted)] font-sans">
                      {unit}
                    </span>
                  </div>
                  <span className="text-2xl font-light text-[var(--border-prominent)]">/</span>
                  <div className="text-2xl font-bold font-sans text-[var(--accent-text)]">
                    {recommendation.rep_target}
                  </div>
                </div>
              </div>

              {recommendation.alternative && (
                <div className="p-3.5 rounded-xl bg-[var(--bg-card)]/80 border border-[var(--border-subtle)] max-w-xs text-xs space-y-1">
                  <span className="font-bold text-[var(--text-muted)] uppercase tracking-wider text-[10px] block">
                    Alternative Variation
                  </span>
                  <p className="text-[var(--text-primary)] font-medium">
                    {recommendation.alternative}
                  </p>
                </div>
              )}
            </div>

            <div className="pt-3 border-t border-[var(--border-subtle)] flex items-start gap-2 text-xs text-[var(--text-secondary)]">
              <Info className="w-4 h-4 text-[var(--accent-text)] shrink-0 mt-0.5" />
              <p>
                <strong className="text-[var(--text-primary)]">Progression Rule: </strong>
                {recommendation.reason}
              </p>
            </div>
          </div>
        )}

        {/* Minimal Fatigue & Plateau Diagnosis Card */}
        {diagnosisData && (diagnosisData.diagnosis?.plateau_detected || diagnosisData.active_deload) && (
          <div className="p-5 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--accent-text)] flex items-center gap-1.5">
                  <Activity className="w-4 h-4" /> Fatigue & Plateau Diagnosis
                </span>
                <Badge
                  variant={
                    diagnosisData.diagnosis?.root_cause === 'fatigue_pattern' ? 'danger' :
                      diagnosisData.diagnosis?.root_cause === 'possible_under_recovery' ? 'warning' :
                        diagnosisData.diagnosis?.root_cause === 'insufficient_stimulus' ? 'info' : 'neutral'
                  }
                  size="sm"
                >
                  {diagnosisData.diagnosis?.root_cause?.replace(/_/g, ' ') || 'Evaluation'}
                </Badge>
                {diagnosisData.active_deload && (
                  <Badge variant="success" size="sm">
                    Active Deload ({diagnosisData.active_deload.sessions_completed || 0}/{diagnosisData.active_deload.duration_sessions} sessions)
                  </Badge>
                )}
              </div>

              {diagnosisData.diagnosis?.deload_target?.target_weight_kg != null && (
                <Button
                  size="sm"
                  variant="primary"
                  onClick={handleApplyDeloadPrefill}
                >
                  Apply Deload (Prefill)
                </Button>
              )}
            </div>

            {diagnosisData.explanation && (
              <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                {diagnosisData.explanation}
              </p>
            )}

            {diagnosisData.diagnosis?.deload_target?.target_weight_kg != null && (
              <div className="p-3.5 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] text-xs flex flex-wrap items-center gap-x-6 gap-y-2">
                <div>
                  <span className="text-[var(--text-muted)] block">Prescribed Target</span>
                  <span className="font-bold text-[var(--text-primary)]">
                    {unit === 'lb'
                      ? (diagnosisData.diagnosis.deload_target.target_weight_kg * 2.20462).toFixed(1)
                      : diagnosisData.diagnosis.deload_target.target_weight_kg}{' '}
                    {unit} × {diagnosisData.diagnosis.deload_target.target_sets} sets × {diagnosisData.diagnosis.deload_target.target_reps_range} @ RPE ≤ {diagnosisData.diagnosis.deload_target.target_rpe_ceiling}
                  </span>
                </div>
                {diagnosisData.diagnosis.deload_target.resume_weight_kg != null && (
                  <div>
                    <span className="text-[var(--text-muted)] block">Resume Weight</span>
                    <span className="font-bold text-[var(--accent-text)]">
                      {unit === 'lb'
                        ? (diagnosisData.diagnosis.deload_target.resume_weight_kg * 2.20462).toFixed(1)
                        : diagnosisData.diagnosis.deload_target.resume_weight_kg}{' '}
                      {unit}
                    </span>
                  </div>
                )}
                {diagnosisData.diagnosis.deload_target.duration_sessions && (
                  <div>
                    <span className="text-[var(--text-muted)] block">Duration</span>
                    <span className="font-semibold text-[var(--text-secondary)]">
                      {diagnosisData.diagnosis.deload_target.duration_sessions} session(s)
                    </span>
                  </div>
                )}
              </div>
            )}

            {diagnosisData.sources && diagnosisData.sources.length > 0 && (
              <div className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] text-[11px] text-[var(--text-muted)] space-y-1.5">
                <span className="font-semibold text-[var(--text-secondary)] block">Retrieved Reference Sources:</span>
                {diagnosisData.sources.map((src: any, sIdx: number) => (
                  <div key={sIdx} className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[var(--accent-text)] font-bold">[{sIdx + 1}]</span>
                    <span className="font-medium text-[var(--text-primary)]">{src.source}</span>
                    {src.source.includes('Deload_and_Fatigue_Management') && (
                      <span className="text-[10px] text-[var(--accent-text)] italic bg-[var(--accent-subtle)] px-2 py-0.5 rounded">
                        AI-drafted summary of common guidance, not a published source
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Main 2-Column Layout: Left (Set Logger) + Right (Progress Chart & History) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column: Today's Session Set Logger (7 cols) */}
          <div className="lg:col-span-7 space-y-6">
            <Card
              title="Today's Session Sets"
              subtitle="Record weights and reps. Working sets at RPE ≥ 6 count toward weekly effective volume."
              action={
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCopyLastSet}
                    disabled={sessionSets.length === 0}
                    leftIcon={<Copy className="w-3.5 h-3.5" />}
                  >
                    Copy Last
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleAddSet}
                    leftIcon={<Plus className="w-3.5 h-3.5" />}
                  >
                    Add Set
                  </Button>
                </div>
              }
            >
              {/* Deviation Warning if entered weight is far from target */}
              {hasDeviation && (
                <div className="mb-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center gap-2.5 text-xs text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>
                    Notice: One or more set weights diverge by &gt;25% from the recommended target ({recommendation?.weight_kg}kg).
                  </span>
                </div>
              )}

              {sessionSets.length === 0 ? (
                <EmptyState
                  title="No Sets In Active Session"
                  description="Add your first working set or copy from previous targets to begin logging."
                  action={{
                    label: 'Add First Set',
                    onClick: handleAddSet,
                    icon: <Plus className="w-4 h-4" />,
                  }}
                />
              ) : (
                <div className="space-y-4">
                  {sessionSets.map((s, idx) => (
                    <div
                      key={idx}
                      className="p-4 rounded-2xl bg-[var(--bg-subtle)]/50 border border-[var(--border-subtle)] hover:border-[var(--border-prominent)] transition-colors space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-wider text-[var(--accent-text)]">
                          Set #{s.set_number}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleRemoveSet(idx)}
                          aria-label="Remove set"
                          className="text-[var(--text-muted)] hover:text-rose-500 p-1 rounded-lg transition-colors cursor-pointer"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="text-[11px] font-semibold text-[var(--text-secondary)] block mb-1">
                            Weight ({unit})
                          </label>
                          <Stepper
                            value={s.weight}
                            onChange={(val) => handleUpdateSet(idx, 'weight', val)}
                            step={unit === 'lb' ? 5 : 2.5}
                            min={0}
                            max={500}
                          />
                        </div>

                        <div>
                          <label className="text-[11px] font-semibold text-[var(--text-secondary)] block mb-1">
                            Reps Performed
                          </label>
                          <Stepper
                            value={s.reps}
                            onChange={(val) => handleUpdateSet(idx, 'reps', val)}
                            step={1}
                            min={1}
                            max={50}
                          />
                        </div>
                      </div>

                      {/* RPE Selectable Chips (6.0 to 10.0 in 0.5 steps) */}
                      <div>
                        <div className="flex items-center justify-between mb-1.5">
                          <label className="text-[11px] font-semibold text-[var(--text-secondary)]">
                            RPE (Rate of Perceived Exertion)
                          </label>
                          <span className="text-xs font-sans tabular-nums font-bold text-[var(--accent-text)]">
                            RIR: {s.rir} ({s.rir === 0 ? 'Failure' : `${s.rir} reps left`})
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {[6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10].map((rpeVal) => (
                            <button
                              key={rpeVal}
                              type="button"
                              onClick={() => handleUpdateSet(idx, 'rpe', rpeVal)}
                              className={`px-2.5 py-1 rounded-lg text-xs font-sans tabular-nums font-bold transition-all cursor-pointer ${s.rpe === rpeVal
                                  ? 'bg-[var(--accent-primary)] text-white shadow-xs'
                                  : 'bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                                }`}
                            >
                              {rpeVal}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* Right Column: Tabs [Progress (1RM Line Chart)] & [Weekly Volume] (5 cols) */}
          <div className="lg:col-span-5 space-y-6">
            <Tabs
              value={activeTab}
              onChange={(val) => setActiveTab(val as 'progress' | 'volume')}
              tabs={[
                { id: 'progress', label: 'Progress & 1RM', icon: <TrendingUp className="w-4 h-4" /> },
                { id: 'volume', label: 'Weekly Volume', icon: <Activity className="w-4 h-4" /> },
              ]}
            />

            {/* Tab: Progress (Estimated 1RM / Top-Set Line Chart + History Table) */}
            {activeTab === 'progress' && (
              <div className="space-y-6">
                {/* Line Chart (Requirement #2) */}
                <Card
                  title="Performance Progression Curve"
                  subtitle={`Estimated 1RM (Epley formula) & top-set weight over time (${unit}).`}
                >
                  {chartData.length < 2 ? (
                    <div className="p-8 text-center text-xs text-[var(--text-muted)]">
                      Log at least 2 sessions to generate your progression trajectory chart.
                    </div>
                  ) : (
                    <div className="h-64 w-full pt-2">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                          <XAxis
                            dataKey="date"
                            tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                            tickLine={false}
                          />
                          <YAxis
                            tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                            tickLine={false}
                            domain={['dataMin - 5', 'dataMax + 5']}
                          />
                          <RechartsTooltip
                            contentStyle={{
                              backgroundColor: 'var(--bg-card)',
                              borderColor: 'var(--border-prominent)',
                              borderRadius: '12px',
                              fontSize: '12px',
                              color: 'var(--text-primary)',
                            }}
                          />
                          <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                          <Line
                            type="monotone"
                            dataKey="est1RM"
                            name="Estimated 1RM"
                            stroke="var(--accent-primary)"
                            strokeWidth={2.5}
                            dot={{ fill: 'var(--accent-primary)', r: 3 }}
                            activeDot={{ r: 5 }}
                          />
                          <Line
                            type="monotone"
                            dataKey="topWeight"
                            name="Top Set Weight"
                            stroke="var(--macro-protein)"
                            strokeWidth={2}
                            strokeDasharray="4 4"
                            dot={{ fill: 'var(--macro-protein)', r: 3 }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </Card>

                {/* Session History Table */}
                <Card
                  title="Historical Sessions"
                  subtitle="Committed performance logs for this movement."
                >
                  {history.length === 0 ? (
                    <div className="p-6 text-center text-xs text-[var(--text-muted)]">
                      No past sessions logged for this lift yet.
                    </div>
                  ) : (
                    <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                      {history.map((sess, sIdx) => (
                        <div
                          key={sIdx}
                          className="p-3.5 rounded-xl bg-[var(--bg-subtle)]/40 border border-[var(--border-subtle)] space-y-2"
                        >
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
                              <Calendar className="w-3.5 h-3.5 text-[var(--accent-primary)]" />
                              {sess.date}
                            </span>
                            <span className="text-[10px] text-[var(--text-muted)]">
                              {sess.sets.length} sets
                            </span>
                          </div>

                          <div className="flex flex-wrap gap-1.5">
                            {sess.sets.map((st) => (
                              <div
                                key={st.id}
                                className="px-2.5 py-1 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs font-sans tabular-nums flex items-center gap-1"
                              >
                                <span className="font-bold text-[var(--text-primary)]">
                                  {unit === 'lb'
                                    ? (st.weight_kg * 2.20462).toFixed(1)
                                    : st.weight_kg}
                                  {unit}
                                </span>
                                <span className="text-[var(--text-muted)]">× {st.reps}</span>
                                <span className="text-[10px] font-semibold text-[var(--accent-text)]">
                                  @{st.rpe}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              </div>
            )}

            {/* Tab: Weekly Volume (Only Committed Sets from Backend!) */}
            {activeTab === 'volume' && (
              <Card
                title="Committed Weekly Volume"
                subtitle="Only confirmed workout sets at RPE ≥ 6.0 count toward your weekly 10–20 set target band."
              >
                {volumeSummary?.muscles ? (
                  <div className="space-y-3">
                    <div className="p-2.5 rounded-xl bg-[var(--bg-subtle)] text-[11px] text-[var(--text-muted)] flex items-center justify-between">
                      <span>Week: {volumeSummary.week_start} to {volumeSummary.week_end}</span>
                      <Badge variant="accent" size="sm">Committed Only</Badge>
                    </div>

                    {Object.entries(volumeSummary.muscles).map(([muscle, data]: [string, any]) => {
                      const count = data.count || 0;
                      const status = data.status; // 'below', 'in_range', 'above'
                      const pct = Math.min(100, Math.round((count / 20) * 100));

                      return (
                        <div key={muscle} className="p-3 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)] space-y-1.5">
                          <div className="flex justify-between items-center text-xs">
                            <span className="font-bold capitalize text-[var(--text-primary)]">
                              {muscle}
                            </span>
                            <div className="flex items-center gap-2">
                              <span className="font-sans tabular-nums font-bold text-[var(--text-primary)]">
                                {count} / 20 sets
                              </span>
                              <Badge
                                variant={status === 'in_range' ? 'success' : status === 'above' ? 'warning' : 'neutral'}
                                size="sm"
                              >
                                {status === 'in_range' ? 'Optimal (10-20)' : status === 'above' ? 'High' : 'Under 10'}
                              </Badge>
                            </div>
                          </div>

                          <div className="w-full bg-[var(--bg-subtle)] h-2 rounded-full overflow-hidden">
                            <div
                              style={{ width: `${pct}%` }}
                              className={`h-full rounded-full transition-all duration-300 ${status === 'in_range'
                                  ? 'bg-emerald-500'
                                  : status === 'above'
                                    ? 'bg-amber-500'
                                    : 'bg-[var(--accent-primary)]'
                                }`}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="p-6 text-center text-xs text-[var(--text-muted)]">
                    No committed volume found for the active week.
                  </div>
                )}
              </Card>
            )}
          </div>
        </div>

        {/* Sticky Finish Session Bar (Never overlaps mobile bottom tab bar) */}
        {sessionSets.length > 0 && (
          <div className="fixed bottom-20 md:bottom-6 left-1/2 -translate-x-1/2 z-40 bg-[var(--bg-card)] border border-[var(--border-prominent)] rounded-2xl p-4 shadow-[var(--shadow-xl)] flex flex-wrap items-center justify-between gap-4 max-w-2xl w-[90%] animate-in slide-in-from-bottom-4 duration-200">
            <div className="flex items-center gap-4 text-xs font-semibold">
              <div>
                <span className="text-[var(--text-muted)] block text-[10px] uppercase">Sets</span>
                <span className="font-sans tabular-nums text-sm font-bold text-[var(--text-primary)]">
                  {sessionStats.totalSets}
                </span>
              </div>
              <div className="h-6 w-px bg-[var(--border-subtle)]" />
              <div>
                <span className="text-[var(--text-muted)] block text-[10px] uppercase">Reps</span>
                <span className="font-sans tabular-nums text-sm font-bold text-[var(--text-primary)]">
                  {sessionStats.totalReps}
                </span>
              </div>
              <div className="h-6 w-px bg-[var(--border-subtle)]" />
              <div>
                <span className="text-[var(--text-muted)] block text-[10px] uppercase">Volume</span>
                <span className="font-sans tabular-nums text-sm font-bold text-[var(--accent-text)]">
                  {sessionStats.totalTonnage.toLocaleString()} {unit}
                </span>
              </div>
            </div>

            <Button
              variant="primary"
              size="md"
              onClick={handleCommitSession}
              isLoading={isLogging}
              leftIcon={<CheckCircle2 className="w-4 h-4" />}
            >
              Commit Workout Session
            </Button>
          </div>
        )}

        {toast && (
          <Toast
            type={toast.type}
            message={toast.message}
            onClose={() => setToast(null)}
          />
        )}
      </div>
    </div>
  );
}
<div
  style={{ width: `${pct}%` }}
  className={`h-full rounded-full transition-all duration-300 ${status === 'in_range'
      ? 'bg-emerald-500'
      : status === 'above'
        ? 'bg-amber-500'
        : 'bg-[var(--accent-primary)]'
    }`}
/>
                          </div >
                        </div >
                      );
                    })}
                  </div >
                ) : (
  <div className="p-6 text-center text-xs text-[var(--text-muted)]">
    No committed volume found for the active week.
  </div>
)}
              </Card >
            )}
          </div >
        </div >

  {/* Sticky Finish Session Bar (Never overlaps mobile bottom tab bar) */ }
{
  sessionSets.length > 0 && (
    <div className="fixed bottom-20 md:bottom-6 left-1/2 -translate-x-1/2 z-40 bg-[var(--bg-card)] border border-[var(--border-prominent)] rounded-2xl p-4 shadow-[var(--shadow-xl)] flex flex-wrap items-center justify-between gap-4 max-w-2xl w-[90%] animate-in slide-in-from-bottom-4 duration-200">
      <div className="flex items-center gap-4 text-xs font-semibold">
        <div>
          <span className="text-[var(--text-muted)] block text-[10px] uppercase">Sets</span>
          <span className="font-sans tabular-nums text-sm font-bold text-[var(--text-primary)]">
            {sessionStats.totalSets}
          </span>
        </div>
        <div className="h-6 w-px bg-[var(--border-subtle)]" />
        <div>
          <span className="text-[var(--text-muted)] block text-[10px] uppercase">Reps</span>
          <span className="font-sans tabular-nums text-sm font-bold text-[var(--text-primary)]">
            {sessionStats.totalReps}
          </span>
        </div>
        <div className="h-6 w-px bg-[var(--border-subtle)]" />
        <div>
          <span className="text-[var(--text-muted)] block text-[10px] uppercase">Volume</span>
          <span className="font-sans tabular-nums text-sm font-bold text-[var(--accent-text)]">
            {sessionStats.totalTonnage.toLocaleString()} {unit}
          </span>
        </div>
      </div>

      <Button
        variant="primary"
        size="md"
        onClick={handleCommitSession}
        isLoading={isLogging}
        leftIcon={<CheckCircle2 className="w-4 h-4" />}
      >
        Commit Workout Session
      </Button>
    </div>
  )
}

{
  toast && (
    <Toast
      type={toast.type}
      message={toast.message}
      onClose={() => setToast(null)}
    />
  )
}
      </div >
    </div >
  );
}
