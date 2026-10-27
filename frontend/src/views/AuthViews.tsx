/**
 * src/views/AuthViews.tsx
 * Public authentication screens: Login and Register, sharing one split layout
 * (brand panel + form card). Validation mirrors the backend rules.
 */

import React, { useId, useMemo, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Calculator,
  Check,
  Dumbbell,
  Eye,
  EyeOff,
  Lock,
  Mail,
  ShieldCheck,
  Sparkles,
  User,
} from 'lucide-react';
import { Button } from '../design';
import { useAuth } from '../context/AuthContext';

// ── Shared building blocks ────────────────────────────────────────────────────

interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  error?: string;
  trailing?: React.ReactNode;
}

function TextInput({ label, icon: Icon, error, trailing, id: customId, ...props }: TextInputProps) {
  const generatedId = useId();
  const id = customId || generatedId;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs sm:text-sm font-semibold text-[var(--text-primary)] select-none">
        {label}
      </label>
      <div className="relative">
        <Icon className="w-4 h-4 text-[var(--text-muted)] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          id={id}
          aria-invalid={Boolean(error)}
          className={`w-full bg-[var(--bg-card)] border text-[var(--text-primary)] text-sm rounded-xl pl-10 ${
            trailing ? 'pr-11' : 'pr-3.5'
          } py-2.5 min-h-[44px] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)] focus:border-transparent transition-all ${
            error ? 'border-rose-500' : 'border-[var(--border-subtle)]'
          }`}
          {...props}
        />
        {trailing && <div className="absolute right-1.5 top-1/2 -translate-y-1/2">{trailing}</div>}
      </div>
      {error && (
        <p className="text-xs text-rose-500 flex items-center gap-1 font-medium">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{error}</span>
        </p>
      )}
    </div>
  );
}

function PasswordToggle({ visible, onToggle }: { visible: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={visible ? 'Hide password' : 'Show password'}
      className="w-8 h-8 inline-flex items-center justify-center rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)] transition-colors"
    >
      {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
    </button>
  );
}

function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5 text-sm text-rose-500"
    >
      <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

const FEATURES = [
  { icon: Calculator, title: 'Exact math, never guessed', text: 'BMR, TDEE, macros and overload targets come from validated formulas.' },
  { icon: Sparkles, title: 'Evidence-based AI coach', text: 'Answers grounded in indexed training & nutrition guides, with sources.' },
  { icon: ShieldCheck, title: 'Private by design', text: 'Your data lives in your account. Personal details are masked before any AI call.' },
];

function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="h-full overflow-y-auto w-full flex bg-[var(--bg-app)] text-[var(--text-primary)]">
      {/* Brand panel */}
      <aside className="hidden lg:flex lg:w-[46%] xl:w-[42%] relative overflow-hidden flex-col justify-between p-10 xl:p-14 auth-brand-panel">
        <div className="absolute -top-24 -right-24 w-80 h-80 rounded-full bg-white/10 blur-2xl" aria-hidden />
        <div className="absolute -bottom-32 -left-16 w-96 h-96 rounded-full bg-emerald-400/10 blur-3xl" aria-hidden />

        <div className="relative flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-white/15 backdrop-blur flex items-center justify-center">
            <Dumbbell className="w-6 h-6" />
          </div>
          <div>
            <p className="text-lg font-bold tracking-tight">FitBot</p>
            <p className="text-xs text-white/70">AI Fitness & Nutrition Coach</p>
          </div>
        </div>

        <div className="relative space-y-8">
          <h2 className="text-3xl xl:text-4xl font-bold leading-tight tracking-tight">
            Train smarter with a coach that shows its work.
          </h2>
          <ul className="space-y-5">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-4">
                <div className="w-10 h-10 rounded-xl bg-white/15 flex items-center justify-center shrink-0">
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <p className="font-semibold">{title}</p>
                  <p className="text-sm text-white/75 leading-relaxed">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-white/60">
          FitBot provides educational guidance and is not a substitute for medical advice.
        </p>
      </aside>

      {/* Form panel */}
      <main className="flex-1 flex min-h-max items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-[420px]">
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <div className="w-10 h-10 rounded-xl bg-[var(--accent-primary)] text-[var(--text-on-accent)] flex items-center justify-center">
              <Dumbbell className="w-5 h-5" />
            </div>
            <span className="text-lg font-bold tracking-tight">FitBot</span>
          </div>

          <Link to="/" className="inline-flex items-center gap-2 mb-6 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            <ArrowLeft className="w-4 h-4" aria-hidden="true" />
            Back to home
          </Link>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">{title}</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1.5 mb-7">{subtitle}</p>
          {children}
        </div>
      </main>
    </div>
  );
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

// ── Login ─────────────────────────────────────────────────────────────────────

