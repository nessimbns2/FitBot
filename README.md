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
   - SlowAPI rate limiting (60 req/min general, 20 req/min chat, 10 req/min login/register).
4. **Accounts & Privacy**:
   - Email/password accounts (bcrypt + JWT); all data lives in PostgreSQL, scoped per user, deleted in cascade with the account.
   - Personal identifiers (emails, phones, the user's name…) are masked before any LLM call; LLM output is validated before display.
   - Typed AI errors (missing key, quota, timeout) with a degraded mode that answers from the retrieved PDF excerpts.
   - Details: [report/ajouts_auth_postgres_ia.md](report/ajouts_auth_postgres_ia.md).

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- Python 3.11+
- Node.js 20+ and npm
- PostgreSQL 16+ (pgAdmin optional)
- Git LFS (`git lfs pull`) — the PDF manuals are stored with LFS; a GitHub ZIP download only contains pointer files

### 2. Database (PostgreSQL)
Create the `fitbot` role and the `fitbot_db` database once — see [database/README.md](database/README.md).

### 3. Backend Setup
```bash
cd backend

# Isolated environment + dependencies
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements_v2.txt   # Linux/macOS: .venv/bin/python

# Configuration: copy and fill DATABASE_URL, LLM_API_KEY, JWT_SECRET_KEY
cp .env.example .env

# Create / upgrade the tables (also done automatically at API startup)
.venv/Scripts/python -m alembic upgrade head

# Build the category FAISS indexes from the PDF manuals (one-time or rebuild)
.venv/Scripts/python -m app.modules.rag_core.ingest --rebuild

# Optional: demo account with 4 weeks of data (credentials in scripts/seed_demo.py)
.venv/Scripts/python scripts/seed_demo.py

# Launch FastAPI development server
.venv/Scripts/python -m uvicorn main_v2:app --reload --port 8000
```
Backend API will be accessible at: `http://localhost:8000` (Docs at `http://localhost:8000/docs`).

### 4. Frontend Setup
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

All endpoints except `/api/auth/register`, `/api/auth/login` and `/api/health*` require
`Authorization: Bearer <access_token>`; every query is scoped to the authenticated user.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Healthcheck liveness probe |
| `GET` | `/api/health/ready` | Readiness: database, LLM key configured, vector indexes |
| `POST` | `/api/auth/register` | Create an account (bcrypt) and return a JWT |
| `POST` | `/api/auth/login` | Email + password → JWT (rate limited) |
| `GET` / `PUT` / `DELETE` | `/api/auth/me` | Current account / rename / delete account and all its data |
| `POST` | `/api/auth/change-password` | Change password (checks the current one) |
| `GET` / `POST` / `DELETE` | `/api/nutrition/meals` | Meal diary (stored in PostgreSQL) |
| `GET` / `PUT` / `DELETE` | `/api/exercises/routine` | Saved training routine (stored in PostgreSQL) |
| `GET` | `/api/user/profile` | Retrieve the user's profile with biometrics & goals |
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
