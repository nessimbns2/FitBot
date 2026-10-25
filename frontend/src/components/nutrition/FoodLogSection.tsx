/**
 * src/components/nutrition/FoodLogSection.tsx
 * Today's food diary, backed by the real database (/api/nutrition/log):
 *  - summary bar: eaten vs daily target, what is left
 *  - list of today's entries with edit / delete
 *  - one form for adding and editing (also used to review AI estimates)
 *  - "what should I eat to finish today?" AI suggestions
 *
 * Numbers for totals / remaining come from the backend (plain math).
 * AI estimates (photo scan, suggestions) are always reviewed in the form
 * before anything is saved.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Badge, Button, Card, Dialog, Field, Select } from '../../design';
import { Camera, Loader2, Pencil, Plus, Sparkles, Trash2, Utensils } from 'lucide-react';
import {
  createFoodLogEntry,
  deleteFoodLogEntry,
  getDailySummary,
  listFoodLog,
  suggestMeal,
  updateFoodLogEntry,
} from '../../api/client';

// ── Types ─────────────────────────────────────────────────────────────────────

export type MealSlotValue = 'breakfast' | 'lunch' | 'dinner' | 'post_workout' | 'snack';

/** A meal waiting to be reviewed in the form (from the scanner or a suggestion). */
export interface FoodLogDraft {
  name: string;
  meal_slot: MealSlotValue;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  notes: string;
  source: 'photo_scan' | 'ai_suggestion' | 'manual';
}

interface FoodLogEntry {
  id: number;
  log_date: string;
  meal_slot: MealSlotValue;
  name: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  source: string;
  notes: string | null;
  created_at: string;
}

