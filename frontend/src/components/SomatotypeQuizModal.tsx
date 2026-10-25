/**
 * src/components/SomatotypeQuizModal.tsx
 * Interactive 5-question AI Anthropometric Assessment for predicting physiological Somatotype.
 */

import React, { useState, useEffect } from 'react';
import { Dialog, Button, Badge } from '../design';
import {
  Sparkles,
  ChevronRight,
  ChevronLeft,
  CheckCircle2,
  Dumbbell,
  Apple,
  RotateCcw,
  Zap,
  Activity,
  AlertCircle,
} from 'lucide-react';
import { UserProfile } from '../context/ProfileContext';

interface QuestionOption {
  value: string;
  label: string;
  detail: string;
  archetype: string;
}

interface SomatotypeQuestion {
  id: string;
  title: string;
  question: string;
  options: QuestionOption[];
}

interface SomatotypePredictionResult {
  predicted_somatotype: UserProfile['somatotype'];
  confidence: string;
  secondary_traits?: string | null;
  traits_summary: string;
  training_focus: string;
  nutrition_focus: string;
  macro_shift_note: string;
  profile_updated?: boolean;
}

// Fallback questions if backend is still initializing
const DEFAULT_QUESTIONS: SomatotypeQuestion[] = [
  {
    id: 'wrist_structure',
    title: 'Bone Structure & Wrist Circumference',
    question: 'When you wrap your thumb and middle finger around your opposite wrist:',
    options: [
      {
        value: 'fingers_overlap',
        label: 'Fingers overlap easily',
        detail: 'Small, slender bone structure with narrow wrists and ankles',
        archetype: 'ectomorph',
      },
      {
        value: 'fingers_touch',
        label: 'Fingers just touch each other',
        detail: 'Medium, proportionate bone structure and joint size',
        archetype: 'mesomorph',
      },
      {
        value: 'fingers_do_not_touch',
        label: 'Fingers do not touch at all',
        detail: 'Large, thick bone structure with broad, heavy joints',
        archetype: 'endomorph',
      },
    ],
  },
  {
    id: 'body_frame',
    title: 'Natural Body Frame & Silhouette',
    question: 'What best describes your natural shoulder-to-waist shape and silhouette?',
    options: [
      {
        value: 'narrow_linear',
        label: 'Narrow & Linear (Pencil build)',
        detail: 'Shoulders and hips are narrow and roughly the same width',
        archetype: 'ectomorph',
      },
      {
        value: 'broad_athletic',
        label: 'Athletic V-Taper',
        detail: 'Naturally broad shoulders tapering down to a narrower waist',
        archetype: 'mesomorph',
      },
      {
        value: 'broad_thick',
        label: 'Blocky or Oval Frame',
        detail: 'Broad shoulders with thicker waist and wider hips',
        archetype: 'endomorph',
      },
    ],
  },
  {
    id: 'weight_tendency',
    title: 'Weight Gain & Metabolic Tendency',
    question: 'How does your body typically respond when you try to change your weight?',
    options: [
      {
        value: 'hardgainer',
        label: 'Hardgainer (Fast Metabolism)',
        detail: 'Struggle to gain weight or muscle even when eating in surplus',
        archetype: 'ectomorph',
      },
      {
        value: 'steady_gains',
        label: 'Adaptable & Steady',
        detail: 'Gain lean muscle readily with training and lose fat with moderate deficit',
        archetype: 'mesomorph',
      },
      {
        value: 'easy_fat_gain',
        label: 'Easy Weight Gain (Slower Metabolism)',
        detail: 'Gain weight and muscle easily, but hold onto body fat persistently',
        archetype: 'endomorph',
      },
    ],
  },
  {
    id: 'muscle_definition',
    title: 'Natural Muscle Tone & Definition',
    question: 'Without intensive weight training, what is your default muscle appearance?',
    options: [
      {
        value: 'lean_low_muscle',
        label: 'Lean, Long & Slender',
        detail: 'Long limbs with stringy, flatter muscle bellies and low natural body fat',
        archetype: 'ectomorph',
      },
      {
        value: 'dense_defined',
        label: 'Dense, Firm & Athletic',
        detail: 'Naturally visible muscular contours and firm muscle tone',
        archetype: 'mesomorph',
      },
      {
        value: 'dense_softer',
        label: 'Thick & Solid with Softer Layer',
        detail: 'Dense strength foundation underneath a softer, thicker body fat layer',
        archetype: 'endomorph',
      },
    ],
  },
  {
    id: 'carb_response',
    title: 'Carbohydrate & Energy Response',
    question: 'How do you feel and react after eating a large, carbohydrate-rich meal (e.g. pasta, rice)?',
    options: [
      {
        value: 'high_energy',
        label: 'Energetic & Thermogenic',
        detail: 'Feel warm and energized; rarely store extra carbs as body fat',
        archetype: 'ectomorph',
      },
      {
        value: 'fuel_workout',
        label: 'Well-Fueled for Training',
        detail: 'Utilize carbs efficiently for muscle fullness and gym performance',
        archetype: 'mesomorph',
      },
      {
        value: 'sluggish_bloated',
        label: 'Sluggish, Bloated or Lethargic',
        detail: 'Experience a quick blood sugar dip, water retention, and prone to fat storage',
        archetype: 'endomorph',
      },
    ],
  },
];

