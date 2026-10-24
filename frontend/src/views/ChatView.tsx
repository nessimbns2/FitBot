/**
 * src/views/ChatView.tsx
 * Complete redesign of Coach Chat:
 * - Single centered 760px conversation stream
 * - Collapsible conversations drawer / slide-in panel (not a rigid permanent sidebar)
 * - Empty state with friendly greeting, 2x2 starter cards, and quick-action chips
 * - Floating rounded composer with auto-grow textarea, send & stop generation buttons
 * - Assistant messages: clean markdown, subtle intent badge, compact expandable source chips
 * - Inline confirmation card for pending workout logs with editable fields
 */

import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  listSessions,
  getSessionMessages,
  deleteSession,
  streamChatMessage,
  logWorkoutSet,
} from '../api/client';
import {
  PageHeader,
  Button,
  Badge,
  Drawer,
  Toast,
} from '../design';
import {
  MessageSquare,
  Plus,
  Trash2,
  Send,
  Square,
  Sparkles,
  FileText,
  ChevronDown,
  ChevronUp,
  Check,
  X,
  History,
  Dumbbell,
  Utensils,
  BookOpen,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
} from 'lucide-react';

interface ChatSession {
  id: string;
  title?: string;
  created_at?: string;
}

interface MessageSource {
  source: string;
  page: number;
  text?: string;
  score?: number;
}

interface PendingWorkoutAction {
  exercise_id: string;
  exercise_name: string;
  sets: number;
  reps: number;
  weight: number;
  rpe?: number;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: MessageSource[];
  pendingAction?: PendingWorkoutAction | null;
}

const STARTER_PROMPTS = [
  {
    icon: Dumbbell,
    title: 'Technique Breakdown',
    prompt: 'How do I optimize foot positioning and leg drive for the barbell bench press?',
  },
  {
    icon: Utensils,
    title: 'Macronutrient Timing',
    prompt: 'What does sports science suggest for protein distribution and peri-workout carbs?',
  },
  {
    icon: TrendingUp,
    title: 'Double Progression',
    prompt: 'Explain how double progression works when I reach the top of my rep target range.',
  },
  {
    icon: Sparkles,
    title: 'Log Workout Naturally',
    prompt: 'Log bench press 82.5 kg for 3 sets of 8 reps at RPE 8.0.',
  },
];

