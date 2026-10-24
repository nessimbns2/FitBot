# FitBot Frontend Redesign — Design System & Architecture Specification (DESIGN.md)

**Document Version:** 1.1.0 (Approved with User Revisions)  
**Target:** `frontend/` (React 19 + Vite + TypeScript + Tailwind CSS)  
**Author:** Senior Product Designer & React Engineer  
**Status:** Approved — In Execution (Phase 1)

---

## 1. Audit of Current Screens & Root-Cause Analysis

| # | Current UI Problem | Root Cause in Code | Architectural Solution |
|---|---|---|---|
| **1** | **No breathing room**: Content touches sidebar/window edges, text sits flush against card borders, empty voids below cramped headers. | Layout wrappers used ad-hoc `p-4 md:p-8` without max-width constraints, nested cards lack standardized padding tokens (e.g. `p-2` or `p-3.5`). | Implement unified shell container: `max-w-[1200px] mx-auto px-6 py-8` (desktop) and `px-4 py-6` (mobile). Every card adheres to 16–24px interior padding (`p-5` to `p-6`). |
| **2** | **Cards barely distinguishable from background**: Flat visual hierarchy where all numbers and headings look equally weighted. | Background `#090a0f` vs card `#121520` had almost zero border contrast (`#1a1f2e`), missing elevation shadows, uniform font sizes across metrics. | Establish a clear 3-tier elevation system (Base App, Raised Card, Overlay/Popover) with crisp border tokens (`--border-subtle`, `--border-prominent`), ambient shadows, and a strict typography scale with `font-sans tabular-nums` for primary vs secondary KPIs. |
| **3** | **Sidebar is plain text list with tiny icons; profile chip is clipped**. | Sidebar is fixed at 240px with rigid overflow, text truncation on `.capitalize` string, no icon badge containers or collapsed rail mode. | Rebuild Desktop Left Rail with expandable (240px) and icon-only rail (72px) modes. Wrap icons in 36x36px optical containers with active indicator pills. Re-architect profile card with avatar circle, unclipped goal & weight tags, and direct route to `/profile`. |
| **4** | **Segmented toggles squashed together** (`kglb`, `Metric (kg / cm)Imperial (lb / in)`). | Implemented with inline raw buttons without gap tokens, inner padding, or sliding background pill. | Implement accessible `SegmentedControl` primitive using styled container (`p-1`, `gap-1`, `rounded-xl`) with distinct active indicator and 40px minimum touch target per segment. |
| **5** | **Profile form dropdowns lack visible labels**. | Raw HTML `<select>` tags rendered without `<label>` elements or accessible `aria-labelledby` linkages. | Create `Select` and `Field` primitives that enforce required floating or stacked `<label>` with semantic description subtitle, error message slots, and custom chevron indicators. |
| **6** | **Nutrition meal plan shows an endless spinner**. | 1) Backend `/api/nutrition/plan?include_guidance=true` ran 3 blocking synchronous LLM completions that timed out or hung without fallback. 2) Frontend lacked timeout, AbortController, skeleton loader, and error retry state. 3) Response payload mismatch: code accessed `meal.name` and `meal.timing` instead of backend's `meal.label` and `meal.time_hint`. | **Zero backend changes**: Fetch `/api/nutrition/plan` without guidance first (6s timeout, skeleton, retry), which completes deterministically in <5ms. Then load guidance separately with its own skeleton and a 30–60s timeout. Map fields cleanly (`label`, `time_hint`, `kcal`, `protein_g`, `carbs_g`, `fat_g`). |
| **7** | **Tracker weekly volume counts uncommitted sets** (e.g., Chest showed 3 sets with 0 sessions). | `TrackerView` hardcoded 3 default mock sets in its initial React state `sessionSets = [{set:1, weight:80...}]`. Users perceived this unlogged form input as counting toward volume. Additionally, the backend DB had 3 previously saved `cable-chest-fly` sets while the active exercise selector was filtered to `barbell-bench-press`. | 1) Active session logger starts with an explicit draft state (or empty state with "+ Add Set" CTA). 2) Distinguish between "Committed Sets This Week" and "Draft Session". 3) Weekly volume card explicitly badges `Committed in History (Mon–Sun)` and displays exercise breakdowns. |
| **8** | **Macro progress bars lack contextual meaning** (bar of what, out of what?). | Raw horizontal percentage bars calculated `(carbs_g * 4) / target_kcal` without baseline indicators or unified chart visualization. | Replace with an interactive **Calorie & Macro Donut Chart / ProgressRing** hero card. Center displays total target kcal; outer rings/donut segments display Protein, Carbs, and Fat share of calories, accompanied by an explicit legend showing grams, kcal, and percentage. |
| **9** | **Workout Planner is a dense wall of text**, catalog squeezed underneath. | Both routine generator schedule and 56+ exercise list were stacked sequentially on a single long scrolling page. | Split into two dedicated top-level tabs: **"My Routine"** (Left: sticky split configuration panel; Right: day schedule cards with sets x reps badges and muscle chips) and **"Exercise Library"** (search bar, muscle/equipment filter chips, 3-column card grid with difficulty badges, and side Drawer for deep form cues). |
| **10** | **No mobile layout, no light theme, unclear states**. | App shell assumed fixed desktop viewport; no light theme CSS tokens existed; empty states were plain text paragraphs. | 1) Responsive shell: 240px/72px collapsible desktop rail, 72px tablet rail, mobile top bar + 5-item bottom dock (44px touch targets). 2) Dual-theme CSS variable design system (`.dark` and `.light`) with persistent toggle in sidebar. 3) Dedicated `EmptyState`, `Skeleton`, and `ErrorState` primitives. Ensure sticky bars sit above mobile dock (`bottom-16`). |