interface SomatotypeQuizModalProps {
  isOpen: boolean;
  onClose: () => void;
  onApplySomatotype: (somatotype: UserProfile['somatotype']) => void;
}

import { getSomatotypeQuestions, predictSomatotype } from '../api/client';

export function SomatotypeQuizModal({
  isOpen,
  onClose,
  onApplySomatotype,
}: SomatotypeQuizModalProps) {
  const [questions, setQuestions] = useState<SomatotypeQuestion[]>(DEFAULT_QUESTIONS);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [result, setResult] = useState<SomatotypePredictionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch questions from backend
  useEffect(() => {
    if (!isOpen) return;
    getSomatotypeQuestions()
      .then((data: any) => {
        if (Array.isArray(data) && data.length > 0) {
          setQuestions(data);
        }
      })
      .catch(() => {
        // Fallback to local DEFAULT_QUESTIONS
      });
  }, [isOpen]);

  const handleSelectOption = (questionId: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const handleNext = () => {
    if (currentStep < questions.length - 1) {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleReset = () => {
    setAnswers({});
    setCurrentStep(0);
    setResult(null);
    setError(null);
  };

  const handleSubmit = async () => {
    setIsAnalyzing(true);
    setError(null);

    const payload = {
      wrist_structure: answers['wrist_structure'] || 'fingers_touch',
      body_frame: answers['body_frame'] || 'broad_athletic',
      weight_tendency: answers['weight_tendency'] || 'steady_gains',
      muscle_definition: answers['muscle_definition'] || 'dense_defined',
      carb_response: answers['carb_response'] || 'fuel_workout',
      auto_apply: false,
    };

    try {
      const data = await predictSomatotype(payload);
      setResult(data);
    } catch (err: any) {
      setError(err?.message || 'Error predicting somatotype. Please try again.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const currentQ = questions[currentStep];
  const isCurrentAnswered = currentQ && !!answers[currentQ.id];
  const allAnswered = questions.every((q) => !!answers[q.id]);

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="AI Somatotype Diagnostic Assessment"
      description="Answer 5 anthropometric questions to determine your metabolic profile and optimal training/nutrition split."
      maxWidth="md"
    >
      <div className="space-y-5">
        {/* If result is ready */}
        {result ? (
          <div className="space-y-4 animate-in fade-in-0 duration-300">
            {/* Header Badge & Name */}
            <div className="p-4 rounded-2xl bg-gradient-to-br from-[var(--accent-primary-subtle)] to-[var(--bg-card)] border border-[var(--accent-primary)]/40 text-center">
              <span className="text-[11px] font-bold tracking-widest uppercase text-[var(--accent-text)]">
                Predicted Primary Somatotype
              </span>
              <h3 className="text-2xl font-black text-[var(--text-primary)] uppercase tracking-tight mt-1 flex items-center justify-center gap-2">
                <Sparkles className="w-5 h-5 text-[var(--accent-primary)]" />
                {result.predicted_somatotype}
                {result.secondary_traits && (
                  <span className="text-sm font-semibold text-[var(--text-secondary)] normal-case">
                    ({result.secondary_traits})
                  </span>
                )}
              </h3>
              <div className="flex items-center justify-center gap-2 mt-2">
                <Badge variant="accent" size="sm">
                  Confidence: {result.confidence.toUpperCase()}
                </Badge>
                <Badge variant="neutral" size="sm">
                  Heath-Carter Method
                </Badge>
              </div>
            </div>

            {/* Trait Summary */}
            <div className="p-3.5 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-subtle)]">
              <span className="text-[11px] font-bold text-[var(--text-secondary)] uppercase tracking-wider block mb-1">
                Physiological & Metabolic Tendency
              </span>
              <p className="text-xs text-[var(--text-primary)] leading-relaxed">
                {result.traits_summary}
              </p>
            </div>

            {/* Training & Nutrition Split */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="p-3.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)] space-y-1.5">
                <div className="flex items-center gap-1.5 text-xs font-bold text-[var(--brand-purple)]">
                  <Dumbbell className="w-4 h-4" />
                  <span>Optimal Training Strategy</span>
                </div>
                <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                  {result.training_focus}
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)] space-y-1.5">
                <div className="flex items-center gap-1.5 text-xs font-bold text-[var(--brand-green)]">
                  <Apple className="w-4 h-4" />
                  <span>Nutrition & Macro Shift</span>
                </div>
                <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                  {result.nutrition_focus}
                </p>
                <div className="pt-1 border-t border-[var(--border-subtle)] text-[10px] text-[var(--accent-text)] font-medium">
                  {result.macro_shift_note}
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="pt-3 border-t border-[var(--border-subtle)] flex items-center justify-between gap-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleReset}
                leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
              >
                Retake Quiz
              </Button>
              <Button
                variant="primary"
                size="md"
                onClick={() => {
                  onApplySomatotype(result.predicted_somatotype);
                  onClose();
                }}
                leftIcon={<CheckCircle2 className="w-4 h-4" />}
              >
                Apply {result.predicted_somatotype.toUpperCase()} to Profile
              </Button>
            </div>
          </div>
        ) : (
          /* Active Question Step View */
          <div className="space-y-4">
            {/* Step Progress Bar */}
            <div>
              <div className="flex items-center justify-between text-xs font-semibold mb-1.5">
                <span className="text-[var(--text-secondary)]">
                  Question {currentStep + 1} of {questions.length}
                </span>
                <span className="text-[var(--accent-primary)] font-bold">
                  {Math.round(((currentStep + 1) / questions.length) * 100)}% Complete
                </span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-[var(--bg-subtle)] overflow-hidden">
                <div
                  className="h-full bg-[var(--accent-primary)] transition-all duration-300"
                  style={{ width: `${((currentStep + 1) / questions.length) * 100}%` }}
                />
              </div>
            </div>

            {/* Current Question */}
            <div className="space-y-2">
              <span className="text-[11px] font-bold text-[var(--accent-text)] uppercase tracking-wider block">
                {currentQ?.title}
              </span>
              <h4 className="text-sm font-semibold text-[var(--text-primary)] leading-snug">
                {currentQ?.question}
              </h4>
            </div>

            {/* Options List */}
            <div className="space-y-2.5">
              {currentQ?.options.map((opt) => {
                const isSelected = answers[currentQ.id] === opt.value;
                return (
                  <div
                    key={opt.value}
                    onClick={() => handleSelectOption(currentQ.id, opt.value)}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-start gap-3 ${
                      isSelected
                        ? 'bg-[var(--accent-primary-subtle)] border-[var(--accent-primary)] shadow-xs'
                        : 'bg-[var(--bg-card)] border-[var(--border-subtle)] hover:border-[var(--border-prominent)]'
                    }`}
                  >
                    <div
                      className={`w-4 h-4 rounded-full mt-0.5 border flex items-center justify-center shrink-0 ${
                        isSelected
                          ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)] text-white'
                          : 'border-[var(--border-prominent)]'
                      }`}
                    >
                      {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                    </div>
                    <div className="space-y-0.5">
                      <span className="text-xs font-bold text-[var(--text-primary)] block">
                        {opt.label}
                      </span>
                      <p className="text-[11px] text-[var(--text-secondary)] leading-tight">
                        {opt.detail}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 flex items-center gap-2 text-xs text-red-400">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Navigation buttons */}
            <div className="pt-3 border-t border-[var(--border-subtle)] flex items-center justify-between">
              <Button
                variant="ghost"
                size="sm"
                onClick={handlePrev}
                disabled={currentStep === 0 || isAnalyzing}
                leftIcon={<ChevronLeft className="w-3.5 h-3.5" />}
              >
                Back
              </Button>

              {currentStep < questions.length - 1 ? (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleNext}
                  disabled={!isCurrentAnswered || isAnalyzing}
                  leftIcon={<ChevronRight className="w-3.5 h-3.5" />}
                >
                  Next
                </Button>
              ) : (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleSubmit}
                  disabled={!allAnswered || isAnalyzing}
                  isLoading={isAnalyzing}
                  leftIcon={<Sparkles className="w-3.5 h-3.5" />}
                >
                  {isAnalyzing ? 'Predicting Somatotype...' : 'Predict My Somatotype with AI'}
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </Dialog>
  );
}
