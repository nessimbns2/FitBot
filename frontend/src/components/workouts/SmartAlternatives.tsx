import { useEffect, useState } from 'react';
import { ArrowLeftRight, ThumbsDown, ThumbsUp } from 'lucide-react';
import { Button } from '../../design';
import { getExerciseAlternatives, recordExerciseFeedback } from '../../api/client';

export interface AlternativeExercise {
  id: string;
  name: string;
  primary_muscle: string;
  secondary_muscles: string[];
  equipment: string;
  movement_pattern: string;
  difficulty: 'beginner' | 'intermediate' | 'advanced';
}

interface Suggestion {
  recommendation_id: string;
  exercise: AlternativeExercise;
  similarity: number;
  reason: string;
}

interface Props {
  sourceId: string;
  equipment: string;
  availableEquipment: string[];
  excludeIds: string[];
  onSelect: (exercise: AlternativeExercise, recommendationId?: string) => Promise<void>;
  onFeedback: () => void;
}

export function SmartAlternatives({ sourceId, equipment, availableEquipment, excludeIds, onSelect, onFeedback }: Props) {
  const [result, setResult] = useState<{ alternatives: Suggestion[]; method: string; message: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [pending, setPending] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Record<string, string>>({});
  const [retry, setRetry] = useState(0);
  const excludedKey = excludeIds.join(',');
  const equipmentKey = availableEquipment.join(',');

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    setLoading(true); setError(''); setResult(null); setFeedback({});
    getExerciseAlternatives({
      exercise_id: sourceId,
      available_equipment: equipmentKey.split(',').filter(value => value && (equipment === 'all' || value === equipment)),
      exclude_ids: excludedKey ? excludedKey.split(',') : [],
    }, controller.signal)
      .then((data) => { if (!cancelled) setResult(data); })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; controller.abort(); };
  }, [sourceId, equipment, equipmentKey, excludedKey, retry]);

  const rate = async (id: string, action: string) => {
    setPending(id); setError('');
    try {
      await recordExerciseFeedback(id, action);
      setFeedback(previous => ({ ...previous, [id]: action }));
      onFeedback();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not save feedback.'); }
    finally { setPending(null); }
  };

  const select = async (suggestion: Suggestion) => {
    setPending(suggestion.recommendation_id); setError('');
    try { await onSelect(suggestion.exercise, suggestion.recommendation_id); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not save the exercise.'); }
    finally { setPending(null); }
  };

  return (
    <section className="rounded-xl border border-[var(--accent-primary-border)] bg-[var(--accent-primary-subtle)] p-4 space-y-3" aria-labelledby="smart-alternatives-title">
      <div><h3 id="smart-alternatives-title" className="text-sm font-bold flex items-center gap-2"><ArrowLeftRight size={16} aria-hidden />Smart alternatives</h3>
        <p className="text-xs text-[var(--text-secondary)] mt-1">Matches your target muscle, available equipment and experience. Similarity measures exercise characteristics.</p></div>
      {loading && <p className="text-xs" role="status">Finding alternatives…</p>}
      {error && <div role="alert" className="text-xs text-rose-400">{error} <button type="button" className="underline" onClick={() => setRetry(value => value + 1)}>Try again</button></div>}
      {result?.method === 'personalized_logistic_regression' && <p className="text-xs text-[var(--accent-text)]">Your feedback also helps order these matches.</p>}
      {result?.alternatives.map(suggestion => (
        <article key={suggestion.recommendation_id} className="border-t border-[var(--border-subtle)] pt-3 space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-semibold text-sm">{suggestion.exercise.name}</h4><span className="text-xs text-[var(--accent-text)]">{Math.round(suggestion.similarity * 100)}% similarity</span></div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{suggestion.reason}</p>
          <div className="flex flex-wrap gap-2 items-center">
            <Button size="sm" disabled={pending !== null} onClick={() => select(suggestion)}>Use this exercise</Button>
            <Button size="sm" variant="ghost" aria-pressed={feedback[suggestion.recommendation_id] === 'liked'} disabled={pending !== null} leftIcon={<ThumbsUp size={13} />} onClick={() => rate(suggestion.recommendation_id, 'liked')}>Like</Button>
            <Button size="sm" variant="ghost" aria-pressed={feedback[suggestion.recommendation_id] === 'disliked'} disabled={pending !== null} leftIcon={<ThumbsDown size={13} />} onClick={() => rate(suggestion.recommendation_id, 'disliked')}>Not for me</Button>
            {feedback[suggestion.recommendation_id] && <span className="text-xs text-[var(--accent-text)]" role="status">Feedback saved</span>}
          </div>
        </article>
      ))}
      {result?.message && <p className="text-xs text-[var(--text-muted)]">{result.message}</p>}
    </section>
  );
}