---

## 2. Design Tokens & System Specification (`src/design/`)

### 2.1 Color Tokens (Dark & Light Themes) — With Electric Violet Accent & AA Contrast

All colors are exposed as semantic CSS variables on `:root` and `.dark` / `.light`.

```css
/* Color Tokens (CSS Variables) */
:root {
  /* Brand / Action Accent: Electric Violet (Distinct from Protein Blue) */
  --accent-primary: #7c3aed;       /* Violet 600 */
  --accent-primary-hover: #6d28d9; /* Violet 700 */
  --accent-primary-subtle: #f5f3ff;/* Violet 50 */
  --accent-primary-border: #ddd6fe;/* Violet 200 */
  --accent-foreground: #ffffff;
  --accent-text: #6d28d9;          /* AA-safe on light background (contrast 6.8:1) */

  /* Fixed Macronutrient Tokens (Identical across all cards, charts, and badges) */
  --macro-protein: #2563eb;        /* Cobalt Blue 600 */
  --macro-protein-text: #1d4ed8;   /* Blue 700 - AA-safe on white (contrast 5.4:1) */
  --macro-protein-subtle: #eff6ff;
  --macro-protein-border: #bfdbfe;

  --macro-carbs: #d97706;          /* Amber 600 */
  --macro-carbs-text: #b45309;     /* Amber 700 - AA-safe on white (contrast 4.7:1) */
  --macro-carbs-subtle: #fffbeb;
  --macro-carbs-border: #fde68a;

  --macro-fat: #059669;            /* Emerald 600 */
  --macro-fat-text: #047857;       /* Emerald 700 - AA-safe on white (contrast 4.9:1) */
  --macro-fat-subtle: #ecfdf5;
  --macro-fat-border: #a7f3d0;

  /* Semantic Feedback */
  --status-success: #059669;
  --status-warning: #d97706;
  --status-danger: #dc2626;
  --status-info: #7c3aed;

  /* Surfaces & Text (Light Theme) */
  --bg-app: #f8fafc;               /* Slate 50 */
  --bg-subtle: #f1f5f9;            /* Slate 100 */
  --bg-card: #ffffff;              /* Pure White */
  --bg-card-hover: #f8fafc;
  --bg-card-active: #f1f5f9;
  --bg-overlay: rgba(15, 23, 42, 0.45);

  --border-subtle: #e2e8f0;        /* Slate 200 */
  --border-prominent: #cbd5e1;     /* Slate 300 */
  --border-focused: #7c3aed;

  --text-primary: #0f172a;         /* Slate 900 (Contrast > 15:1) */
  --text-secondary: #334155;       /* Slate 700 (Contrast 9.6:1) */
  --text-muted: #64748b;           /* Slate 500 - AA-safe on white (Contrast 4.6:1 >= 4.5:1) */
  --text-on-accent: #ffffff;

  /* Elevation Shadows (Light Theme) */
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.07);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.08);
  --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
}

.dark {
  /* Brand / Action Accent: Electric Violet (Dark Theme) */
  --accent-primary: #8b5cf6;       /* Violet 500 */
  --accent-primary-hover: #7c3aed; /* Violet 600 */
  --accent-primary-subtle: rgba(139, 92, 246, 0.15);
  --accent-primary-border: rgba(139, 92, 246, 0.35);
  --accent-foreground: #ffffff;
  --accent-text: #a78bfa;          /* Violet 400 (Contrast 8.5:1 on dark) */

  /* Fixed Macronutrient Tokens (Dark Athletic Obsidian Theme) */
  --macro-protein: #3b82f6;        /* Blue 500 */
  --macro-protein-text: #60a5fa;   /* Blue 400 */
  --macro-protein-subtle: rgba(59, 130, 246, 0.15);
  --macro-protein-border: rgba(59, 130, 246, 0.35);

  --macro-carbs: #f59e0b;          /* Amber 500 */
  --macro-carbs-text: #fbbf24;     /* Amber 400 */
  --macro-carbs-subtle: rgba(245, 158, 11, 0.15);
  --macro-carbs-border: rgba(245, 158, 11, 0.35);

  --macro-fat: #10b981;            /* Emerald 500 */
  --macro-fat-text: #34d399;       /* Emerald 400 */
  --macro-fat-subtle: rgba(16, 185, 129, 0.15);
  --macro-fat-border: rgba(16, 185, 129, 0.35);

  /* Semantic Feedback */
  --status-success: #10b981;
  --status-warning: #f59e0b;
  --status-danger: #ef4444;
  --status-info: #8b5cf6;

  /* Surfaces & Text (Dark Athletic Obsidian Theme) */
  --bg-app: #08090d;               /* Deep Void */
  --bg-subtle: #0e1118;            /* Slate 950 */
  --bg-card: #131722;              /* Elevation 1 */
  --bg-card-hover: #191f2e;        /* Elevation 2 */
  --bg-card-active: #1f273a;       /* Elevation 3 */
  --bg-overlay: rgba(0, 0, 0, 0.7);

  --border-subtle: #1e2538;        /* Slate 800/90 */
  --border-prominent: #2a344e;     /* Slate 700/80 */
  --border-focused: #8b5cf6;

  --text-primary: #f8fafc;         /* Slate 50 (Contrast > 15:1) */
  --text-secondary: #cbd5e1;       /* Slate 300 (Contrast 11:1) */
  --text-muted: #94a3b8;           /* Slate 400 (Contrast 6:1) */
  --text-on-accent: #ffffff;

  /* Shadows (Dark Theme) */
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.3);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.4), 0 2px 4px -2px rgb(0 0 0 / 0.3);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.5), 0 4px 6px -4px rgb(0 0 0 / 0.4);
  --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.6), 0 8px 10px -6px rgb(0 0 0 / 0.5);
}
```