export function ChatView() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [isHistoryDrawerOpen, setIsHistoryDrawerOpen] = useState<boolean>(false);

  // Expanded sources tracking
  const [expandedSources, setExpandedSources] = useState<Record<number, boolean>>({});

  // Pending workout log confirmation card
  const [pendingAction, setPendingAction] = useState<PendingWorkoutAction | null>(null);
  const [isCommittingAction, setIsCommittingAction] = useState<boolean>(false);

  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  // Auto-grow textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [inputMessage]);

  const loadSessions = async () => {
    try {
      const data = await listSessions();
      setSessions(data || []);
      if (data && data.length > 0 && !activeSessionId) {
        selectSession(data[data.length - 1].id);
      }
    } catch (err) {
      console.error('Error fetching chat sessions:', err);
    }
  };

  const selectSession = async (sessionId: string) => {
    setActiveSessionId(sessionId);
    setIsHistoryDrawerOpen(false);
    try {
      const msgs = await getSessionMessages(sessionId);
      setMessages(msgs || []);
      setPendingAction(null);
      setExpandedSources({});
    } catch (err) {
      console.error('Error loading session messages:', err);
    }
  };

  const handleNewSession = () => {
    setActiveSessionId(null);
    setMessages([]);
    setPendingAction(null);
    setExpandedSources({});
    setIsHistoryDrawerOpen(false);
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      await deleteSession(sessionId);
      if (activeSessionId === sessionId) {
        handleNewSession();
      }
      loadSessions();
    } catch (err) {
      console.error('Error deleting session:', err);
    }
  };

  const toggleSource = (msgIndex: number) => {
    setExpandedSources((prev) => ({
      ...prev,
      [msgIndex]: !prev[msgIndex],
    }));
  };

  const handleSendMessage = async (customPrompt?: string) => {
    const textToSend = customPrompt || inputMessage;
    if (!textToSend.trim() || isStreaming) return;

    setInputMessage('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';

    const userMsg: ChatMessage = { role: 'user', content: textToSend };
    setMessages((prev) => [...prev, userMsg]);
    setIsStreaming(true);

    let botMsgContent = '';
    let sources: MessageSource[] = [];

    setMessages((prev) => [
      ...prev,
      { role: 'assistant', content: '', sources: [] },
    ]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await streamChatMessage(textToSend, activeSessionId, {
        onToken: (token: string) => {
          botMsgContent += token;
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = {
              role: 'assistant',
              content: botMsgContent,
              sources,
            };
            return next;
          });
        },
        onSources: (retrievedSources: MessageSource[]) => {
          sources = retrievedSources;
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = {
              ...next[next.length - 1],
              sources,
            };
            return next;
          });
        },
        onPendingAction: (actionPayload: any) => {
          if (actionPayload?.action === 'log_workout' || actionPayload?.exercise_id) {
            setPendingAction({
              exercise_id: actionPayload.exercise_id || 'barbell-bench-press',
              exercise_name: actionPayload.exercise_name || actionPayload.exercise_id,
              sets: actionPayload.sets || 3,
              reps: actionPayload.reps || 8,
              weight: actionPayload.weight || 80,
              rpe: actionPayload.rpe || 8.0,
            });
          }
        },
        onMeta: (meta: any) => {
          if (meta?.session_id && !activeSessionId) {
            setActiveSessionId(meta.session_id);
            loadSessions();
          }
        },
        onError: (errMsg: string) => {
          setToast({ type: 'error', message: errMsg || 'Failed to generate response' });
        },
        signal: controller.signal,
      });

    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error('Chat stream error:', err);
        setToast({ type: 'error', message: err.message || 'Stream connection interrupted' });
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  };

  const handleStopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
    }
  };

  const handleConfirmLog = async () => {
    if (!pendingAction || isCommittingAction) return;
    setIsCommittingAction(true);

    const payload = Array.from({ length: pendingAction.sets }).map((_, idx) => ({
      exercise_id: pendingAction.exercise_id,
      set_number: idx + 1,
      reps: pendingAction.reps,
      weight: pendingAction.weight,
      unit: 'kg',
      rpe: pendingAction.rpe || 8.0,
      rir: Math.max(0, Math.min(5, Math.round(10 - (pendingAction.rpe || 8.0)))),
      performed_at: new Date().toISOString(),
    }));

    try {
      await logWorkoutSet(payload);
      setToast({ type: 'success', message: `Logged ${pendingAction.sets} sets of ${pendingAction.exercise_name}!` });
      setPendingAction(null);
    } catch (err: any) {
      setToast({ type: 'error', message: err.message || 'Failed to commit workout sets' });
    } finally {
      setIsCommittingAction(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[var(--bg-app)] text-[var(--text-primary)] transition-colors duration-200 overflow-hidden">
      {/* Top Header */}
      <div className="h-16 border-b border-[var(--border-subtle)] px-6 flex items-center justify-between bg-[var(--bg-card)]/80 backdrop-blur-md shrink-0 z-10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-[var(--accent-primary)] flex items-center justify-center text-white shadow-xs">
            <MessageSquare className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-[var(--text-primary)] tracking-tight">
              Evidence-Based AI Coach
            </h2>
            <p className="text-[11px] text-[var(--text-muted)]">
              RAG answers from verified sports science manuals
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsHistoryDrawerOpen(true)}
            leftIcon={<History className="w-3.5 h-3.5" />}
          >
            History ({sessions.length})
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleNewSession}
            leftIcon={<Plus className="w-3.5 h-3.5" />}
          >
            New Chat
          </Button>
        </div>
      </div>

      {/* Main Single Conversation Stream (Centered ~760px) */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8 space-y-6">
        <div className="max-w-[760px] mx-auto space-y-6">
          {messages.length === 0 ? (
            /* Empty State */
            <div className="py-10 text-center space-y-8 animate-in fade-in-0 duration-300">
              <div className="max-w-md mx-auto space-y-3">
                <div className="w-14 h-14 rounded-2xl bg-[var(--accent-primary-subtle)] border border-[var(--accent-primary-border)] text-[var(--accent-text)] flex items-center justify-center mx-auto shadow-xs">
                  <Sparkles className="w-7 h-7" />
                </div>
                <h1 className="text-2xl font-black text-[var(--text-primary)] tracking-tight">
                  How can I guide your training today?
                </h1>
                <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                  Ask about technique cues, nutrition timing, or speak naturally to log your sets directly to history.
                </p>
              </div>

              {/* 2x2 Starter Prompts Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
                {STARTER_PROMPTS.map((item, idx) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handleSendMessage(item.prompt)}
                      className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] hover:border-[var(--border-prominent)] shadow-xs hover:shadow-md transition-all text-left cursor-pointer group space-y-1.5"
                    >
                      <div className="flex items-center gap-2 text-xs font-bold text-[var(--text-primary)] group-hover:text-[var(--accent-text)] transition-colors">
                        <Icon className="w-4 h-4 text-[var(--accent-primary)]" />
                        <span>{item.title}</span>
                      </div>
                      <p className="text-[11px] text-[var(--text-secondary)] line-clamp-2 leading-relaxed">
                        {item.prompt}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            /* Message Bubbles */
            messages.map((msg, idx) => {
              const isUser = msg.role === 'user';
              return (
                <div
                  key={idx}
                  className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} animate-in fade-in-0 duration-200`}
                >
                  <div
                    className={`max-w-[88%] sm:max-w-[80%] rounded-2xl p-4 sm:p-5 text-xs sm:text-sm leading-relaxed ${
                      isUser
                        ? 'bg-[var(--accent-primary)] text-white shadow-xs rounded-br-xs'
                        : 'bg-[var(--bg-card)] text-[var(--text-primary)] border border-[var(--border-subtle)] shadow-xs rounded-bl-xs'
                    }`}
                  >
                    {!isUser && (
                      <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-[var(--accent-text)] mb-2">
                        <Sparkles className="w-3 h-3" />
                        FitBot Evidence Coach
                      </div>
                    )}

                    <div className="prose prose-xs sm:prose-sm max-w-none text-current space-y-2">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>

                    {/* Expandable Source Citations */}
                    {!isUser && msg.sources && msg.sources.length > 0 && (
                      <div className="mt-4 pt-3 border-t border-[var(--border-subtle)]">
                        <button
                          type="button"
                          onClick={() => toggleSource(idx)}
                          className="flex items-center gap-1.5 text-[11px] font-semibold text-[var(--text-muted)] hover:text-[var(--accent-text)] transition-colors cursor-pointer"
                        >
                          <FileText className="w-3.5 h-3.5" />
                          <span>Sources ({msg.sources.length})</span>
                          {expandedSources[idx] ? (
                            <ChevronUp className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronDown className="w-3.5 h-3.5" />
                          )}
                        </button>

                        {expandedSources[idx] && (
                          <div className="mt-2.5 space-y-2">
                            {msg.sources.map((src, sIdx) => (
                              <div
                                key={sIdx}
                                className="p-3 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[11px] text-[var(--text-secondary)] space-y-1.5"
                              >
                                <div className="flex items-center justify-between text-[10px] font-mono text-[var(--accent-text)] font-semibold">
                                  <div className="flex items-center gap-2 min-w-0">
                                    <span className="px-1.5 py-0.5 rounded bg-[var(--accent-subtle)] text-[var(--accent-text)] font-bold shrink-0">
                                      [{sIdx + 1}]
                                    </span>
                                    <span className="truncate max-w-[280px]" title={src.source}>
                                      {src.source}
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-2 shrink-0">
                                    {typeof src.score === 'number' && (
                                      <span className="text-[var(--text-muted)] font-normal">
                                        {Math.round(src.score * 100)}% match
                                      </span>
                                    )}
                                    <span>Page {src.page}</span>
                                  </div>
                                </div>
                                {src.text ? (
                                  <p className="text-[11px] text-[var(--text-secondary)] italic leading-relaxed pl-2 border-l-2 border-[var(--border-subtle)]">
                                    "{src.text}"
                                  </p>
                                ) : null}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}

          {/* Pending Workout Action Confirmation Card */}
          {pendingAction && (
            <div className="p-5 rounded-2xl bg-[var(--bg-card)] border-2 border-[var(--accent-primary)] shadow-lg space-y-4 animate-in slide-in-from-bottom-2 duration-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-bold text-[var(--accent-text)] uppercase tracking-wider">
                  <Dumbbell className="w-4 h-4" /> Pending Workout Set Confirmation
                </div>
                <button
                  type="button"
                  onClick={() => setPendingAction(null)}
                  className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Coach extracted the following workout data from your message. Review and confirm before writing to your permanent history.
              </p>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-2.5 bg-[var(--bg-subtle)] rounded-xl border border-[var(--border-subtle)]">
                  <span className="text-[10px] text-[var(--text-muted)] block">Movement</span>
                  <span className="text-xs font-bold text-[var(--text-primary)] truncate block">
                    {pendingAction.exercise_name}
                  </span>
                </div>
                <div className="p-2.5 bg-[var(--bg-subtle)] rounded-xl border border-[var(--border-subtle)]">
                  <span className="text-[10px] text-[var(--text-muted)] block">Sets</span>
                  <input
                    type="number"
                    value={pendingAction.sets}
                    onChange={(e) =>
                      setPendingAction({ ...pendingAction, sets: Number(e.target.value) })
                    }
                    className="w-full bg-transparent text-xs font-sans tabular-nums font-bold text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
                <div className="p-2.5 bg-[var(--bg-subtle)] rounded-xl border border-[var(--border-subtle)]">
                  <span className="text-[10px] text-[var(--text-muted)] block">Reps</span>
                  <input
                    type="number"
                    value={pendingAction.reps}
                    onChange={(e) =>
                      setPendingAction({ ...pendingAction, reps: Number(e.target.value) })
                    }
                    className="w-full bg-transparent text-xs font-sans tabular-nums font-bold text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
                <div className="p-2.5 bg-[var(--bg-subtle)] rounded-xl border border-[var(--border-subtle)]">
                  <span className="text-[10px] text-[var(--text-muted)] block">Weight (kg)</span>
                  <input
                    type="number"
                    step="0.5"
                    value={pendingAction.weight}
                    onChange={(e) =>
                      setPendingAction({ ...pendingAction, weight: Number(e.target.value) })
                    }
                    className="w-full bg-transparent text-xs font-sans tabular-nums font-bold text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="ghost" size="sm" onClick={() => setPendingAction(null)}>
                  Discard
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleConfirmLog}
                  isLoading={isCommittingAction}
                  leftIcon={<Check className="w-3.5 h-3.5" />}
                >
                  Confirm & Commit Sets
                </Button>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Floating Composer Container */}
      <div className="p-4 sm:p-6 border-t border-[var(--border-subtle)] bg-[var(--bg-card)]/90 backdrop-blur-md shrink-0">
        <div className="max-w-[760px] mx-auto space-y-2">
          {/* Quick Action Chips above Composer */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
            <span className="text-[11px] font-semibold text-[var(--text-muted)] shrink-0">Quick prompts:</span>
            {[
              { label: 'Log workout set', text: 'Log 3 sets of Barbell Bench Press at 80kg for 8 reps' },
              { label: 'Check macro goals', text: 'What are my target calories and protein goals for today?' },
              { label: 'Squat form cues', text: 'Give me key execution cues for the barbell back squat' },
            ].map((chip, cIdx) => (
              <button
                key={cIdx}
                type="button"
                onClick={() => handleSendMessage(chip.text)}
                className="px-2.5 py-1 rounded-lg bg-[var(--bg-subtle)] hover:bg-[var(--accent-primary-subtle)] border border-[var(--border-subtle)] hover:border-[var(--accent-primary-border)] text-[var(--text-secondary)] hover:text-[var(--accent-text)] text-[11px] font-medium whitespace-nowrap transition-colors cursor-pointer"
              >
                {chip.label}
              </button>
            ))}
          </div>

          {/* Floating Composer Card with Auto-Grow Textarea */}
          <div className="relative rounded-2xl bg-[var(--bg-card)] border border-[var(--border-prominent)] shadow-md p-2 flex items-end gap-2 focus-within:ring-2 focus-within:ring-[var(--border-focused)] focus-within:border-transparent transition-all">
            <textarea
              ref={textareaRef}
              rows={1}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything or log sets, e.g. 'Bench press 80kg 3x8 @ RPE 8'..."
              className="flex-1 bg-transparent text-xs sm:text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none p-2 resize-none max-h-40 leading-relaxed"
            />

            {isStreaming ? (
              <button
                type="button"
                onClick={handleStopStreaming}
                aria-label="Stop generation"
                className="w-10 h-10 rounded-xl bg-rose-600 text-white flex items-center justify-center hover:bg-rose-700 transition-colors cursor-pointer shrink-0"
              >
                <Square className="w-4 h-4 fill-current" />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => handleSendMessage()}
                disabled={!inputMessage.trim()}
                aria-label="Send message"
                className="w-10 h-10 rounded-xl bg-[var(--accent-primary)] text-white flex items-center justify-center hover:bg-[var(--accent-primary-hover)] disabled:opacity-40 disabled:pointer-events-none transition-colors cursor-pointer shrink-0 shadow-xs"
              >
                <Send className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* History Drawer */}
      <Drawer
        isOpen={isHistoryDrawerOpen}
        onClose={() => setIsHistoryDrawerOpen(false)}
        title="Conversation History"
        description="Select a past coaching thread or start fresh."
      >
        <div className="space-y-2">
          {sessions.length === 0 ? (
            <p className="text-xs text-[var(--text-muted)] text-center py-6">
              No previous conversation threads.
            </p>
          ) : (
            sessions.map((s) => (
              <div
                key={s.id}
                onClick={() => selectSession(s.id)}
                className={`group flex items-center justify-between p-3 rounded-xl border text-xs cursor-pointer transition-all ${
                  activeSessionId === s.id
                    ? 'bg-[var(--accent-primary-subtle)] border-[var(--accent-primary)] text-[var(--accent-text)] font-semibold'
                    : 'bg-[var(--bg-card)] border-[var(--border-subtle)] hover:border-[var(--border-prominent)] text-[var(--text-primary)]'
                }`}
              >
                <div className="flex items-center gap-2 truncate pr-2">
                  <MessageSquare className="w-4 h-4 shrink-0 text-[var(--text-muted)]" />
                  <span className="truncate">{s.title || 'Coaching Session'}</span>
                </div>
                <button
                  type="button"
                  onClick={(e) => handleDeleteSession(e, s.id)}
                  aria-label="Delete session"
                  className="opacity-0 group-hover:opacity-100 p-1 text-[var(--text-muted)] hover:text-rose-500 rounded transition-all cursor-pointer"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))
          )}
        </div>
      </Drawer>

      {toast && (
        <Toast
          type={toast.type}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}
