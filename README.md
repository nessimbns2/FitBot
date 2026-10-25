# FitBot 🏋️ — Exact-Math & RAG Fitness Coach

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-6+-646CFF.svg?logo=vite&logoColor=white)](https://vitejs.dev)
[![SQLModel](https://img.shields.io/badge/SQLModel-0.0.22-blue.svg)](https://sqlmodel.tiangolo.com)
[![FAISS](https://img.shields.io/badge/FAISS-VectorStore-orange.svg)](https://github.com/facebookresearch/faiss)
[![Test Coverage](https://img.shields.io/badge/Coverage-93%25-brightgreen.svg)]()

**FitBot** is an evidence-based personal fitness and nutrition coach application combining **deterministic mathematical calculations** (BMR, TDEE, macros, double progression overload) with **category-isolated RAG retrieval** (FAISS + SentenceTransformers) and a modern dark-mode React frontend.

---

## 🏛️ Architecture & Core Principles

```
  ┌─────────────────────────────────────────────────────────────┐
  │                    React 19 + Vite Frontend                 │
  │   Coach Chat  │  Macros & Meals  │  Workouts  │  Tracker    │
  └──────────────────────────────┬──────────────────────────────┘
                                 │ HTTP / SSE Stream
  ┌──────────────────────────────▼──────────────────────────────┐
  │                      FastAPI Backend                        │
  ├─────────────────────────────────────────────────────────────┤
  │  [Router Agent] Intent Classifier & Exercise Entity Matcher │
  │                                                             │
  │  ┌────────────────────────┐     ┌────────────────────────┐  │
  │  │ Deterministic Math     │     │ Category-Isolated RAG  │  │
  │  │ - Mifflin-St Jeor BMR  │     │ - nutrition.faiss      │  │
  │  │ - Katch-McArdle BMR    │     │ - exercise.faiss       │  │
  │  │ - Caloric Floors       │     │ - SentenceTransformers │  │
  │  │ - Double Progression   │     │ - Isolated Retrieval   │  │
  │  │ - Routine Generator    │     │ - LLM Context Prompt   │  │
  │  └────────────────────────┘     └────────────────────────┘  │
  │                                                             │
  │  [SQLModel ORM] SQLite / PostgreSQL Database Engine         │
  └─────────────────────────────────────────────────────────────┘
```

1. **Numbers Never Originate from LLMs**:
   - All calories, macronutrient splits, 1-Rep Maxes, and progression targets are computed by pure Python functions. The LLM only quotes and explains them.
2. **Category Isolation**:
   - Queries tagged with `nutrition` retrieve chunks **only** from `nutrition.faiss`.
   - Queries tagged with `exercise` retrieve chunks **only** from `exercise.faiss`.
3. **Safety Guardrails**:
   - Physiological caloric floors (1200 kcal for females, 1500 kcal for males).
   - Automated refusal of anabolic steroids, SARMs, and unprescribed PEDs.
   - Medical disclaimer for injury, acute pain, or diagnostic inquiries.
   - SlowAPI rate limiting (60 req/min general, 10 req/min chat streams).

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- Python 3.11+
- Node.js 20+ and npm

### 2. Backend Setup
```bash
cd backend

# Install dependencies
pip install -r requirements_v2.txt
pip install slowapi

# Run database migrations
alembic upgrade head

# Ingest PDF manuals into vectorstore (one-time or rebuild)
python scripts/ingest_docs.py

# Launch FastAPI development server
uvicorn main_v2:app --reload --port 8000
```
Backend API will be accessible at: `http://localhost:8000` (Docs at `http://localhost:8000/docs`).

### 3. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install --legacy-peer-deps

# Launch Vite dev server
npm run dev
```
Frontend Web App will be running at: `http://localhost:5173`.

---

## 🐳 Docker Compose Deployment

Run the entire stack (PostgreSQL, Backend API, and Nginx-served Frontend) with a single command:

```bash
docker-compose up --build -d
```

- **Frontend**: `http://localhost` (or `http://localhost:5173`)
- **Backend API**: `http://localhost:8000`
- **PostgreSQL Database**: `localhost:5432`

---

## 🧪 Testing & Evaluation

### Run Pytest Suite with Coverage
```bash
cd backend
python -m pytest --cov=app tests/
```
Output: **87+ tests passing**, coverage > **92%** on all calculation, service, and routing layers.

### Run RAG Precision Benchmark
```bash
cd backend
python scripts/rag_eval.py
```
Evaluates 20 real fitness and nutrition questions against the indexed PDF manuals:
- **Category Isolation Rate**: 100.0%
- **Semantic Keyword Hit Rate**: 90.0%
- **MRR (Mean Reciprocal Rank)**: 0.817

---

## 📡 API Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Healthcheck liveness probe |
| `GET` | `/api/user/profile` | Retrieve default profile with biometrics & goals |
| `PUT` | `/api/user/profile` | Update user profile (height, weight, body fat, etc.) |
| `GET` | `/api/user/sessions` | List active chat sessions |
| `POST` | `/api/nutrition/calculate` | Compute exact BMR, TDEE, calories, and macros |
| `POST` | `/api/nutrition/plan` | Generate meal distribution with optional RAG timing |
| `POST` | `/api/nutrition/ask` | Retrieve evidence-based nutrition answers |
| `GET` | `/api/exercises/catalog` | Filter and search 56+ seed exercises |
| `POST` | `/api/exercises/generate-routine` | Deterministic routine generator (PPL, UL, Full Body) |
| `POST` | `/api/exercises/form-cue` | Form cues, setup steps, and pain caution notices |
| `POST` | `/api/overload/sets` | Log completed exercise workout set |
| `GET` | `/api/overload/recommendation/{id}` | Compute double/linear progression recommendation |
| `GET` | `/api/overload/volume/summary` | Weekly volume status per muscle group |
| `POST` | `/api/chat` | Non-streaming RAG chat with action extraction |
| `POST` | `/api/chat/stream` | Server-Sent Events (SSE) token streaming chat |
| `POST` | `/api/overload/diagnosis` | AI Fatigue & Plateau diagnosis with evidence and RAG |
| `POST` | `/api/overload/apply-deload` | Server-verified deload activation with bounded strategy |
| `POST` | `/api/overload/cancel-deload` | Cancel an active deload record |

---

## 🧠 Fatigue & Plateau Diagnostician: Heuristics & Known Limits

- **Minimum History Window**: Requires at least 3 qualifying sessions over a minimum span of 14 days (within a 28-day window) to compute OLS regression slopes; fewer sessions or large gaps classify as `insufficient_data`.
- **Deterministic Root Cause Classification**: Mathematical heuristics classify plateaus into `fatigue_pattern` (rising RPE slope $\ge 0.5$/sess and rep dropoff $\ge 15\%$), `possible_under_recovery` (rising RPE without dropoff), `insufficient_stimulus` (falling RPE $\le -0.5$/sess), or `progressing`.
- **Noisy Data & Gray-Zone Demotion**: When residual variance across sessions is erratic (`noise_ratio >= 0.12`) or RPE coverage is sparse ($<50\%$), the diagnosis is demoted to `undetermined_cause` with a `hold` strategy to prevent erroneous deloads.
- **Gray-Zone Formulaic Design**: Gray-zone explanations are formulaic by design; Python decides, the LLM justifies and explains.
- **Reference Document Notice**: `Deload_and_Fatigue_Management_in_Strength_Training.pdf` is an AI-drafted summary of common guidance, not a published source.
- **Manual Deload Cutoff & Alternating Program Limit**: Load drops $\ge 15\%$ automatically detect manual deloads; however, volume-only deloads (same load, fewer sets) and daily undulating / heavy-light alternating splits are not automatically detected and require manual marking.
- **Pure Math Ownership & Prose Validation**: Every target number (kg, sets, reps, RPE ceiling, resume load) is computed by Python; LLMs generate only hedged prose, strictly validated against digits/number words with automatic fallback to deterministic templates.

---

## 📄 License
MIT License.