### 2.2 Typography: Sans-Serif with Tabular Numbers

- **Typeface**: Inter / SF Pro Display sans-serif system stack (`font-sans`), with **`font-sans tabular-nums font-semibold`** for all stats, weights, reps, calories, and timestamps.
- **Type Scale**:
  - `text-xs`: 12px / 16px line-height (Badges, labels, helper notes)
  - `text-sm`: 14px / 20px line-height (Form inputs, table rows, button labels)
  - `text-base`: 16px / 24px line-height (Body text, card descriptions)
  - `text-lg`: 18px / 28px line-height (Card titles, section headers)
  - `text-xl`: 20px / 28px line-height (Medium stat cards, hero subtitles)
  - `text-2xl`: 24px / 32px line-height (Page headers, secondary KPIs)
  - `text-4xl` / `text-5xl`: 36px / 48px line-height (`font-sans tabular-nums font-black` for primary calorie & 1RM KPIs)
- **Radii**: Small elements 8px (`rounded-lg`), inputs & buttons 12px (`rounded-xl`), cards & modals 16–20px (`rounded-2xl`), pills `rounded-full`.
- **Motion**: Micro-transitions 150ms (`ease-out`), slide/drawer 250ms (`cubic-bezier(0.16, 1, 0.3, 1)`), respecting `@media (prefers-reduced-motion: reduce)`.

