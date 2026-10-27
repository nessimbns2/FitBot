import { useEffect, useRef, useState } from 'react';
import { BookOpen, RefreshCw } from 'lucide-react';
import { Button, Card } from '../../design';
import { explainWorkoutRoutine, getPreferenceStatus, resetExercisePreferences, trainExercisePreferences } from '../../api/client';

interface Explanation {
  plan_summary: string;
  weekly_sets: Record<string, number>;
  sections: Array<{ title: string; text: string; citations: number[] }>;
  sources: Array<{ id: number; source: string; page: number; excerpt: string }>;
  mode: string;
  message: string;
}

export function RoutineExplanation({ routine }: { routine: unknown }) {
  const [result, setResult] = useState<Explanation | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const currentRequest = useRef<AbortController | null>(null);
  useEffect(() => {
    currentRequest.current?.abort();
    setResult(null); setError(''); setLoading(false);
    return () => currentRequest.current?.abort();
  }, [routine]);

  const explain = async () => {
    const controller = new AbortController();
    currentRequest.current?.abort(); currentRequest.current = controller;
    setLoading(true); setError('');
    try {
      const data = await explainWorkoutRoutine(routine, controller.signal);
      if (!controller.signal.aborted) setResult(data);
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Could not explain this routine.');
    } finally { if (!controller.signal.aborted) setLoading(false); }
  };

  return <Card title="Why this routine?" subtitle="Explore your plan with explanations from the exercise guides."
    action={<Button size="sm" variant="secondary" disabled={!routine} isLoading={loading} onClick={explain} leftIcon={<BookOpen size={15} />}>{result ? 'Refresh explanation' : 'Explain my routine'}</Button>}>
    {!result && !loading && !error && <p className="text-xs text-[var(--text-muted)]">Review the exercises, movement coverage and planned volume with cited references.</p>}
    {loading && <p className="text-xs" role="status">Retrieving guides and explaining your plan…</p>}
    {error && <p className="text-xs text-rose-400" role="alert">{error}</p>}
    {result && <div className="space-y-4 text-xs leading-relaxed">
      <p>{result.plan_summary}</p>
      <div className="flex gap-2 flex-wrap" aria-label="Planned weekly sets">{Object.entries(result.weekly_sets).map(([muscle, sets]) => <span className="rounded-lg bg-[var(--bg-subtle)] px-2 py-1 capitalize" key={muscle}>{muscle}: {sets} sets</span>)}</div>
      <p className="text-[var(--text-secondary)]" role="status">{result.message}</p>
      {result.sections.map((section, index) => <section key={index}><h4 className="font-bold text-sm mb-1">{section.title}</h4><p className="whitespace-pre-line text-[var(--text-secondary)]">{section.text}</p>
        <div className="flex gap-2 mt-1">{section.citations.map(id => <a className="text-[var(--accent-text)] underline" key={id} href={`#routine-source-${id}`} aria-label={`View source ${id}`}>[{id}]</a>)}</div>
      </section>)}
      {result.sources.length > 0 && <div className="space-y-2 border-t border-[var(--border-subtle)] pt-3"><h4 className="font-semibold">Sources</h4>{result.sources.map(source => <details key={source.id} id={`routine-source-${source.id}`} className="rounded-lg bg-[var(--bg-subtle)] p-3 scroll-mt-6">
        <summary className="cursor-pointer text-[var(--accent-text)]">[{source.id}] {source.source} · page {source.page}</summary><p className="mt-2 whitespace-pre-line text-[var(--text-secondary)]">{source.excerpt}</p>
      </details>)}</div>}
    </div>}
  </Card>;
}

interface LearningStatus {
  examples: number; positive: number; negative: number; unique_exercises: number; neutral_replacements: number;
  minimum_examples: number; minimum_per_class: number; minimum_exercises: number;
  can_train: boolean; active: boolean; trained_at: string | null;
  metrics: { balanced_accuracy: number; baseline_balanced_accuracy: number; test_examples: number; evaluation: string } | null;
}

