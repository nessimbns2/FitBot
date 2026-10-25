/**
 * src/components/AthleteBlueprintModal.tsx
 * AI Athlete Blueprint & Physiological Profile Audit Modal.
 * Generates and presents comprehensive evidence-based strengths, volume landmarks,
 * timeline milestones, and coaching directives.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Dialog, Button, Badge, Skeleton } from '../design';
import {
  Sparkles,
  Award,
  CheckCircle2,
  AlertTriangle,
  TrendingUp,
  Target,
  Dumbbell,
  Zap,
  Activity,
  RotateCcw,
  MessageSquare,
  BookOpen,
  Calendar,
  ShieldAlert,
} from 'lucide-react';
import { UserProfile } from '../context/ProfileContext';
import { getAthleteBlueprint } from '../api/client';

export interface VolumeLandmarks {
  mev_sets_per_week: string;
  mrv_sets_per_week: string;
  recommended_frequency: string;
  recovery_capacity: string;
}

export interface TimelineProjection {
  rate_of_change: string;
  milestone_12_weeks: string;
  milestone_24_weeks: string;
}

export interface AthleteBlueprintData {
  athlete_archetype: string;
  executive_summary: string;
  physiological_strengths: string[];
  blindspots_and_risks: string[];
  volume_landmarks: VolumeLandmarks;
  timeline_projection: TimelineProjection;
  key_coaching_directives: string[];
  calculated_metrics: Record<string, any>;
  sources?: Array<{ source: string; page: number; score: number }>;
}

interface AthleteBlueprintModalProps {
  isOpen: boolean;
  onClose: () => void;
  profile: UserProfile | null;
}

export const AthleteBlueprintModal: React.FC<AthleteBlueprintModalProps> = ({
  isOpen,
  onClose,
  profile,
}) => {
  const navigate = useNavigate();
  const [blueprint, setBlueprint] = useState<AthleteBlueprintData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBlueprint = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getAthleteBlueprint({
        age: profile?.age,
        sex: profile?.sex,
        height_cm: profile?.height_cm,
        weight_kg: profile?.weight_kg,
        body_fat_pct: profile?.body_fat_pct,
        somatotype: profile?.somatotype,
        experience_level: profile?.experience_level,
        goal: profile?.goal,
        activity_level: profile?.activity_level,
      });
      setBlueprint(data);
    } catch (err: any) {
      console.error('Failed to generate athlete blueprint:', err);
      setError(err?.message || 'Failed to generate Athlete Blueprint. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && !blueprint && !isLoading) {
      fetchBlueprint();
    }
  }, [isOpen]);

  const handleDiscussInChat = () => {
    if (!blueprint) return;
    const prompt = `FitBot, I just reviewed my AI Athlete Blueprint (${blueprint.athlete_archetype}). Can you give me specific tips on how to apply my volume landmarks (${blueprint.volume_landmarks?.mev_sets_per_week} to ${blueprint.volume_landmarks?.mrv_sets_per_week}) into my weekly training split?`;
    onClose();
    navigate('/coach', { state: { initialPrompt: prompt } });
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="AI Athlete Blueprint & Profile Audit"
      description="Evidence-based physiological assessment synthesizing biometrics, somatotype, and volume landmarks."
      size="lg"
    >
      <div className="space-y-6 max-h-[75vh] overflow-y-auto pr-1">
        {/* Loading State */}
        {isLoading && (
          <div className="space-y-4 py-8">
            <div className="flex flex-col items-center justify-center text-center space-y-3">
              <div className="relative">
                <div className="w-12 h-12 rounded-2xl bg-[var(--accent-primary-subtle)] border border-[var(--accent-primary)]/40 flex items-center justify-center animate-pulse">
                  <Sparkles className="w-6 h-6 text-[var(--accent-primary)]" />
                </div>
              </div>
              <h4 className="text-sm font-bold text-[var(--text-primary)]">
                Synthesizing Biometrics & Scientific Literature...
              </h4>
              <p className="text-xs text-[var(--text-muted)] max-w-sm">
                Evaluating metabolic rate, volume capacity, and hypertrophy thresholds from verified sports science manuals.
              </p>
            </div>

            <div className="space-y-3 pt-4">
              <Skeleton variant="card" height={100} />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Skeleton variant="card" height={120} />
                <Skeleton variant="card" height={120} />
              </div>
              <Skeleton variant="card" height={80} />
            </div>
          </div>
        )}

        {/* Error State */}
        {!isLoading && error && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-center space-y-3 py-6">
            <AlertTriangle className="w-8 h-8 text-rose-500 mx-auto" />
            <h4 className="text-sm font-bold text-[var(--text-primary)]">Audit Generation Issue</h4>
            <p className="text-xs text-[var(--text-secondary)] max-w-sm mx-auto">{error}</p>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchBlueprint}
              leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
            >
              Retry Analysis
            </Button>
          </div>
        )}

        {/* Blueprint Content */}
        {!isLoading && blueprint && (
          <div className="space-y-5 animate-in fade-in-0 duration-300">
            {/* Header: Athlete Archetype Banner */}
            <div className="p-5 rounded-2xl bg-gradient-to-br from-[var(--accent-primary-subtle)] via-[var(--bg-card)] to-[var(--bg-subtle)] border border-[var(--accent-primary)]/40 relative overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-3 relative z-10">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-black tracking-widest uppercase text-[var(--accent-text)] bg-[var(--bg-app)]/80 px-2 py-0.5 rounded-md border border-[var(--border-subtle)]">
                      Athlete Archetype
                    </span>
                    <Badge variant="accent" size="sm">
                      Evidence Grounded
                    </Badge>
                  </div>
                  <h3 className="text-xl sm:text-2xl font-black text-[var(--text-primary)] tracking-tight flex items-center gap-2 mt-1">
                    <Award className="w-5 h-5 text-[var(--accent-primary)] shrink-0" />
                    {blueprint.athlete_archetype}
                  </h3>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  <Badge variant="neutral" size="sm">
                    {blueprint.calculated_metrics?.somatotype?.toUpperCase() || 'MESOMORPH'}
                  </Badge>
                  <Badge variant="neutral" size="sm">
                    {blueprint.calculated_metrics?.goal?.replace('_', ' ').toUpperCase() || 'HYPERTROPHY'}
                  </Badge>
                  <Badge variant="neutral" size="sm">
                    {blueprint.calculated_metrics?.target_kcal || 2500} KCAL
                  </Badge>
                </div>
              </div>

              {/* Executive Summary */}
              <div className="mt-4 pt-3.5 border-t border-[var(--border-subtle)]/70">
                <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                  {blueprint.executive_summary}
                </p>
              </div>
            </div>

            {/* 2-Column: Strengths & Blindspots */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Strengths */}
              <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20 space-y-3">
                <h4 className="text-xs font-bold text-emerald-500 uppercase tracking-wider flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  Physiological Strengths & Levers
                </h4>
                <ul className="space-y-2">
                  {blueprint.physiological_strengths?.map((str, idx) => (
                    <li key={idx} className="text-xs text-[var(--text-primary)] flex items-start gap-2 leading-relaxed">
                      <span className="text-emerald-500 font-bold shrink-0 mt-0.5">•</span>
                      <span>{str}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Blindspots & Risks */}
              <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 space-y-3">
                <h4 className="text-xs font-bold text-amber-500 uppercase tracking-wider flex items-center gap-1.5">
                  <ShieldAlert className="w-4 h-4 text-amber-500" />
                  Potential Blindspots & Safeguards
                </h4>
                <ul className="space-y-2">
                  {blueprint.blindspots_and_risks?.map((risk, idx) => (
                    <li key={idx} className="text-xs text-[var(--text-secondary)] flex items-start gap-2 leading-relaxed">
                      <span className="text-amber-500 font-bold shrink-0 mt-0.5">•</span>
                      <span>{risk}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Hypertrophy Volume Landmarks */}
            {blueprint.volume_landmarks && (
              <div className="p-4 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-subtle)] space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider flex items-center gap-1.5">
                    <Dumbbell className="w-4 h-4 text-[var(--accent-primary)]" />
                    Hypertrophy Volume Landmarks & Capacity
                  </h4>
                  <Badge variant="accent" size="sm">
                    {blueprint.volume_landmarks.recovery_capacity} Recovery
                  </Badge>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1">
                  <div className="p-3 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] text-center">
                    <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase block">
                      Min Effective Vol (MEV)
                    </span>
                    <span className="text-xs sm:text-sm font-black text-[var(--text-primary)] mt-0.5 block">
                      {blueprint.volume_landmarks.mev_sets_per_week}
                    </span>
                  </div>

                  <div className="p-3 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] text-center">
                    <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase block">
                      Max Recoverable (MRV)
                    </span>
                    <span className="text-xs sm:text-sm font-black text-amber-500 mt-0.5 block">
                      {blueprint.volume_landmarks.mrv_sets_per_week}
                    </span>
                  </div>

                  <div className="p-3 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] text-center">
                    <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase block">
                      Frequency
                    </span>
                    <span className="text-xs sm:text-sm font-black text-[var(--text-primary)] mt-0.5 block">
                      {blueprint.volume_landmarks.recommended_frequency}
                    </span>
                  </div>

                  <div className="p-3 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] text-center">
                    <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase block">
                      Fat-Free Mass / LBM
                    </span>
                    <span className="text-xs sm:text-sm font-black text-emerald-500 mt-0.5 block">
                      {blueprint.calculated_metrics?.lean_mass_kg ? `${blueprint.calculated_metrics.lean_mass_kg} kg` : 'Calculated'}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Timeline Milestones & Periodization */}
            {blueprint.timeline_projection && (
              <div className="p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)] space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider flex items-center gap-1.5">
                    <Calendar className="w-4 h-4 text-[var(--accent-primary)]" />
                    Realistic Progression Milestones
                  </h4>
                  <span className="text-[11px] font-mono text-[var(--accent-text)] font-semibold">
                    Rate: {blueprint.timeline_projection.rate_of_change}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                  <div className="p-3 rounded-lg bg-[var(--bg-subtle)] border border-[var(--border-subtle)] space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-[var(--accent-primary)]" />
                      <span className="text-[11px] font-bold text-[var(--text-primary)] uppercase tracking-wide">
                        12-Week Milestone
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] leading-relaxed pl-4">
                      {blueprint.timeline_projection.milestone_12_weeks}
                    </p>
                  </div>

                  <div className="p-3 rounded-lg bg-[var(--bg-subtle)] border border-[var(--border-subtle)] space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-emerald-500" />
                      <span className="text-[11px] font-bold text-[var(--text-primary)] uppercase tracking-wide">
                        24-Week Transformation
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] leading-relaxed pl-4">
                      {blueprint.timeline_projection.milestone_24_weeks}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Key Coaching Directives */}
            {blueprint.key_coaching_directives?.length > 0 && (
              <div className="p-4 rounded-xl bg-gradient-to-r from-[var(--bg-subtle)] to-[var(--bg-card)] border border-[var(--border-subtle)] space-y-2.5">
                <h4 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider flex items-center gap-1.5">
                  <Target className="w-4 h-4 text-[var(--accent-primary)]" />
                  Key Coaching Directives
                </h4>
                <div className="space-y-2">
                  {blueprint.key_coaching_directives.map((directive, idx) => (
                    <div key={idx} className="flex items-start gap-2.5 text-xs text-[var(--text-secondary)] leading-relaxed">
                      <span className="w-4 h-4 rounded-full bg-[var(--accent-primary)]/10 text-[var(--accent-text)] text-[10px] font-black flex items-center justify-center shrink-0 mt-0.5 border border-[var(--accent-primary)]/30">
                        {idx + 1}
                      </span>
                      <span>{directive}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Literature Sources */}
            {blueprint.sources && blueprint.sources.length > 0 && (
              <div className="p-3 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-subtle)] flex items-center justify-between text-xs text-[var(--text-muted)]">
                <div className="flex items-center gap-1.5">
                  <BookOpen className="w-3.5 h-3.5" />
                  <span>Grounding: {blueprint.sources.map((s) => `${s.source} (p. ${s.page})`).join(', ')}</span>
                </div>
                <Badge variant="neutral" size="sm">
                  Verified RAG
                </Badge>
              </div>
            )}
          </div>
        )}

        {/* Modal Actions */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-[var(--border-subtle)]">
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchBlueprint}
            disabled={isLoading}
            leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
          >
            Re-run Audit
          </Button>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDiscussInChat}
              disabled={isLoading || !blueprint}
              leftIcon={<MessageSquare className="w-3.5 h-3.5" />}
            >
              Discuss with Coach
            </Button>
            <Button variant="primary" size="sm" onClick={onClose}>
              Done
            </Button>
          </div>
        </div>
      </div>
    </Dialog>
  );
};