---

## 3. UI Component Primitives Library (`src/design/`)

Built in TypeScript (`.tsx`) with full keyboard navigation and focus rings:

| Component | Props / Variants | Description & Accessibility |
|---|---|---|
| `Button` | `variant: 'primary' \| 'secondary' \| 'ghost' \| 'danger'`, `size: 'sm' \| 'md' \| 'lg'`, `isLoading`, `leftIcon`, `rightIcon` | Minimum 44px touch target on mobile (`size="md"` is 42px desktop, 44px mobile). Keyboard accessible with focus ring. |
| `IconButton` | `icon`, `aria-label`, `variant`, `size` | Accessible icon-only button requiring explicit `aria-label`. |
| `Card` | `title`, `subtitle`, `action`, `variant: 'default' \| 'glass' \| 'interactive'`, `padding: 'sm' \| 'md' \| 'lg'` | Standardized elevated container with 16–24px padding and subtle border. |
| `StatCard` | `label`, `value`, `unit`, `trend`, `infoTooltip`, `color: 'accent' \| 'protein' \| 'carbs' \| 'fat'` | Compact KPI tile with optional information tooltip for physiological formulas. |
| `SegmentedControl` | `options: { value, label, icon }[]`, `value`, `onChange`, `size` | Modern sliding pill toggle with keyboard left/right arrow navigation. |
| `Stepper` | `value`, `min`, `max`, `step`, `onChange`, `unit` | Clean numeric increment/decrement with large touchable `+` / `-` buttons and direct input. |
| `Field` | `label`, `helper`, `error`, `required`, `children` | Accessible form wrapper linking `<label>` to `children` via `htmlFor` and `aria-describedby`. |
| `Select` | `label`, `options: { value, label, hint }[]`, `value`, `onChange`, `helper`, `error` | Styled dropdown with visible label and custom chevron icon. |
| `Combobox` | `options`, `value`, `onChange`, `placeholder`, `searchable` | Accessible searchable picker with keyboard selection (Enter/Esc/Arrows). |
| `Tabs` | `tabs: { id, label, icon, badge }[]`, `activeTab`, `onChange` | WAI-ARIA tab list with keyboard arrow navigation and active underline pill. |
| `Chip` / `Badge` | `variant: 'neutral' \| 'accent' \| 'protein' \| 'carbs' \| 'fat' \| 'warning' \| 'success'`, `size`, `onRemove` | Compact semantic tag for muscles, equipment, and status. |
| `Drawer` | `isOpen`, `onClose`, `title`, `description`, `children`, `position: 'right' \| 'bottom'` | Side-sheet with backdrop blur, focus trap, Escape key listener, and smooth spring entrance. |
| `Dialog` | `isOpen`, `onClose`, `title`, `description`, `children` | Centered accessible modal for confirmations (e.g. discard workout, delete session). |
| `Tooltip` | `content`, `children`, `side: 'top' \| 'right' \| 'bottom' \| 'left'` | Hover/focus accessible tooltip with 200ms delay. |
| `Toast` | `type: 'success' \| 'error' \| 'info'`, `message`, `onClose`, `duration` | Non-blocking floating status toast at top-right or bottom-center. |
| `Skeleton` | `variant: 'text' \| 'card' \| 'circular' \| 'rect'`, `width`, `height` | Subtle pulsing placeholder for loading states (e.g., meal plan generator). |
| `EmptyState` | `icon`, `title`, `description`, `action` | Helpful zero-data screen with clear call-to-action button. |
| `ErrorState` | `title`, `message`, `onRetry` | Actionable recovery screen for failed API requests. |
| `ProgressRing` | `value`, `max`, `size`, `strokeWidth`, `color`, `centerContent` | SVG circular gauge for daily calories and macro distribution. |
| `PageHeader` | `title`, `description`, `actionSlot`, `badge` | Standard top header across all views guaranteeing unified layout spacing. |

