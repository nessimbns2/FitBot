/**
 * src/api/client.js
 * Centralized API client for Fitness Coach FastAPI backend.
 * Every request carries the JWT access token; a 401 on an authenticated call logs the user out.
 */

// Same-origin by default: Vite (dev) and nginx (Docker) proxy /api to the FastAPI backend,
// so the app works whatever port it is served on and no CORS preflight is needed.
const API_BASE = import.meta.env.VITE_API_URL || '';
const TOKEN_KEY = 'fitbot_access_token';

// ── Token storage ─────────────────────────────────────────────────────────────

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable (private mode): the session lasts until reload */
  }
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function handleUnauthorized() {
  setToken(null);
  window.dispatchEvent(new Event('fitbot:unauthorized'));
}

// FastAPI sends validation errors (422) as a list of {loc, msg}; turn them into text.
function formatErrorDetail(detail) {
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc.filter((part) => part !== 'body').join('.') : '';
        return field ? `${field}: ${d.msg}` : d.msg;
      })
      .join('; ');
  }
  return detail;
}

async function request(endpoint, options = {}) {
  const { auth = true, ...fetchOptions } = options;
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(auth ? authHeaders() : {}),
    ...(fetchOptions.headers || {}),
  };

  let response;
  try {
    response = await fetch(url, {
      ...fetchOptions,
      headers,
    });
  } catch {
    throw new Error('Cannot reach the FitBot server. Is the backend running?');
  }

  if (response.status === 401 && auth) {
    handleUnauthorized();
  }

  if (!response.ok) {
    let errorDetail = 'API request failed';
    try {
      const errorData = await response.json();
      const detail = formatErrorDetail(errorData.detail ?? errorData.message ?? errorData.error);
      errorDetail = typeof detail === 'string' && detail ? detail : JSON.stringify(errorData);
    } catch {
      errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    }
    if (response.status === 429) errorDetail = 'Too many attempts. Please wait a minute and try again.';
    const err = new Error(errorDetail);
    err.status = response.status;
    throw err;
  }

  if (response.status === 204) return null;
  return response.json();
}

// ── Authentication ────────────────────────────────────────────────────────────

export async function register(fullName, email, password) {
  return request('/api/auth/register', {
    method: 'POST',
    auth: false,
    body: JSON.stringify({ full_name: fullName, email, password }),
  });
}

export async function login(email, password) {
  return request('/api/auth/login', {
    method: 'POST',
    auth: false,
    body: JSON.stringify({ email, password }),
  });
}

export async function getMe() {
  return request('/api/auth/me');
}

export async function updateMe(fullName) {
  return request('/api/auth/me', {
    method: 'PUT',
    body: JSON.stringify({ full_name: fullName }),
  });
}

export async function changePassword(currentPassword, newPassword) {
  return request('/api/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}

export async function deleteAccount(password) {
  return request('/api/auth/me', {
    method: 'DELETE',
    body: JSON.stringify({ password }),
  });
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

export async function getSomatotypeQuestions() {
  return request('/api/user/somatotype-questions');
}

export async function predictSomatotype(data) {
  return request('/api/user/predict-somatotype', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getAthleteBlueprint(overrides = {}) {
  return request('/api/user/blueprint', {
    method: 'POST',
    body: JSON.stringify(overrides),
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

export async function scanMealPhoto(imageBase64, mimeType = 'image/jpeg', mealSlot = null) {
  return request('/api/nutrition/scan-meal', {
    method: 'POST',
    body: JSON.stringify({
      image_base64: imageBase64,
      mime_type: mimeType,
      meal_slot: mealSlot,
    }),
  });
}

// ── Meal diary (persisted in PostgreSQL) ─────────────────────────────────────

export async function listMeals(day = null) {
  return request(day ? `/api/nutrition/meals?day=${day}` : '/api/nutrition/meals');
}

export async function createMeal(meal) {
  return request('/api/nutrition/meals', {
    method: 'POST',
    body: JSON.stringify(meal),
  });
}

export async function deleteMeal(mealId) {
  return request(`/api/nutrition/meals/${mealId}`, { method: 'DELETE' });
}

// ── Saved routine (persisted in PostgreSQL) ──────────────────────────────────

export async function getSavedRoutine() {
  return request('/api/exercises/routine');
}

export async function saveRoutine(split, daysPerWeek, routine) {
  return request('/api/exercises/routine', {
    method: 'PUT',
    body: JSON.stringify({ split, days_per_week: Number(daysPerWeek), routine }),
  });
}

export async function deleteSavedRoutine() {
  return request('/api/exercises/routine', { method: 'DELETE' });
}

// ── Nutrition: food log (diary) ───────────────────────────────────────────────

export async function listFoodLog(date = null) {
  const query = date ? `?date=${encodeURIComponent(date)}` : '';
  return request(`/api/nutrition/log${query}`);
}

export async function getDailySummary(date = null) {
  const query = date ? `?date=${encodeURIComponent(date)}` : '';
  return request(`/api/nutrition/log/summary${query}`);
}

export async function createFoodLogEntry(data) {
  return request('/api/nutrition/log', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateFoodLogEntry(entryId, data) {
  return request(`/api/nutrition/log/${entryId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteFoodLogEntry(entryId) {
  return request(`/api/nutrition/log/${entryId}`, { method: 'DELETE' });
}

export async function suggestMeal(data = {}) {
  return request('/api/nutrition/suggest-meal', {
    method: 'POST',
    body: JSON.stringify(data),
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

export async function getPlateauDiagnosis(exerciseId, options = {}) {
  return request('/api/overload/diagnosis', {
    method: 'POST',
    body: JSON.stringify({ exercise_id: exerciseId, ...options }),
  });
}

export async function applyDeload(exerciseId, options = {}) {
  return request('/api/overload/apply-deload', {
    method: 'POST',
    body: JSON.stringify({ exercise_id: exerciseId, ...options }),
  });
}

export async function cancelDeload(deloadRecordId, reason = null) {
  return request('/api/overload/cancel-deload', {
    method: 'POST',
    body: JSON.stringify({ deload_record_id: deloadRecordId, reason }),
  });
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
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ message, session_id: sessionId }),
    signal,
  });

  if (response.status === 401) {
    handleUnauthorized();
    throw new Error('Your session has expired. Please log in again.');
  }
  if (response.status === 429) {
    throw new Error('You are sending messages too quickly. Please wait a moment.');
  }
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