export function LoginView() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from || '/dashboard';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  if (isAuthenticated) return <Navigate to={from} replace />;

  const emailError = submitted && !EMAIL_RE.test(email.trim()) ? 'Enter a valid email address.' : undefined;
  const passwordError = submitted && !password ? 'Enter your password.' : undefined;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    setFormError(null);
    if (!EMAIL_RE.test(email.trim()) || !password) return;
    setIsSubmitting(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err: any) {
      setFormError(err.message || 'Login failed. Please try again.');
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Welcome back" subtitle="Log in to continue your training plan.">
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <FormError message={formError} />
        <TextInput
          label="Email"
          icon={Mail}
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={emailError}
          autoFocus
        />
        <TextInput
          label="Password"
          icon={Lock}
          type={showPassword ? 'text' : 'password'}
          autoComplete="current-password"
          placeholder="Your password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={passwordError}
          trailing={<PasswordToggle visible={showPassword} onToggle={() => setShowPassword((v) => !v)} />}
        />
        <Button type="submit" size="lg" isLoading={isSubmitting} rightIcon={<ArrowRight className="w-4 h-4" />} className="w-full mt-2">
          Log in
        </Button>
      </form>

      <p className="text-sm text-[var(--text-secondary)] mt-6 text-center">
        New to FitBot?{' '}
        <Link to="/register" state={location.state} className="font-semibold text-[var(--accent-text)] hover:underline">
          Create an account
        </Link>
      </p>
    </AuthLayout>
  );
}

// ── Register ──────────────────────────────────────────────────────────────────

function passwordChecks(pw: string) {
  return [
    { label: 'At least 8 characters', ok: pw.length >= 8 },
    { label: 'Contains a letter', ok: /[A-Za-z]/.test(pw) },
    { label: 'Contains a digit', ok: /\d/.test(pw) },
  ];
}

export function RegisterView() {
  const { register, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const checks = useMemo(() => passwordChecks(password), [password]);
  const passwordOk = checks.every((c) => c.ok) && new TextEncoder().encode(password).length <= 72;

  // While submitting, onSubmit itself redirects new accounts to /profile (onboarding).
  if (isAuthenticated && !isSubmitting) return <Navigate to="/dashboard" replace />;

  const nameError = submitted && fullName.trim().length < 2 ? 'Enter your full name.' : undefined;
  const emailError = submitted && !EMAIL_RE.test(email.trim()) ? 'Enter a valid email address.' : undefined;
  const passwordError = submitted && !passwordOk ? 'Choose a stronger password (see rules below).' : undefined;
  const confirmError = submitted && confirm !== password ? 'Passwords do not match.' : undefined;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    setFormError(null);
    if (fullName.trim().length < 2 || !EMAIL_RE.test(email.trim()) || !passwordOk || confirm !== password) return;
    setIsSubmitting(true);
    try {
      await register(fullName, email, password);
      // New accounts start on the profile page to enter their biometrics. isSubmitting stays
      // true on purpose: router navigations are transitions, and resetting it here would let
      // the already-authenticated guard above render first and win.
      navigate('/profile', { replace: true, state: { welcome: true } });
    } catch (err: any) {
      setFormError(err.message || 'Registration failed. Please try again.');
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Create your account" subtitle="Your profile, workouts and meals are saved to your account.">
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <FormError message={formError} />
        <TextInput
          label="Full name"
          icon={User}
          autoComplete="name"
          placeholder="e.g. Sara Ben Ali"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          error={nameError}
          maxLength={120}
          autoFocus
        />
        <TextInput
          label="Email"
          icon={Mail}
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={emailError}
        />
        <TextInput
          label="Password"
          icon={Lock}
          type={showPassword ? 'text' : 'password'}
          autoComplete="new-password"
          placeholder="Create a password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={passwordError}
          trailing={<PasswordToggle visible={showPassword} onToggle={() => setShowPassword((v) => !v)} />}
        />
        <ul className="grid grid-cols-1 sm:grid-cols-3 gap-1.5 -mt-1" aria-label="Password rules">
          {checks.map((c) => (
            <li
              key={c.label}
              className={`flex items-center gap-1.5 text-xs ${c.ok ? 'text-emerald-500' : 'text-[var(--text-muted)]'}`}
            >
              <Check className={`w-3.5 h-3.5 ${c.ok ? 'opacity-100' : 'opacity-40'}`} />
              {c.label}
            </li>
          ))}
        </ul>
        <TextInput
          label="Confirm password"
          icon={Lock}
          type={showPassword ? 'text' : 'password'}
          autoComplete="new-password"
          placeholder="Repeat the password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={confirmError}
        />
        <Button type="submit" size="lg" isLoading={isSubmitting} rightIcon={<ArrowRight className="w-4 h-4" />} className="w-full mt-2">
          Create account
        </Button>
        <p className="text-xs text-[var(--text-muted)] text-center leading-relaxed">
          Passwords are hashed with bcrypt and never stored in plain text.
        </p>
      </form>

      <p className="text-sm text-[var(--text-secondary)] mt-6 text-center">
        Already have an account?{' '}
        <Link to="/login" className="font-semibold text-[var(--accent-text)] hover:underline">
          Log in
        </Link>
      </p>
    </AuthLayout>
  );
}