interface Totals {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

interface DailySummary {
  consumed: Totals;
  targets: Totals;
  remaining: Totals;
  percent_of_target: Partial<Record<keyof Totals, number | null>>;
}

interface MealSuggestion {
  name: string;
  description: string;
  portion: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fits_remaining: boolean;
}

interface SuggestionResult {
  meal_slot: MealSlotValue | null;
  remaining: Totals;
  suggestions: MealSuggestion[];
  ai_used: boolean;
  message: string | null;
}

interface FormState {
  name: string;
  meal_slot: MealSlotValue;
  calories: string;
  protein_g: string;
  carbs_g: string;
  fat_g: string;
  notes: string;
  source: string;
}

type FormErrors = Partial<Record<keyof FormState, string>>;

interface FoodLogSectionProps {
  onScanClick: () => void;
  incomingDraft: FoodLogDraft | null;
  onDraftHandled: () => void;
  onNotify: (type: 'success' | 'error', message: string) => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const SLOT_OPTIONS: Array<{ value: MealSlotValue; label: string }> = [
  { value: 'breakfast', label: 'Breakfast' },
  { value: 'lunch', label: 'Lunch' },
  { value: 'dinner', label: 'Dinner' },
  { value: 'post_workout', label: 'Post-Workout' },
  { value: 'snack', label: 'Snack' },
];

const slotLabel = (value: string) => SLOT_OPTIONS.find((o) => o.value === value)?.label ?? value;

const EMPTY_FORM: FormState = {
  name: '',
  meal_slot: 'lunch',
  calories: '',
  protein_g: '',
  carbs_g: '',
  fat_g: '',
  notes: '',
  source: 'manual',
};

const INPUT_CLASS =
  'w-full bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-xl px-3.5 py-2.5 min-h-[44px] text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)] transition-all';

const fmt = (n: number) => Math.round(n).toLocaleString();

/** The server sends UTC times without a "Z"; add it so the browser shows local time. */
function formatTime(createdAt: string): string {
  const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(createdAt) ? createdAt : `${createdAt}Z`;
  const date = new Date(iso);
  return isNaN(date.getTime())
    ? ''
    : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function parseNumber(value: string): number {
  return value.trim() === '' ? NaN : Number(value);
}

function validate(form: FormState): FormErrors {
  const errors: FormErrors = {};
  const name = form.name.trim();
  if (!name) errors.name = 'Enter a name for this meal.';
  else if (name.length > 120) errors.name = 'Keep the name under 120 characters.';

  const calories = parseNumber(form.calories);
  if (isNaN(calories)) errors.calories = 'Enter the calories.';
  else if (calories < 0 || calories > 5000) errors.calories = 'Use a value between 0 and 5000.';

  (['protein_g', 'carbs_g', 'fat_g'] as const).forEach((key) => {
    if (form[key].trim() === '') return; // optional, counts as 0
    const value = Number(form[key]);
    if (isNaN(value) || value < 0 || value > 500) errors[key] = 'Use a value between 0 and 500.';
  });

  if (form.notes.length > 500) errors.notes = 'Keep notes under 500 characters.';
  return errors;
}

function formFromEntry(entry: FoodLogEntry): FormState {
  return {
    name: entry.name,
    meal_slot: entry.meal_slot,
    calories: String(entry.calories),
    protein_g: String(entry.protein_g),
    carbs_g: String(entry.carbs_g),
    fat_g: String(entry.fat_g),
    notes: entry.notes ?? '',
    source: entry.source,
  };
}

function formFromDraft(draft: FoodLogDraft): FormState {
  return {
    name: draft.name,
    meal_slot: draft.meal_slot,
    calories: String(Math.round(draft.calories)),
    protein_g: String(Math.round(draft.protein_g * 10) / 10),
    carbs_g: String(Math.round(draft.carbs_g * 10) / 10),
    fat_g: String(Math.round(draft.fat_g * 10) / 10),
    notes: draft.notes,
    source: draft.source,
  };
}

// ── Component ─────────────────────────────────────────────────────────────────

export function FoodLogSection({
  onScanClick,
  incomingDraft,
  onDraftHandled,
  onNotify,
}: FoodLogSectionProps) {
  const [entries, setEntries] = useState<FoodLogEntry[]>([]);
  const [summary, setSummary] = useState<DailySummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Add / edit form
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [formNotice, setFormNotice] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // AI suggestions
  const [isSuggestOpen, setIsSuggestOpen] = useState(false);
  const [suggestSlot, setSuggestSlot] = useState<'' | MealSlotValue>('');
  const [suggestPrefs, setSuggestPrefs] = useState('');
  const [isSuggesting, setIsSuggesting] = useState(false);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const [suggestResult, setSuggestResult] = useState<SuggestionResult | null>(null);

  const refresh = useCallback(async () => {
    const [listResult, summaryResult] = await Promise.allSettled([listFoodLog(), getDailySummary()]);
    if (listResult.status === 'fulfilled') {
      setEntries(listResult.value);
      setLoadError(null);
    } else {
      setLoadError(listResult.reason?.message || 'Could not load your food diary.');
    }
    // The diary still works if the targets cannot be calculated.
    setSummary(summaryResult.status === 'fulfilled' ? summaryResult.value : null);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // ── Form handling ──────────────────────────────────────────────────────────

  const openForm = (entry: FoodLogEntry | null, draft: FoodLogDraft | null = null) => {
    setEditingId(entry ? entry.id : null);
    setForm(entry ? formFromEntry(entry) : draft ? formFromDraft(draft) : EMPTY_FORM);
    setFormErrors({});
    setFormNotice(
      draft?.source === 'photo_scan'
        ? 'This is the AI’s estimate from your photo. Check it and correct anything before saving.'
        : draft?.source === 'ai_suggestion'
          ? 'These are the AI’s rough estimates. Adjust them to what you actually eat before saving.'
          : null
    );
    setIsFormOpen(true);
  };

  // A meal arrives from the photo scanner: open the form so it can be reviewed.
  useEffect(() => {
    if (incomingDraft) {
      openForm(null, incomingDraft);
      onDraftHandled();
    }
  }, [incomingDraft]);

  const closeForm = () => {
    if (!isSaving) setIsFormOpen(false);
  };

  const setField = (key: keyof FormState, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (formErrors[key]) setFormErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const errors = validate(form);
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) return;

    const payload = {
      name: form.name.trim(),
      meal_slot: form.meal_slot,
      calories: Number(form.calories),
      protein_g: form.protein_g.trim() === '' ? 0 : Number(form.protein_g),
      carbs_g: form.carbs_g.trim() === '' ? 0 : Number(form.carbs_g),
      fat_g: form.fat_g.trim() === '' ? 0 : Number(form.fat_g),
      notes: form.notes.trim() === '' ? null : form.notes.trim(),
    };

    setIsSaving(true);
    try {
      if (editingId !== null) {
        await updateFoodLogEntry(editingId, payload);
        onNotify('success', `Updated ${payload.name}.`);
      } else {
        await createFoodLogEntry({ ...payload, source: form.source });
        onNotify('success', `Added ${payload.name} to today’s diary.`);
      }
      setIsFormOpen(false);
      await refresh();
    } catch (err: any) {
      setFormNotice(null);
      setFormErrors({ name: err.message || 'Could not save this meal. Please try again.' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (entry: FoodLogEntry) => {
    setDeletingId(entry.id);
    try {
      await deleteFoodLogEntry(entry.id);
      onNotify('success', `Removed ${entry.name}.`);
      await refresh();
    } catch (err: any) {
      onNotify('error', err.message || 'Could not remove this meal.');
    } finally {
      setDeletingId(null);
    }
  };

  // ── AI suggestions ─────────────────────────────────────────────────────────

  const handleSuggest = async () => {
    setIsSuggesting(true);
    setSuggestError(null);
    setSuggestResult(null);
    try {
      const result = await suggestMeal({
        meal_slot: suggestSlot || null,
        preferences: suggestPrefs.trim() || null,
      });
      setSuggestResult(result);
    } catch (err: any) {
      setSuggestError(err.message || 'Could not get suggestions right now.');
    } finally {
      setIsSuggesting(false);
    }
  };

  const reviewSuggestion = (s: MealSuggestion) => {
    openForm(null, {
      name: s.name,
      meal_slot: (suggestSlot || suggestResult?.meal_slot || 'snack') as MealSlotValue,
      calories: s.calories,
      protein_g: s.protein_g,
      carbs_g: s.carbs_g,
      fat_g: s.fat_g,
      notes: [s.portion, s.description].filter(Boolean).join(' - ').slice(0, 500),
      source: 'ai_suggestion',
    });
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  const remainingKcal = summary ? summary.remaining.calories : 0;
  const isOver = summary ? remainingKcal < 0 : false;
  const kcalPct = summary?.percent_of_target.calories ?? 0;

  const macroRows: Array<{ key: 'protein_g' | 'carbs_g' | 'fat_g'; label: string; color: string }> = [
    { key: 'protein_g', label: 'Protein', color: 'protein' },
    { key: 'carbs_g', label: 'Carbs', color: 'carbs' },
    { key: 'fat_g', label: 'Fat', color: 'fat' },
  ];

  return (
    <>
      <Card
        title="Today’s Food Diary"
        subtitle="Log what you eat and see how it adds up against your daily targets."
        action={
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={() => openForm(null)} leftIcon={<Plus className="w-3.5 h-3.5" />}>
              Add Meal
            </Button>
            <Button variant="primary" size="sm" onClick={onScanClick} leftIcon={<Camera className="w-3.5 h-3.5" />}>
              Scan Meal
            </Button>
          </div>
        }
      >
        <div className="space-y-5">
          {/* Summary: eaten vs target */}
          {summary && (
            <div className="p-4 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-subtle)] space-y-4">
              <div>
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-sm font-black text-[var(--text-primary)] font-sans tabular-nums">
                    {fmt(summary.consumed.calories)}{' '}
                    <span className="text-xs font-normal text-[var(--text-muted)]">
                      / {fmt(summary.targets.calories)} kcal
                    </span>
                  </span>
                  <span className={`text-xs font-bold ${isOver ? 'text-rose-500' : 'text-[var(--text-secondary)]'}`}>
                    {isOver ? `${fmt(Math.abs(remainingKcal))} kcal over target` : `${fmt(remainingKcal)} kcal left`}
                  </span>
                </div>
                <div
                  className="mt-2 h-2 rounded-full bg-[var(--border-subtle)] overflow-hidden"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.min(Math.round(kcalPct), 100)}
                  aria-label="Calories eaten today versus target"
                >
                  <div
                    className={`h-full rounded-full transition-all ${isOver ? 'bg-rose-500' : 'bg-[var(--accent-primary)]'}`}
                    style={{ width: `${Math.min(kcalPct, 100)}%` }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {macroRows.map(({ key, label, color }) => {
                  const pct = summary.percent_of_target[key] ?? 0;
                  const left = summary.remaining[key];
                  return (
                    <div key={key}>
                      <div className="flex items-baseline justify-between">
                        <span
                          className="text-[10px] font-bold uppercase tracking-wider"
                          style={{ color: `var(--macro-${color}-text)` }}
                        >
                          {label}
                        </span>
                        <span className="text-[11px] text-[var(--text-secondary)] font-sans tabular-nums">
                          {fmt(summary.consumed[key])} / {fmt(summary.targets[key])} g
                        </span>
                      </div>
                      <div className="mt-1 h-1.5 rounded-full bg-[var(--border-subtle)] overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: `var(--macro-${color})` }}
                        />
                      </div>
                      <span className="text-[10px] text-[var(--text-muted)]">
                        {left >= 0 ? `${fmt(left)} g left` : `${fmt(Math.abs(left))} g over`}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Entries */}
          {isLoading ? (
            <div className="py-8 flex items-center justify-center text-[var(--text-muted)]">
              <Loader2 className="w-5 h-5 animate-spin" aria-label="Loading your diary" />
            </div>
          ) : loadError ? (
            <div className="py-6 px-4 text-center rounded-2xl border border-rose-500/30 bg-rose-500/5 space-y-3">
              <p className="text-sm text-[var(--text-primary)]">{loadError}</p>
              <Button variant="secondary" size="sm" onClick={() => { setIsLoading(true); refresh(); }}>
                Try again
              </Button>
            </div>
          ) : entries.length === 0 ? (
            <div className="py-8 px-4 text-center border-2 border-dashed border-[var(--border-subtle)] rounded-2xl bg-[var(--bg-subtle)]/30 space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-[var(--accent-primary-subtle)] text-[var(--accent-text)] mx-auto flex items-center justify-center">
                <Utensils className="w-6 h-6" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-[var(--text-primary)]">Nothing logged yet today</h4>
                <p className="text-xs text-[var(--text-muted)] mt-1 max-w-sm mx-auto">
                  Add a meal by hand or scan a photo of your plate.
                </p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {entries.map((entry) => (
                <div
                  key={entry.id}
                  className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] hover:border-[var(--border-prominent)] shadow-xs transition-all space-y-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-[var(--accent-text)] uppercase tracking-wider">
                          {slotLabel(entry.meal_slot)}
                        </span>
                        <span className="text-[11px] text-[var(--text-muted)] font-mono">
                          {formatTime(entry.created_at)}
                        </span>
                        {entry.source === 'photo_scan' && <Badge size="sm" variant="neutral">Photo</Badge>}
                        {entry.source === 'ai_suggestion' && <Badge size="sm" variant="accent">AI idea</Badge>}
                      </div>
                      <h4 className="text-sm font-bold text-[var(--text-primary)] mt-0.5 truncate" title={entry.name}>
                        {entry.name}
                      </h4>
                    </div>
                    <div className="flex items-center gap-0.5 shrink-0">
                      <button
                        type="button"
                        onClick={() => openForm(entry)}
                        aria-label={`Edit ${entry.name}`}
                        title="Edit"
                        className="text-[var(--text-muted)] hover:text-[var(--accent-text)] p-1.5 rounded-lg hover:bg-[var(--bg-subtle)] transition-colors cursor-pointer"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(entry)}
                        disabled={deletingId === entry.id}
                        aria-label={`Delete ${entry.name}`}
                        title="Delete"
                        className="text-[var(--text-muted)] hover:text-rose-500 p-1.5 rounded-lg hover:bg-rose-500/10 transition-colors cursor-pointer disabled:opacity-50"
                      >
                        {deletingId === entry.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs pt-1 border-t border-[var(--border-subtle)]">
                    <span className="text-sm font-black text-[var(--text-primary)] font-sans tabular-nums">
                      {fmt(entry.calories)} <span className="text-[10px] font-normal text-[var(--text-muted)]">kcal</span>
                    </span>
                    <div className="flex items-center gap-1.5">
                      <Badge variant="protein" size="sm">P: {Math.round(entry.protein_g)}g</Badge>
                      <Badge variant="carbs" size="sm">C: {Math.round(entry.carbs_g)}g</Badge>
                      <Badge variant="fat" size="sm">F: {Math.round(entry.fat_g)}g</Badge>
                    </div>
                  </div>

                  {entry.notes && (
                    <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">{entry.notes}</p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* AI: what should I eat to finish today? */}
          <div className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-subtle)]/40 p-4 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h4 className="text-sm font-bold text-[var(--text-primary)]">What should I eat to finish today?</h4>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  The app works out what is left; the AI suggests meals that fit.
                </p>
              </div>
              <Button
                variant={isSuggestOpen ? 'ghost' : 'secondary'}
                size="sm"
                onClick={() => setIsSuggestOpen((open) => !open)}
                leftIcon={<Sparkles className="w-3.5 h-3.5" />}
                aria-expanded={isSuggestOpen}
              >
                {isSuggestOpen ? 'Hide' : 'Suggest'}
              </Button>
            </div>

            {isSuggestOpen && (
              <div className="space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <Select
                    label="Meal type"
                    value={suggestSlot}
                    onChange={(e) => setSuggestSlot(e.target.value as '' | MealSlotValue)}
                    options={[{ value: '', label: 'Any' }, ...SLOT_OPTIONS]}
                  />
                  <Field label="Preferences (optional)" className="sm:col-span-2" htmlFor="suggest-prefs">
                    <input
                      id="suggest-prefs"
                      type="text"
                      maxLength={200}
                      value={suggestPrefs}
                      onChange={(e) => setSuggestPrefs(e.target.value)}
                      placeholder="e.g. vegetarian, no dairy, quick to cook"
                      className={INPUT_CLASS}
                    />
                  </Field>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleSuggest}
                  isLoading={isSuggesting}
                  disabled={isSuggesting}
                  leftIcon={<Sparkles className="w-3.5 h-3.5" />}
                >
                  {isSuggesting ? 'Thinking…' : 'Get suggestions'}
                </Button>

                {suggestError && (
                  <p role="alert" className="text-xs text-rose-500 font-medium">{suggestError}</p>
                )}

                {suggestResult && (
                  <div className="space-y-3">
                    <p className="text-xs text-[var(--text-secondary)]">
                      Left today: <strong>{fmt(suggestResult.remaining.calories)} kcal</strong>
                      {' · '}P {fmt(suggestResult.remaining.protein_g)} g
                      {' · '}C {fmt(suggestResult.remaining.carbs_g)} g
                      {' · '}F {fmt(suggestResult.remaining.fat_g)} g
                    </p>

                    {suggestResult.message && (
                      <p className="text-sm text-[var(--text-primary)]">{suggestResult.message}</p>
                    )}

                    {suggestResult.suggestions.length > 0 && (
                      <>
                        <p className="text-[11px] text-[var(--text-muted)]">
                          Numbers below are the AI’s rough estimates. You can edit them before saving.
                        </p>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          {suggestResult.suggestions.map((s, idx) => (
                            <div key={idx} className="p-3 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)] space-y-2 flex flex-col">
                              <div className="flex items-start justify-between gap-2">
                                <h5 className="text-sm font-bold text-[var(--text-primary)]">{s.name}</h5>
                                <Badge size="sm" variant={s.fits_remaining ? 'success' : 'warning'}>
                                  {s.fits_remaining ? 'Fits' : 'Over'}
                                </Badge>
                              </div>
                              {s.portion && <p className="text-[11px] text-[var(--text-secondary)]">{s.portion}</p>}
                              {s.description && <p className="text-[11px] text-[var(--text-muted)]">{s.description}</p>}
                              <div className="flex flex-wrap items-center gap-1.5 mt-auto pt-1">
                                <span className="text-xs font-black text-[var(--text-primary)] tabular-nums">~{fmt(s.calories)} kcal</span>
                                <Badge variant="protein" size="sm">P {Math.round(s.protein_g)}g</Badge>
                                <Badge variant="carbs" size="sm">C {Math.round(s.carbs_g)}g</Badge>
                                <Badge variant="fat" size="sm">F {Math.round(s.fat_g)}g</Badge>
                              </div>
                              <Button variant="secondary" size="sm" onClick={() => reviewSuggestion(s)} leftIcon={<Plus className="w-3.5 h-3.5" />}>
                                Review &amp; add
                              </Button>
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* Add / edit form */}
      <Dialog
        isOpen={isFormOpen}
        onClose={closeForm}
        title={editingId !== null ? 'Edit meal' : 'Add a meal'}
        description="Enter what you ate. Protein, carbs and fat are optional."
      >
        <form onSubmit={handleSave} className="space-y-4" noValidate>
          {formNotice && (
            <div className="p-3 rounded-xl bg-[var(--accent-primary-subtle)] border-l-2 border-[var(--accent-primary)] text-xs text-[var(--text-secondary)] leading-relaxed">
              {formNotice}
            </div>
          )}

          <Field label="Name" required error={formErrors.name} htmlFor="food-name">
            <input
              id="food-name"
              type="text"
              value={form.name}
              maxLength={120}
              onChange={(e) => setField('name', e.target.value)}
              placeholder="e.g. Chicken and rice"
              className={INPUT_CLASS}
              autoFocus
            />
          </Field>

          <Select
            label="Meal"
            value={form.meal_slot}
            onChange={(e) => setField('meal_slot', e.target.value)}
            options={SLOT_OPTIONS}
          />

          <div className="grid grid-cols-2 gap-3">
            <Field label="Calories (kcal)" required error={formErrors.calories} htmlFor="food-calories">
              <input
                id="food-calories"
                type="number"
                inputMode="decimal"
                step="any"
                min={0}
                value={form.calories}
                onChange={(e) => setField('calories', e.target.value)}
                className={INPUT_CLASS}
              />
            </Field>
            <Field label="Protein (g)" error={formErrors.protein_g} htmlFor="food-protein">
              <input
                id="food-protein"
                type="number"
                inputMode="decimal"
                step="any"
                min={0}
                value={form.protein_g}
                onChange={(e) => setField('protein_g', e.target.value)}
                className={INPUT_CLASS}
              />
            </Field>
            <Field label="Carbs (g)" error={formErrors.carbs_g} htmlFor="food-carbs">
              <input
                id="food-carbs"
                type="number"
                inputMode="decimal"
                step="any"
                min={0}
                value={form.carbs_g}
                onChange={(e) => setField('carbs_g', e.target.value)}
                className={INPUT_CLASS}
              />
            </Field>
            <Field label="Fat (g)" error={formErrors.fat_g} htmlFor="food-fat">
              <input
                id="food-fat"
                type="number"
                inputMode="decimal"
                step="any"
                min={0}
                value={form.fat_g}
                onChange={(e) => setField('fat_g', e.target.value)}
                className={INPUT_CLASS}
              />
            </Field>
          </div>

          <Field label="Notes (optional)" error={formErrors.notes} htmlFor="food-notes">
            <textarea
              id="food-notes"
              rows={2}
              maxLength={500}
              value={form.notes}
              onChange={(e) => setField('notes', e.target.value)}
              placeholder="Portions, ingredients, anything useful"
              className={`${INPUT_CLASS} resize-none`}
            />
          </Field>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--border-subtle)]">
            <Button type="button" variant="ghost" size="sm" onClick={closeForm} disabled={isSaving}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" isLoading={isSaving} disabled={isSaving}>
              {editingId !== null ? 'Save changes' : 'Add to diary'}
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
