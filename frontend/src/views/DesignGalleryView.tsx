/**
 * src/views/DesignGalleryView.tsx
 * Hidden /design showroom for verifying every component primitive in both Dark and Light themes.
 */

import React, { useState } from 'react';
import {
  Button,
  IconButton,
  Card,
  StatCard,
  SegmentedControl,
  Stepper,
  Field,
  Select,
  Combobox,
  Tabs,
  TabContent,
  Badge,
  Drawer,
  Dialog,
  Tooltip,
  Toast,
  Skeleton,
  EmptyState,
  ErrorState,
  ProgressRing,
  PageHeader,
  useTheme,
} from '../design';
import {
  Sun,
  Moon,
  Dumbbell,
  Sparkles,
  Flame,
  Droplet,
  Trash2,
  TrendingUp,
  Info,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';

export function DesignGalleryView() {
  const { theme, toggleTheme } = useTheme();

  // Interactive component states
  const [segmentedVal, setSegmentedVal] = useState<'kg' | 'lb'>('kg');
  const [stepperVal, setStepperVal] = useState<number>(80);
  const [comboboxVal, setComboboxVal] = useState<string>('bench');
  const [activeTab, setActiveTab] = useState<string>('buttons');
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const macroSegments = [
    { label: 'Protein', value: 180, color: 'var(--macro-protein)', percent: 27 },
    { label: 'Carbs', value: 310, color: 'var(--macro-carbs)', percent: 47 },
    { label: 'Fat', value: 75, color: 'var(--macro-fat)', percent: 26 },
  ];

  return (
    <div className="flex-1 overflow-y-auto bg-[var(--bg-app)] text-[var(--text-primary)] p-6 sm:p-10 transition-colors duration-200">
      <div className="max-w-[1200px] mx-auto space-y-10">
        {/* Gallery Header */}
        <PageHeader
          title="FitBot Design System Gallery"
          description="Interactive showcase of all design primitives in both Dark and Light themes. Accessible, AA-compliant contrast, 44px touch targets."
          badge={<Badge variant="accent">Phase 1 Primitives</Badge>}
          actionSlot={
            <Button
              variant="secondary"
              size="md"
              onClick={toggleTheme}
              leftIcon={theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-indigo-500" />}
            >
              Switch to {theme === 'dark' ? 'Light' : 'Dark'} Theme
            </Button>
          }
        />

        {/* Section 1: Color Tokens & WCAG AA Contrast Verification */}
        <Card title="Color Tokens & Contrast Verification" subtitle="Action Accent is Electric Violet (distinct from Protein Blue). Fixed macronutrient colors.">
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
            <div className="p-4 rounded-xl bg-[var(--accent-primary)] text-white text-xs font-semibold shadow-xs">
              <span className="block font-bold">Accent Action</span>
              <span className="opacity-80">Electric Violet</span>
            </div>
            <div className="p-4 rounded-xl bg-[var(--accent-primary-subtle)] border border-[var(--accent-primary-border)] text-[var(--accent-text)] text-xs font-semibold">
              <span className="block font-bold">Accent Subtle</span>
              <span>AA-Safe Text</span>
            </div>
            <div className="p-4 rounded-xl bg-[var(--macro-protein)] text-white text-xs font-semibold">
              <span className="block font-bold">Protein</span>
              <span className="opacity-80">Cobalt Blue</span>
            </div>
            <div className="p-4 rounded-xl bg-[var(--macro-protein-subtle)] border border-[var(--macro-protein-border)] text-[var(--macro-protein-text)] text-xs font-semibold">
              <span className="block font-bold">Protein Text</span>
              <span>AA Contrast 5.4:1</span>
            </div>
            <div className="p-4 rounded-xl bg-[var(--macro-carbs)] text-white text-xs font-semibold">
              <span className="block font-bold">Carbs</span>
              <span className="opacity-80">Amber Gold</span>
            </div>
            <div className="p-4 rounded-xl bg-[var(--macro-carbs-subtle)] border border-[var(--macro-carbs-border)] text-[var(--macro-carbs-text)] text-xs font-semibold">
              <span className="block font-bold">Carbs Text</span>
              <span>AA Contrast 4.7:1</span>
            </div>
            <div className="p-4 rounded-xl bg-[var(--macro-fat)] text-white text-xs font-semibold">
              <span className="block font-bold">Fat</span>
              <span className="opacity-80">Emerald Green</span>
            </div>
            <div className="p-4 rounded-xl bg-[var(--macro-fat-subtle)] border border-[var(--macro-fat-border)] text-[var(--macro-fat-text)] text-xs font-semibold">
              <span className="block font-bold">Fat Text</span>
              <span>AA Contrast 4.9:1</span>
            </div>
            <div className="p-4 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-muted)] text-xs font-semibold">
              <span className="block font-bold">Muted Text</span>
              <span>AA Contrast 4.6:1</span>
            </div>
          </div>
        </Card>

        {/* Section 2: ProgressRing & Macro Donut */}
        <Card title="ProgressRing & Macro Donut Gauge" subtitle="Solves Problem #8: Shows exact macro caloric share of total daily calorie target.">
          <div className="flex flex-col sm:flex-row items-center justify-around gap-8 py-4">
            <ProgressRing
              size={210}
              strokeWidth={16}
              segments={macroSegments}
              centerLabel="Daily Target"
              centerValue="2,650"
              centerUnit="kcal / day"
            />

            <div className="space-y-4 max-w-sm w-full">
              <div className="p-3.5 rounded-xl bg-[var(--macro-protein-subtle)] border border-[var(--macro-protein-border)] flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-[var(--macro-protein-text)] uppercase tracking-wider block">Protein (27% kcal)</span>
                  <span className="text-xs text-[var(--text-secondary)]">720 kcal</span>
                </div>
                <span className="text-xl font-black font-sans tabular-nums text-[var(--macro-protein-text)]">180g</span>
              </div>

              <div className="p-3.5 rounded-xl bg-[var(--macro-carbs-subtle)] border border-[var(--macro-carbs-border)] flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-[var(--macro-carbs-text)] uppercase tracking-wider block">Carbohydrates (47% kcal)</span>
                  <span className="text-xs text-[var(--text-secondary)]">1,240 kcal</span>
                </div>
                <span className="text-xl font-black font-sans tabular-nums text-[var(--macro-carbs-text)]">310g</span>
              </div>

              <div className="p-3.5 rounded-xl bg-[var(--macro-fat-subtle)] border border-[var(--macro-fat-border)] flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-[var(--macro-fat-text)] uppercase tracking-wider block">Fats (26% kcal)</span>
                  <span className="text-xs text-[var(--text-secondary)]">675 kcal</span>
                </div>
                <span className="text-xl font-black font-sans tabular-nums text-[var(--macro-fat-text)]">75g</span>
              </div>
            </div>
          </div>
        </Card>

        {/* Section 3: StatCards Row */}
        <div>
          <h3 className="text-lg font-bold text-[var(--text-primary)] mb-3">StatCards with Sans-Serif Tabular Numbers</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Total Daily Energy"
              value="2,650"
              unit="kcal"
              subValue="TDEE +10% surplus"
              infoTooltip="Total Daily Energy Expenditure: Basal Metabolic Rate multiplied by physical activity factor."
              color="accent"
            />
            <StatCard
              label="Basal Metabolic Rate"
              value="1,750"
              unit="kcal"
              subValue="Mifflin-St Jeor Formula"
              infoTooltip="BMR calculated mathematically using age, biological sex, height, and weight."
              color="neutral"
            />
            <StatCard
              label="Daily Hydration"
              value="3.2"
              unit="Liters"
              subValue="40 ml / kg body mass"
              infoTooltip="Baseline fluid recommendation based on verified sports science manuals."
              color="protein"
            />
            <StatCard
              label="Next Bench Target"
              value="82.5"
              unit="kg"
              subValue="Double progression: +2.5kg"
              infoTooltip="Target derived from previous session RPE <= 8."
              color="accent"
            />
          </div>
        </div>

        {/* Section 4: Buttons, Controls & Inputs */}
        <Card title="Interactive Controls & Inputs" subtitle="40-44px touch targets, visible focus rings, keyboard accessible.">
          <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="primary">Primary Violet</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="ghost">Ghost Button</Button>
              <Button variant="danger">Danger Action</Button>
              <Button variant="primary" isLoading>Loading State</Button>
              <IconButton icon={<Sun className="w-4 h-4" />} aria-label="Toggle theme" variant="secondary" />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 items-end pt-4 border-t border-[var(--border-subtle)]">
              <div>
                <label className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider block mb-2">
                  Segmented Control (Solves #4)
                </label>
                <SegmentedControl
                  value={segmentedVal}
                  onChange={(val) => setSegmentedVal(val as 'kg' | 'lb')}
                  options={[

                    { value: 'kg', label: 'Metric (kg)' },
                    { value: 'lb', label: 'Imperial (lb)' },
                  ]}
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider block mb-2">
                  Numeric Stepper
                </label>
                <Stepper
                  value={stepperVal}
                  onChange={setStepperVal}
                  step={2.5}
                  min={20}
                  max={250}
                  unit={segmentedVal}
                />
              </div>

              <div>
                <Combobox
                  label="Searchable Exercise Picker"
                  value={comboboxVal}
                  onChange={setComboboxVal}
                  options={[
                    { value: 'bench', label: 'Barbell Bench Press', sublabel: 'Chest · Compound' },
                    { value: 'squat', label: 'Barbell Back Squat', sublabel: 'Quads · Compound' },
                    { value: 'deadlift', label: 'Romanian Deadlift', sublabel: 'Hamstrings · Compound' },
                    { value: 'overhead', label: 'Overhead Press', sublabel: 'Delts · Compound' },
                  ]}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-4 border-t border-[var(--border-subtle)]">
              <Select
                label="Select with Visible Label (Solves #5)"
                helper="Ensures clear accessibility without hidden labels."
                options={[
                  { value: 'hypertrophy', label: 'Hypertrophy (+10% kcal surplus)' },
                  { value: 'fat_loss', label: 'Fat Loss (-20% deficit)' },
                  { value: 'strength', label: 'Strength Focus (+5% surplus)' },
                ]}
              />

              <Field label="Text Input Field" helper="With focus ring and helper text">
                <input
                  type="text"
                  placeholder="Enter body weight..."
                  className="w-full bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-xl px-3.5 py-2.5 text-sm min-h-[44px] focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)] text-[var(--text-primary)]"
                />
              </Field>
            </div>
          </div>
        </Card>

        {/* Section 5: Overlays, Modals & Drawers */}
        <Card title="Overlays & Notifications" subtitle="Accessible Radix-based drawers and dialogs.">
          <div className="flex flex-wrap items-center gap-4">
            <Button variant="secondary" onClick={() => setIsDrawerOpen(true)}>
              Open Exercise Drawer
            </Button>
            <Button variant="secondary" onClick={() => setIsDialogOpen(true)}>
              Open Confirmation Dialog
            </Button>
            <Button variant="primary" onClick={() => setToastMessage('Workout session saved successfully!')}>
              Trigger Success Toast
            </Button>
          </div>
        </Card>

        {/* Section 6: Skeletons & Resilience States */}
        <Card title="Loading, Empty & Error States" subtitle="Solves #6 & #10: Resilient skeletons and recovery retry states.">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div className="p-4 rounded-xl border border-[var(--border-subtle)] space-y-3">
              <span className="text-xs font-bold text-[var(--text-secondary)] uppercase">Skeleton Loader</span>
              <Skeleton variant="card" height={100} />
              <Skeleton variant="text" width="60%" />
            </div>

            <EmptyState
              title="No Past Sessions"
              description="Complete your first workout session to establish progression baselines."
              action={{ label: 'Start Session', onClick: () => {} }}
            />

            <ErrorState
              title="Failed to Load Meal Plan"
              message="The request timed out after 6 seconds. Click below to retry."
              onRetry={() => {}}
            />
          </div>
        </Card>
      </div>

      {/* Interactive Drawer */}
      <Drawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        title="Barbell Bench Press Technique"
        description="Biomechanical execution cues and setup steps."
      >
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-[var(--bg-subtle)] space-y-2">
            <h5 className="text-xs font-bold uppercase tracking-wider text-[var(--accent-text)]">Setup Checklist</h5>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              1. Retract and depress scapulae firmly into the bench.<br />
              2. Plant feet flat with driving leg pressure.<br />
              3. Grip slightly wider than shoulder width with neutral wrists.
            </p>
          </div>
          <Button variant="secondary" onClick={() => setIsDrawerOpen(false)}>Close Drawer</Button>
        </div>
      </Drawer>

      {/* Interactive Dialog */}
      <Dialog
        isOpen={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        title="Commit Workout Session?"
        description="This will permanently log 3 sets to your history and update double progression targets."
      >
        <div className="space-y-4">
          <p className="text-xs text-[var(--text-secondary)]">
            Total effective volume: 3 sets (24 reps @ 80kg).
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setIsDialogOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={() => setIsDialogOpen(false)}>Commit Sets</Button>
          </div>
        </div>
      </Dialog>

      {/* Toast */}
      {toastMessage && (
        <Toast
          type="success"
          message={toastMessage}
          onClose={() => setToastMessage(null)}
        />
      )}
    </div>
  );
}