---

## 4. App Shell & Navigation Map

### 4.1 Shell Architecture & Mobile Dock Safety
- **Collapsible Rail**: 240px expanded / 72px icon-only (stored in `localStorage`).
- **Tablet**: 72px rail by default.
- **Mobile**: Top Bar (mark + title + theme toggle + avatar) + Bottom Dock (5 items: Today, Coach, Nutrition, Workouts, Tracker).
- **Mobile Bottom Bar Safety**: All sticky bars (e.g. session commit bar) use `bottom-16` or `mb-16` on mobile (`md:bottom-0 md:mb-0`), ensuring zero overlap with the 64px bottom tab bar.
- **Theme Switcher**: Supported across dark & light modes, stored in `localStorage('fitbot_theme')`, instantly applied via `document.documentElement.classList`.

### 4.2 Route Hierarchy
```
/                   -> Today (Home Dashboard with macro progress, next targets, volume summary)
/coach              -> Coach Chat (760px column, drawer conversation list, starter chips)
/nutrition          -> Nutrition & Metabolic Targets (Hero macro donut, meal timeline, RAG drawer)
/workouts           -> Workout Planner (Tabs: "My Routine" & "Exercise Library")
/tracker            -> Overload Tracker (Session logger, double progression targets, 1RM line chart, weekly volume)
/profile            -> Athlete Profile (Body biometrics, training goals, live preview card, onboarding)
/design             -> Component System Gallery (Displays all primitives in both themes)
```

---

## 5. Detailed Page Redesigns

### 5.1 Route: `/` — "Today" Dashboard
- Daily snapshot: Calorie & Macro `ProgressRing`, Next Session Objective Card, Mini Weekly Volume Gauge, and Quick Coach Ask.

### 5.2 Route: `/coach` — Coach Chat
- Centered 760px conversation stream, slide-in conversation list drawer, 2x2 starter prompt cards, floating composer, inline pending workout log confirmation card.

### 5.3 Route: `/nutrition` — Nutrition & Metabolic Targets
- Hero card: Calorie target + Macro Donut Chart.
- StatCards row: TDEE, BMR, Hydration with tooltips.
- Meal Plan: Fetches `/api/nutrition/plan` without guidance first (6s timeout, skeleton, retry). Then loads guidance separately with its own skeleton and 30–60s timeout.

### 5.4 Route: `/workouts` — Workout Planner & Exercise Library
- Two tabs: "My routine" & "Exercise library".
- Left sticky configuration + right routine day cards with "Start in Tracker".
- Exercise library with search, filter chips, difficulty badges, and form cue Drawer.

### 5.5 Route: `/tracker` — Overload Tracker
- Top exercise Combobox + `[kg / lb]` SegmentedControl.
- Left column: Today's Session with double progression target card, clean set logger with steppers and RPE chips (6–10 in 0.5 steps with RIR), sticky bottom commit bar.
- Right column:
  - **Progress Tab**: **Estimated-1RM / top-set Line Chart** rendered via Recharts, plus historical sessions table with plateau/deload alerts.
  - **Weekly Volume Tab**: Visual bars showing **only committed sets** for the week (Mon–Sun) against the 10–20 optimal range.

### 5.6 Route: `/profile` — Athlete Profile & Settings
- Stacked section cards (Body, Body composition, Goal & training, Units) with labeled controls.
- Sticky live preview card of BMI, BMR, calories.
- Dirty state save bar.
- 3-step onboarding wizard for first run.

### 5.7 Route: `/design` — Component Gallery
- Complete visual showroom of all primitives in Dark and Light themes.