export function PreferenceLearning({ refresh }: { refresh: number }) {
  const [status, setStatus] = useState<LearningStatus | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [pending, setPending] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let cancelled = false;
    getPreferenceStatus().then(data => { if (!cancelled) { setStatus(data); setError(''); } }).catch(err => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [refresh, retry]);
  const train = async () => {
    setPending(true); setError(''); setMessage('');
    try { const data = await trainExercisePreferences(); setStatus(data.status); setMessage(data.message); }
    catch (err) { setError(err instanceof Error ? err.message : 'Training failed.'); }
    finally { setPending(false); }
  };
  const reset = async () => {
    setPending(true); setError('');
    try { await resetExercisePreferences(); setStatus(await getPreferenceStatus()); setMessage('Your exercise preferences have been cleared.'); setConfirmReset(false); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not clear preferences.'); }
    finally { setPending(false); }
  };

  return <Card title="Your exercise preferences" subtitle="Your choices help personalize future alternatives.">
    <div className="space-y-3 text-xs leading-relaxed">
      <p className="text-[var(--text-secondary)]">Use Like, Not for me, or choose a suggested replacement. Removing or replacing an exercise is neutral, because your equipment or plan may have changed.</p>
      {status && <>
        <p className="font-semibold text-[var(--accent-text)]">{status.active ? 'Personalized ranking is active' : 'Collecting your preferences'}</p>
        <p>{status.examples} / {status.minimum_examples} different exercise pairs rated</p>
        <div role="progressbar" aria-label="Feedback collection" aria-valuenow={Math.min(status.examples, status.minimum_examples)} aria-valuemin={0} aria-valuemax={status.minimum_examples} className="w-full h-2 rounded-full bg-[var(--bg-subtle)] overflow-hidden">
          <div className="h-full bg-[var(--accent-primary)] rounded-full" style={{ width: `${Math.min(100, status.examples / status.minimum_examples * 100)}%` }} />
        </div>
        <p className="text-[var(--text-muted)]">{status.positive} positive · {status.negative} negative · {status.unique_exercises} exercises</p>
        {status.neutral_replacements > 0 && <p className="text-[var(--text-muted)]">{status.neutral_replacements} neutral replacements excluded from training.</p>}
        {!status.can_train && <p className="text-[var(--text-secondary)]">Training needs at least {status.minimum_examples} rated pairs, {status.minimum_per_class} positive and {status.minimum_per_class} negative choices across {status.minimum_exercises} exercises.</p>}
        <Button size="sm" onClick={train} disabled={!status.can_train || pending} isLoading={pending} leftIcon={<RefreshCw size={13} />}>{status.active ? 'Update my preferences' : 'Train my preferences'}</Button>
        <p className="text-[var(--text-muted)]">A new model is used only if it beats a simple baseline on separate exercise groups. Otherwise, similarity ranking stays available.</p>
        {status.metrics && <details><summary className="cursor-pointer text-[var(--accent-text)]">Model evaluation</summary><p className="mt-2">Held-out balanced accuracy: {Math.round(status.metrics.balanced_accuracy * 100)}%. Constant baseline: 50%. Evaluated on {status.metrics.test_examples} choices with separate exercise groups. A small personal dataset does not establish performance for other users.</p></details>}
        {(status.examples > 0 || status.neutral_replacements > 0 || status.active) && <div>{confirmReset ? <div className="space-y-2"><p>Clear your feedback and trained model? Your workout routine will stay saved.</p><div className="flex gap-2"><Button size="sm" variant="danger" disabled={pending} onClick={reset}>Clear preferences</Button><Button size="sm" variant="ghost" disabled={pending} onClick={() => setConfirmReset(false)}>Cancel</Button></div></div> : <Button size="sm" variant="ghost" onClick={() => setConfirmReset(true)}>Clear my preferences</Button>}</div>}
      </>}
      {error && <p className="text-rose-400" role="alert">{error} <button type="button" className="underline" onClick={() => setRetry(value => value + 1)}>Retry</button></p>}
      {message && <p role="status">{message}</p>}
    </div>
  </Card>;
}
