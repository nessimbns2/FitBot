/**
 * src/views/ProfileView.tsx
 * Complete redesign of Athlete Profile & Settings:
 * - Stacked section cards (Body, Body Composition, Goal & Training, Units)
 * - Selectable visual cards for Goal & Somatotype (no unlabeled dropdowns)
 * - SegmentedControl for Experience & Units
 * - Sticky side card with debounced live preview (BMI, BMR, Target Kcal)
 * - Save bar appearing only on dirty state (safe from mobile tab bar)
 * - 3-step onboarding wizard for fresh profiles
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { useProfile, UserProfile } from '../context/ProfileContext';
import { AccountSettings } from '../components/AccountSettings';
import {
  PageHeader,
  Card,
  StatCard,
  Field,
  Select,
  SegmentedControl,
  Button,
  Badge,
  Toast,
  Dialog,
  useTheme,
} from '../design';
import {
  UserCheck,
  Scale,
  Sparkles,
  ShieldCheck,
  Flame,
  Dumbbell,
  Compass,
  Save,
  RotateCcw,
  CheckCircle2,
  Info,
  TrendingUp,
  Target,
  Zap,
  ArrowRight,
  ChevronLeft,
  Award,
} from 'lucide-react';

interface GoalOption {
  id: UserProfile['goal'];
  title: string;
  description: string;
  kcalNote: string;
  icon: React.ComponentType<{ className?: string }>;
}

const GOAL_OPTIONS: GoalOption[] = [
  {
    id: 'hypertrophy',
    title: 'Hypertrophy',
    description: 'Muscle growth & lean mass accumulation',
    kcalNote: '+10% kcal surplus · 2.0g/kg protein',
    icon: Dumbbell,
  },
  {
    id: 'fat_loss',
    title: 'Fat Loss',
    description: 'Caloric deficit with lean mass preservation',
    kcalNote: '-20% kcal deficit · 2.2g/kg protein floor',
    icon: Flame,
  },
  {
    id: 'strength',
    title: 'Strength Focus',
    description: 'Maximal force output & neurological drive',
    kcalNote: '+5% kcal surplus · heavy compound focus',
    icon: Target,
  },
  {
    id: 'athletic_performance',
    title: 'Athletic Performance',
    description: 'Explosive conditioning, speed & recovery',
    kcalNote: 'Maintenance kcal · balanced glycogen',
    icon: Zap,
  },
];

interface SomatotypeOption {
  id: UserProfile['somatotype'];
  title: string;
  description: string;
  macroNote: string;
}

const SOMATOTYPE_OPTIONS: SomatotypeOption[] = [
  {
    id: 'mesomorph',
    title: 'Mesomorph',
    description: 'Naturally athletic & muscular build',
    macroNote: 'Standard balanced carb/fat partition',
  },
  {
    id: 'endomorph',
    title: 'Endomorph',
    description: 'Higher carb sensitivity & slower metabolism',
    macroNote: 'Shifts 5% carbohydrate allocation to dietary fat',
  },
  {
    id: 'ectomorph',
    title: 'Ectomorph',
    description: 'Fast metabolic rate & lean bone structure',
    macroNote: 'Shifts 5% dietary fat allocation to carbohydrates',
  },
  {
    id: 'unknown',
    title: 'Unknown',
    description: 'Neutral metabolic baseline without adaptations',
    macroNote: 'Standard sports science baseline distribution',
  },
];

import { SomatotypeQuizModal } from '../components/SomatotypeQuizModal';
import { AthleteBlueprintModal } from '../components/AthleteBlueprintModal';

export function ProfileView() {
  const { profile, isLoading, update, needsOnboarding } = useProfile();
  const [formData, setFormData] = useState<Partial<UserProfile>>({});
  const [initialData, setInitialData] = useState<Partial<UserProfile>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Unit mode: 'metric' (kg, cm) or 'imperial' (lb, in)
  const [unitMode, setUnitMode] = useState<'metric' | 'imperial'>('metric');

  // Onboarding wizard state
  const [showWizard, setShowWizard] = useState(false);
  const [wizardStep, setWizardStep] = useState<number>(1);

  // Somatotype diagnostic quiz modal state
  const [showSomatotypeQuiz, setShowSomatotypeQuiz] = useState(false);

  // Right after sign-up the register page sends { welcome: true }: open the onboarding wizard.
  const location = useLocation();
  const isNewAccount = Boolean((location.state as { welcome?: boolean } | null)?.welcome);

  // Athlete Blueprint modal state
  const [showBlueprintModal, setShowBlueprintModal] = useState(false);

  useEffect(() => {
    if (profile) {
      const data: Partial<UserProfile> = {
        age: profile.age ?? 25,
        sex: profile.sex ?? 'male',
        height_cm: profile.height_cm ?? 175,
        weight_kg: profile.weight_kg ?? 75,
        body_fat_pct: profile.body_fat_pct ?? null,
        experience_level: profile.experience_level ?? 'intermediate',
        goal: profile.goal ?? 'hypertrophy',
        somatotype: profile.somatotype ?? 'mesomorph',
        activity_level: profile.activity_level ?? 'moderate',
        unit_system: profile.unit_system ?? 'metric',
      };
      setFormData(data);
      setInitialData(data);
      setUnitMode(data.unit_system || 'metric');

      if (needsOnboarding || isNewAccount) {
        setShowWizard(true);
      }
    }
  }, [profile, needsOnboarding, isNewAccount]);

  const handleChange = <K extends keyof UserProfile>(field: K, value: UserProfile[K]) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  // Check dirty state
  const isDirty = useMemo(() => {
    return JSON.stringify(formData) !== JSON.stringify(initialData);
  }, [formData, initialData]);

  // Unit display values
  const displayWeight =
    unitMode === 'imperial'
      ? formData.weight_kg ? Number((formData.weight_kg * 2.20462).toFixed(1)) : ''
      : formData.weight_kg || '';

  const displayHeight =
    unitMode === 'imperial'
      ? formData.height_cm ? Number((formData.height_cm / 2.54).toFixed(1)) : ''
      : formData.height_cm || '';

  // Deterministic Live Preview Calculations
  const previewMetrics = useMemo(() => {
    const weight = Number(formData.weight_kg) || 75;
    const height = Number(formData.height_cm) || 175;
    const age = Number(formData.age) || 25;
    const sex = formData.sex || 'male';
    const bf = formData.body_fat_pct ? Number(formData.body_fat_pct) : null;
    const activity = formData.activity_level || 'moderate';
    const goal = formData.goal || 'hypertrophy';

    // BMI
    const bmiVal = weight / Math.pow(height / 100, 2);

    // BMR
    let bmrVal = 0;
    let formula = 'Mifflin-St Jeor';
    if (bf && bf >= 3 && bf <= 60) {
      const lbm = weight * (1 - bf / 100);
      bmrVal = 370 + 21.6 * lbm;
      formula = 'Katch-McArdle (LBM)';
    } else {
      if (sex === 'male') {
        bmrVal = 10 * weight + 6.25 * height - 5 * age + 5;
      } else {
        bmrVal = 10 * weight + 6.25 * height - 5 * age - 161;
      }
    }

    // TDEE Multipliers
    const activityMults: Record<string, number> = {
      sedentary: 1.2,
      light: 1.375,
      moderate: 1.55,
      very_active: 1.725,
      extreme: 1.9,
    };
    const tdeeVal = bmrVal * (activityMults[activity] || 1.55);

    // Goal Adjustments
    let targetKcal = tdeeVal;
    if (goal === 'hypertrophy') targetKcal = tdeeVal * 1.1;
    else if (goal === 'fat_loss') targetKcal = tdeeVal * 0.8;
    else if (goal === 'strength') targetKcal = tdeeVal * 1.05;

    return {
      bmi: bmiVal.toFixed(1),
      bmr: Math.round(bmrVal),
      formula,
      tdee: Math.round(tdeeVal),
      targetKcal: Math.round(targetKcal),
    };
  }, [formData]);

  const handleSave = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setIsSaving(true);
    setToast(null);

    const payload: Partial<UserProfile> = {
      ...formData,
      age: Number(formData.age),
      height_cm: Number(formData.height_cm),
      weight_kg: Number(formData.weight_kg),
      body_fat_pct: formData.body_fat_pct ? Number(formData.body_fat_pct) : null,
      unit_system: unitMode,
    };

    const res = await update(payload);
    setIsSaving(false);

    if (res.success) {
      setInitialData({ ...formData, unit_system: unitMode });
      setToast({ type: 'success', message: 'Athlete profile updated and nutrition targets recalculated!' });
      setShowWizard(false);
    } else {
      setToast({ type: 'error', message: res.error || 'Failed to update profile.' });
    }
  };

  const handleDiscard = () => {
    setFormData(initialData);
    setUnitMode(initialData.unit_system || 'metric');
  };

  return (
    <div className="flex-1 overflow-y-auto bg-[var(--bg-app)] text-[var(--text-primary)] p-6 sm:p-10 transition-colors duration-200">
      <div className="max-w-[1200px] mx-auto space-y-8 pb-28">
        {/* Page Header with Action */}
        <PageHeader
          title="Athlete Profile & Physiological Parameters"
          description="Your physical metrics calibrate our deterministic algorithms. Energy expenditure, macro distribution, and overload recommendations compute mathematically from these values."
          badge={<Badge variant="accent">Deterministic Core</Badge>}
          actionSlot={
            <div className="flex items-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setWizardStep(1);
                  setShowWizard(true);
                }}
              >
                Onboarding Wizard
              </Button>
            </div>
          }
        />

        <form onSubmit={handleSave} className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Main Column: Stacked Sections (8 cols) */}
          <div className="lg:col-span-8 space-y-6">
            {/* Section 1: Physical Biometrics */}
            <Card
              title="1. Physical Biometrics"
              subtitle="Core anthropometric data used to determine baseline metabolic rate."
              action={
                <SegmentedControl
                  size="sm"
                  value={unitMode}
                  onChange={(mode) => {
                    setUnitMode(mode);
                    handleChange('unit_system', mode);
                  }}
                  options={[
                    { value: 'metric', label: 'Metric (kg / cm)' },
                    { value: 'imperial', label: 'Imperial (lb / in)' },
                  ]}
                />
              }
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <Field label="Age (years)" helper="Must be between 14 and 100" required>
                  <input
                    type="number"
                    min={14}
                    max={100}
                    value={formData.age ?? ''}
                    onChange={(e) => handleChange('age', Number(e.target.value))}
                    required
                    className="w-full bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-primary)] text-sm rounded-xl px-3.5 py-2.5 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)] font-sans tabular-nums font-semibold"
                  />
                </Field>

                <Select
                  label="Biological Sex"
                  helper="Calibrates hormonal baseline BMR constant (+5 male / -161 female)"
                  value={formData.sex || 'male'}
                  onChange={(e) => handleChange('sex', e.target.value as 'male' | 'female')}
                  options={[
                    { value: 'male', label: 'Male' },
                    { value: 'female', label: 'Female' },
                  ]}
                />

                <Field
                  label={`Height (${unitMode === 'imperial' ? 'inches' : 'cm'})`}
                  helper={unitMode === 'imperial' ? '1 inch = 2.54 cm' : 'Centimeters'}
                  required
                >
                  <input
                    type="number"
                    step="0.1"
                    min={unitMode === 'imperial' ? 48 : 120}
                    max={unitMode === 'imperial' ? 95 : 240}
                    value={displayHeight}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      const inCm = unitMode === 'imperial' ? val * 2.54 : val;
                      handleChange('height_cm', Number(inCm.toFixed(1)));
                    }}
                    required
                    className="w-full bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-primary)] text-sm rounded-xl px-3.5 py-2.5 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)] font-sans tabular-nums font-semibold"
                  />
                </Field>

                <Field
                  label={`Body Weight (${unitMode === 'imperial' ? 'lb' : 'kg'})`}
                  helper={unitMode === 'imperial' ? '1 kg = 2.20462 lb' : 'Kilograms'}
                  required
                >
                  <input
                    type="number"
                    step="0.1"
                    min={unitMode === 'imperial' ? 66 : 30}
                    max={unitMode === 'imperial' ? 660 : 300}
                    value={displayWeight}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      const inKg = unitMode === 'imperial' ? val * 0.453592 : val;
                      handleChange('weight_kg', Number(inKg.toFixed(1)));
                    }}
                    required
                    className="w-full bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-primary)] text-sm rounded-xl px-3.5 py-2.5 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)] font-sans tabular-nums font-semibold"
                  />
                </Field>
              </div>
            </Card>

            {/* Section 2: Body Composition */}
            <Card
              title="2. Body Composition & Formula Selection"
              subtitle="Enables the gold-standard Katch-McArdle equation based on lean body mass."
            >
              <div className="space-y-4">
                <Field
                  label="Body Fat Percentage (%) — Optional"
                  helper="Enter between 3.0% and 60.0% if measured via DEXA, caliper, or bioimpedance."
                >
                  <input
                    type="number"
                    step="0.5"
                    min={3}
                    max={60}
                    placeholder="e.g. 15.0"
                    value={formData.body_fat_pct ?? ''}
                    onChange={(e) =>
                      handleChange(
                        'body_fat_pct',
                        e.target.value ? Number(e.target.value) : null
                      )
                    }
                    className="w-full sm:w-1/2 bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-primary)] text-sm rounded-xl px-3.5 py-2.5 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)] font-sans tabular-nums font-semibold"
                  />
                </Field>

                <div className="p-4 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-subtle)] flex items-start gap-3">
                  <Info className="w-4 h-4 text-[var(--accent-text)] shrink-0 mt-0.5" />
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    <strong className="text-[var(--text-primary)] font-semibold">Formula rule: </strong>
                    {formData.body_fat_pct
                      ? 'Katch-McArdle formula is active. BMR is calculated strictly from lean body mass (LBM), providing superior accuracy for lean individuals and athletes.'
                      : 'Mifflin-St Jeor formula is active using sex, weight, height, and age.'}
                  </p>
                </div>
              </div>
            </Card>

            {/* Section 3: Training Goal (Selectable Visual Cards) */}
            <Card
              title="3. Primary Training Goal"
              subtitle="Shapes your daily caloric balance, protein intake floor, and training periodization."
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                {GOAL_OPTIONS.map((opt) => {
                  const Icon = opt.icon;
                  const isSelected = formData.goal === opt.id;
                  return (
                    <div
                      key={opt.id}
                      onClick={() => handleChange('goal', opt.id)}
                      className={`p-4 rounded-2xl border transition-all cursor-pointer select-none flex flex-col justify-between ${
                        isSelected
                          ? 'bg-[var(--accent-primary-subtle)] border-[var(--accent-primary)] shadow-sm'
                          : 'bg-[var(--bg-card)] border-[var(--border-subtle)] hover:border-[var(--border-prominent)] hover:bg-[var(--bg-card-hover)]'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div
                          className={`w-9 h-9 rounded-xl flex items-center justify-center ${
                            isSelected
                              ? 'bg-[var(--accent-primary)] text-white'
                              : 'bg-[var(--bg-subtle)] text-[var(--text-secondary)]'
                          }`}
                        >
                          <Icon className="w-4 h-4" />
                        </div>
                        {isSelected && (
                          <CheckCircle2 className="w-5 h-5 text-[var(--accent-primary)]" />
                        )}
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-[var(--text-primary)]">
                          {opt.title}
                        </h4>
                        <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-snug">
                          {opt.description}
                        </p>
                        <span className="inline-block mt-2 text-[11px] font-semibold text-[var(--accent-text)]">
                          {opt.kcalNote}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* Section 4: Experience Level & Somatotype */}
            <Card
              title="4. Training Experience & Somatotype"
              subtitle="Calibrates progression increment pace and macronutrient allocation."
            >
              <div className="space-y-6">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] block mb-2">
                    Lifting Experience Level
                  </label>
                  <SegmentedControl
                    value={formData.experience_level || 'intermediate'}
                    onChange={(val) => handleChange('experience_level', val)}
                    options={[
                      { value: 'beginner', label: 'Beginner (< 1 yr)' },
                      { value: 'intermediate', label: 'Intermediate (1–3 yrs)' },
                      { value: 'advanced', label: 'Advanced (3+ yrs)' },
                    ]}
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] block">
                      Somatotype (Metabolic Tendency)
                    </label>
                    <button
                      type="button"
                      onClick={() => setShowSomatotypeQuiz(true)}
                      className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--accent-primary)] hover:underline cursor-pointer"
                    >
                      <Sparkles className="w-3.5 h-3.5 text-[var(--accent-primary)]" />
                      Not sure? Take AI Quiz
                    </button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {SOMATOTYPE_OPTIONS.map((s) => {
                      const isSelected = formData.somatotype === s.id;
                      return (
                        <div
                          key={s.id}
                          onClick={() => handleChange('somatotype', s.id)}
                          className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
                            isSelected
                              ? 'bg-[var(--accent-primary-subtle)] border-[var(--accent-primary)]'
                              : 'bg-[var(--bg-card)] border-[var(--border-subtle)] hover:border-[var(--border-prominent)]'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-bold text-[var(--text-primary)]">
                              {s.title}
                            </span>
                            {isSelected && (
                              <span className="w-2 h-2 rounded-full bg-[var(--accent-primary)]" />
                            )}
                          </div>
                          <p className="text-[11px] text-[var(--text-secondary)] leading-tight">
                            {s.description}
                          </p>
                          <span className="block text-[10px] text-[var(--accent-text)] mt-1.5 font-medium">
                            {s.macroNote}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <Select
                  label="Daily Activity Factor"
                  helper="Reflects non-exercise activity thermogenesis (NEAT) plus workout density."
                  value={formData.activity_level || 'moderate'}
                  onChange={(e) =>
                    handleChange('activity_level', e.target.value as UserProfile['activity_level'])
                  }
                  options={[
                    { value: 'sedentary', label: 'Sedentary', hint: '1.2× — Desk work, minimal exercise' },
                    { value: 'light', label: 'Lightly Active', hint: '1.375× — 1–3 sessions/week' },
                    { value: 'moderate', label: 'Moderately Active', hint: '1.55× — 3–5 training days' },
                    { value: 'very_active', label: 'Very Active', hint: '1.725× — 6–7 intense days' },
                    { value: 'extreme', label: 'Extreme', hint: '1.9× — Physical manual labor + lifting' },
                  ]}
                />
              </div>
            </Card>
          </div>

          {/* Sticky Side Column: Live Target Preview (4 cols) */}
          <div className="lg:col-span-4 space-y-6 lg:sticky lg:top-6">
            <Card
              title="Live Target Calculation"
              subtitle="Debounced physiological projection from your current values."
            >
              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-[var(--accent-primary-subtle)] border border-[var(--accent-primary-border)]">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--accent-text)] block">
                    Daily Calorie Target
                  </span>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-3xl font-black font-sans tabular-nums text-[var(--text-primary)]">
                      {previewMetrics.targetKcal}
                    </span>
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      kcal / day
                    </span>
                  </div>
                  <span className="text-[11px] text-[var(--text-secondary)] block mt-1 capitalize">
                    {formData.goal?.replace('_', ' ')} strategy
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-[var(--bg-subtle)] rounded-xl border border-[var(--border-subtle)]">
                    <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase block">
                      BMR ({previewMetrics.formula.split(' ')[0]})
                    </span>
                    <span className="text-lg font-bold font-sans tabular-nums text-[var(--text-primary)]">
                      {previewMetrics.bmr}
                    </span>
                    <span className="text-[10px] text-[var(--text-muted)] block">kcal baseline</span>
                  </div>

                  <div className="p-3 bg-[var(--bg-subtle)] rounded-xl border border-[var(--border-subtle)]">
                    <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase block">
                      Calculated BMI
                    </span>
                    <span className="text-lg font-bold font-sans tabular-nums text-[var(--text-primary)]">
                      {previewMetrics.bmi}
                    </span>
                    <span className="text-[10px] text-[var(--text-muted)] block">kg/m²</span>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl border border-[var(--border-subtle)] space-y-1 text-xs">
                  <div className="flex items-center gap-1.5 font-semibold text-[var(--accent-text)]">
                    <ShieldCheck className="w-4 h-4" />
                    Zero Probabilistic Hallucination
                  </div>
                  <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                    Unlike generic AI chatbots, FitBot calculates every gram of protein and calorie target through verified mathematical formulas.
                  </p>
                </div>
              </div>
            </Card>

            {/* AI Athlete Blueprint & Profile Audit Card */}
            <Card className="border-[var(--accent-primary)]/40 bg-gradient-to-br from-[var(--accent-primary-subtle)] via-[var(--bg-card)] to-[var(--bg-subtle)] relative overflow-hidden">
              <div className="space-y-3.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[var(--accent-text)]">
                    <Sparkles className="w-4 h-4 text-[var(--accent-primary)]" />
                    Your Fitness Blueprint
                  </div>
                  <Badge variant="accent" size="sm">
                    Personalized Plan
                  </Badge>
                </div>

                <div className="space-y-1">
                  <h4 className="text-sm font-black text-[var(--text-primary)] flex items-center gap-2">
                    <Award className="w-4 h-4 text-[var(--accent-primary)]" />
                    Your Personalized Fitness Plan
                  </h4>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    See your body's strengths, how many sets to do each week, and realistic results to expect over 3 and 6 months.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-1 text-[11px] font-semibold text-[var(--text-muted)]">
                  <div className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                    <span>Workout Sets</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                    <span>Body Strengths</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                    <span>What to Watch</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                    <span>Expected Results</span>
                  </div>
                </div>

                <Button
                  variant="primary"
                  size="md"
                  type="button"
                  onClick={() => setShowBlueprintModal(true)}
                  leftIcon={<Sparkles className="w-4 h-4" />}
                  className="w-full mt-2"
                >
                  View Your Fitness Blueprint
                </Button>
              </div>
            </Card>
          </div>
        </form>

        <AccountSettings notify={(type, message) => setToast({ type, message })} />

        {/* Floating Dirty-State Save Bar (Safe from Mobile Tab Bar) */}
        {isDirty && (
          <div className="fixed bottom-20 md:bottom-6 left-1/2 -translate-x-1/2 z-40 bg-[var(--bg-card)] border border-[var(--border-prominent)] rounded-2xl p-4 shadow-[var(--shadow-xl)] flex items-center gap-4 animate-in slide-in-from-bottom-4 duration-200">
            <span className="text-xs sm:text-sm font-semibold text-[var(--text-primary)]">
              You have unsaved biometrics changes
            </span>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={handleDiscard}>
                <RotateCcw className="w-3.5 h-3.5" /> Discard
              </Button>
              <Button variant="primary" size="sm" onClick={() => handleSave()} isLoading={isSaving}>
                <Save className="w-3.5 h-3.5" /> Save Changes
              </Button>
            </div>
          </div>
        )}

        {/* 3-Step Onboarding Wizard Modal */}
        <Dialog
          isOpen={showWizard}
          onClose={() => setShowWizard(false)}
          title={`Athlete Onboarding — Step ${wizardStep} of 3`}
          description={
            wizardStep === 1
              ? 'Tell us your physical measurements.'
              : wizardStep === 2
              ? 'Select your primary training objective.'
              : 'Tell us about your daily activity level.'
          }
        >
          <div className="space-y-6">
            {wizardStep === 1 && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Age" required>
                    <input
                      type="number"
                      value={formData.age || ''}
                      onChange={(e) => handleChange('age', Number(e.target.value))}
                      className="w-full bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-xl p-2.5 text-sm"
                    />
                  </Field>
                  <Select
                    label="Sex"
                    value={formData.sex || 'male'}
                    onChange={(e) => handleChange('sex', e.target.value as 'male' | 'female')}
                    options={[
                      { value: 'male', label: 'Male' },
                      { value: 'female', label: 'Female' },
                    ]}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Height (cm)" required>
                    <input
                      type="number"
                      value={formData.height_cm || ''}
                      onChange={(e) => handleChange('height_cm', Number(e.target.value))}
                      className="w-full bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-xl p-2.5 text-sm"
                    />
                  </Field>
                  <Field label="Weight (kg)" required>
                    <input
                      type="number"
                      value={formData.weight_kg || ''}
                      onChange={(e) => handleChange('weight_kg', Number(e.target.value))}
                      className="w-full bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-xl p-2.5 text-sm"
                    />
                  </Field>
                </div>
              </div>
            )}

            {wizardStep === 2 && (
              <div className="space-y-2.5">
                {GOAL_OPTIONS.map((g) => (
                  <div
                    key={g.id}
                    onClick={() => handleChange('goal', g.id)}
                    className={`p-3 rounded-xl border cursor-pointer ${
                      formData.goal === g.id
                        ? 'bg-[var(--accent-primary-subtle)] border-[var(--accent-primary)] font-bold'
                        : 'bg-[var(--bg-card)] border-[var(--border-subtle)]'
                    }`}
                  >
                    <div className="text-xs text-[var(--text-primary)]">{g.title}</div>
                    <div className="text-[11px] text-[var(--text-secondary)]">{g.description}</div>
                  </div>
                ))}
              </div>
            )}

            {wizardStep === 3 && (
              <div className="space-y-3">
                <Select
                  label="Daily Activity"
                  value={formData.activity_level || 'moderate'}
                  onChange={(e) =>
                    handleChange('activity_level', e.target.value as UserProfile['activity_level'])
                  }
                  options={[
                    { value: 'sedentary', label: 'Sedentary (Desk work)' },
                    { value: 'light', label: 'Lightly Active (1–3 training days)' },
                    { value: 'moderate', label: 'Moderately Active (3–5 training days)' },
                    { value: 'very_active', label: 'Very Active (6–7 intense days)' },
                  ]}
                />
              </div>
            )}

            <div className="flex justify-between items-center pt-4 border-t border-[var(--border-subtle)]">
              {wizardStep > 1 ? (
                <Button variant="ghost" size="sm" onClick={() => setWizardStep(wizardStep - 1)}>
                  <ChevronLeft className="w-4 h-4" /> Back
                </Button>
              ) : (
                <div />
              )}

              {wizardStep < 3 ? (
                <Button variant="primary" size="sm" onClick={() => setWizardStep(wizardStep + 1)}>
                  Next Step <ArrowRight className="w-4 h-4" />
                </Button>
              ) : (
                <Button variant="primary" size="sm" onClick={() => handleSave()} isLoading={isSaving}>
                  Finish & Save Profile
                </Button>
              )}
            </div>
          </div>
        </Dialog>

        {toast && (
          <Toast
            type={toast.type}
            message={toast.message}
            onClose={() => setToast(null)}
          />
        )}

        <SomatotypeQuizModal
          isOpen={showSomatotypeQuiz}
          onClose={() => setShowSomatotypeQuiz(false)}
          onApplySomatotype={(predicted) => {
            handleChange('somatotype', predicted);
            setToast({
              type: 'success',
              message: `Somatotype updated to ${predicted.toUpperCase()} based on AI assessment. Click 'Save Profile' to lock it in.`,
            });
          }}
        />

        <AthleteBlueprintModal
          isOpen={showBlueprintModal}
          onClose={() => setShowBlueprintModal(false)}
          profile={profile}
        />
      </div>
    </div>
  );
}
