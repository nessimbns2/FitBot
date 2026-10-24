/**
 * src/api/client.js
 * Centralized API client for Fitness Coach FastAPI backend.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = 'API request failed';
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorData.message || JSON.stringify(errorData);
    } catch {
      errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    }
    throw new Error(errorDetail);
  }

  if (response.status === 204) return null;
  return response.json();
}

// ── User & Profile ────────────────────────────────────────────────────────────

export async function getProfile() {
  return request('/api/user/profile');
}

export async function updateProfile(data) {
  return request('/api/user/profile', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function listSessions() {
  return request('/api/user/sessions');
}

export async function getSessionMessages(sessionId) {
  return request(`/api/user/sessions/${sessionId}/messages`);
}

export async function deleteSession(sessionId) {
  return request(`/api/user/sessions/${sessionId}`, {
    method: 'DELETE',
  });
}

// ── Nutrition ─────────────────────────────────────────────────────────────────

export async function calculateMacros(data) {
  return request('/api/nutrition/calculate-macros', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getMealPlan(data, includeGuidance = false) {
  const url = includeGuidance ? '/api/nutrition/plan?include_guidance=true' : '/api/nutrition/plan';
  return request(url, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function askNutrition(question) {
  return request('/api/nutrition/ask', {
    method: 'POST',
    body: JSON.stringify({ question }),
  });
}

// ── Exercises ─────────────────────────────────────────────────────────────────

export async function getCatalogExercises(filters = {}) {
  const params = new URLSearchParams();
  if (filters.muscle) params.append('muscle', filters.muscle);
  if (filters.equipment) params.append('equipment', filters.equipment);
  if (filters.pattern) params.append('pattern', filters.pattern);
  if (filters.q) params.append('q', filters.q);

  const query = params.toString() ? `?${params.toString()}` : '';
  return request(`/api/exercises/catalog${query}`);
}

export async function getExercise(exerciseId) {
  return request(`/api/exercises/catalog/${exerciseId}`);
}

export async function generateRoutine(data) {
  return request('/api/exercises/generate-routine', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getFormCue(exerciseId, question = null) {
  return request('/api/exercises/form-cue', {
    method: 'POST',
    body: JSON.stringify({ exercise_id: exerciseId, question }),
  });
}

export async function getBodyTypeGuidance() {
  return request('/api/exercises/body-type-guidance');
}

export async function getAISuggestExercise(routineData, goal = 'hypertrophy', experienceLevel = 'intermediate') {
  return request('/api/exercises/ai-suggest-exercise', {
    method: 'POST',
    body: JSON.stringify({
      routine: routineData,
      goal,
      experience_level: experienceLevel,
    }),
  });
}

// ── Progressive Overload ──────────────────────────────────────────────────────

export async function logWorkoutSet(setData) {
  return request('/api/overload/log-set', {
    method: 'POST',
    body: JSON.stringify(setData),
  });
}

export async function getExerciseHistory(exerciseId, limit = 50) {
  return request(`/api/overload/history/${exerciseId}?limit=${limit}`);
}

export async function getRecommendation(exerciseId, algorithm = 'double') {
  return request(`/api/overload/recommendation/${exerciseId}?algorithm=${algorithm}`);
}

export async function getWeeklyVolume(weekStart = null) {
  const url = weekStart ? `/api/overload/volume?week_start=${weekStart}` : '/api/overload/volume';
  return request(url);
}

// ── Chat & Streaming ──────────────────────────────────────────────────────────

export async function sendChatMessage(message, sessionId = null) {
  return request('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ message, session_id: sessionId }),
  });
}

export async function streamChatMessage(
  message,
  sessionId,
  optionsOrOnToken,
  onSourcesPositional,
  onPendingActionPositional,
  onMetaPositional,
  signalPositional
) {
  let onMeta, onSources, onToken, onPendingAction, onDone, onError, signal;

  if (typeof optionsOrOnToken === 'function') {
    // Positional signature
    onToken = optionsOrOnToken;
    onSources = onSourcesPositional;
    onPendingAction = onPendingActionPositional;
    onMeta = onMetaPositional;
    signal = signalPositional;
  } else if (optionsOrOnToken && typeof optionsOrOnToken === 'object') {
    // Object signature
    ({ onMeta, onSources, onToken, onPendingAction, onDone, onError, signal } = optionsOrOnToken);
  }

  const url = `${API_BASE}/api/chat/stream`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP error ${response.status}`);
  }


  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split(/(?:\r?\n){2}/);
    buffer = chunks.pop() || '';

    for (const chunk of chunks) {
      if (!chunk.trim()) continue;

      let currentEvent = 'message';
      const dataLines = [];

      for (const rawLine of chunk.split(/\r?\n/)) {
        const line = rawLine.trim();
        if (line.startsWith('event:')) {
          currentEvent = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trim());
        }
      }

      if (dataLines.length > 0) {
        const rawData = dataLines.join('\n');
        try {
          const data = JSON.parse(rawData);
          if (currentEvent === 'meta' && onMeta) onMeta(data);
          else if (currentEvent === 'sources' && onSources) onSources(data);
          else if (currentEvent === 'token' && onToken) onToken(data.token);
          else if (currentEvent === 'pending_action' && onPendingAction) onPendingAction(data);
          else if (currentEvent === 'done' && onDone) onDone(data);
          else if (currentEvent === 'error' && onError) onError(data.error);
        } catch (err) {
          console.error('SSE JSON parse error:', err, 'raw:', rawData);
        }
      }
    }
  }

}
