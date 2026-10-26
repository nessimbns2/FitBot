# FitBot — Compléments au rapport technique

Ce document décrit les ajouts faits pour rendre le projet complet (front-end, back-end, base de données)
et conforme aux exigences du mini-projet *IA for Software Engineering* : données personnelles, validation
des sorties, gestion des erreurs d'API.

## 1. Architecture

```
React 19 + Vite (TypeScript)                    FastAPI (Python 3.13)                      PostgreSQL 17
┌──────────────────────────┐   HTTP + JWT     ┌─────────────────────────────────┐   SQLModel  ┌──────────────┐
│ /login /register (public) │ ───────────────▶ │ /api/auth   (register, login…)  │ ──────────▶ │ users        │
│ AuthContext (jeton)       │  Authorization:  │ get_current_user (dépendance)   │  Alembic    │ user_profile │
│ RequireAuth (routes)      │  Bearer <jwt>    │ /api/user /nutrition /exercises │             │ chat_*       │
│ Today, Coach, Nutrition,  │ ◀─────────────── │ /api/overload /chat (SSE)       │             │ workout_sets │
│ Workouts, Tracker, Profil │   JSON / SSE     │ privacy.py · RAG FAISS · Gemini │             │ meal_logs …  │
└──────────────────────────┘                  └─────────────────────────────────┘             └──────────────┘
```

## 2. Authentification

| Élément | Choix | Justification |
|---|---|---|
| Hachage | `bcrypt` (coût 12, sel aléatoire) | Lent par conception, résiste au brute-force ; jamais de mot de passe en clair |
| Jeton | JWT HS256 (`pyjwt`), durée 24 h, `sub` = id utilisateur | Sans état côté serveur, simple à vérifier dans une dépendance FastAPI |
| Règles mot de passe | ≥ 8 caractères, une lettre et un chiffre, ≤ 72 octets (limite bcrypt) | Vérifiées côté front **et** côté back |
| Email | `EmailStr`, normalisé en minuscules, index unique | Pas de doublons « A@x.com » / « a@x.com » |
| Anti brute-force | `slowapi` : 10 tentatives/min sur login/register, 20 messages/min sur le chat | Limite les attaques par dictionnaire et le coût LLM |
| Énumération | Message générique « Incorrect email or password » + temps de réponse constant (hash factice) | On ne révèle pas si un email existe |
| Protection API | `dependencies=[Depends(get_current_user)]` sur tous les routeurs sauf `/api/auth` et `/api/health` | Aucune donnée accessible sans jeton valide |
| Front-end | `AuthContext` + `RequireAuth` ; tout 401 déconnecte l'utilisateur | Session expirée → retour propre à /login |
| Compte | Modifier le nom, changer le mot de passe (vérifie l'ancien), supprimer le compte (cascade) | Droit à l'effacement des données |

Endpoints : `POST /api/auth/register`, `POST /api/auth/login`, `GET|PUT|DELETE /api/auth/me`,
`POST /api/auth/change-password`.

## 3. Données personnelles et IA (exigences du sujet)

**« Jamais de données personnelles brutes envoyées au LLM »** — `app/core/privacy.py`, `redact_pii()` :
avant chaque appel externe (chat, questions nutrition, form cues), le texte est nettoyé :
emails → `[email]`, téléphones (+216…, 8 chiffres, format FR) → `[phone]`, IBAN → `[iban]`,
numéros de carte → `[number]`, URL avec identifiants → `[url]`, nom de l'utilisateur → `[name]`.
Les chiffres d'entraînement (« 100 100 95 kg », dates, kcal) sont conservés.
Le profil envoyé au modèle ne contient que des mesures (âge, poids, objectif…), jamais le nom ni l'email.
Le message original reste uniquement dans notre base PostgreSQL.

**« Sortie validée avant affichage »** — `validate_llm_output()` : réponse vide → repli, balises
`<script>/<iframe>` retirées, fuite du prompt (`SYSTEM:`/`USER:`) coupée, longueur plafonnée.
Le scan de repas (vision) exige un JSON conforme à un schéma Pydantic avec bornes
(0–10 000 kcal…) ; sinon 502 au lieu d'afficher des chiffres inventés. L'ancien code affichait de
fausses valeurs nutritionnelles quand l'IA échouait : c'est supprimé.

**« Gestion des erreurs d'appel API (timeout, quota, clé absente) »** — `LLMUnavailableError` avec
une raison typée (`missing_api_key`, `invalid_api_key`, `quota_exceeded`, `timeout`, `blocked`,
`provider_error`) produite par `classify_llm_error()`.
* Clé absente : aucun appel réseau, réponse immédiate.
* Budget de temps global `LLM_TIMEOUT_SECONDS` (30 s) partagé par les modèles de repli : l'utilisateur
  n'attend jamais N modèles × timeout. Modèles retirés (404) et lents écartés de la liste de repli.
* **Mode dégradé** : si l'IA est indisponible, le coach répond avec les extraits des PDF retrouvés par
  la recherche RAG, avec leurs sources, et un avertissement explicite. Le champ `ai_status` de l'API
  indique la cause.

**Mémoire de conversation** : les 6 derniers messages de la session (eux aussi nettoyés) sont envoyés
au modèle. Avant, chaque question était traitée sans contexte.

## 4. Prompts et modèles

* LLM : Google Gemini `gemini-3.5-flash-lite` (repli : `gemini-3.5-flash`, `gemini-flash-lite-latest`).
* Embeddings : `sentence-transformers/all-MiniLM-L6-v2` (local), index FAISS séparés `nutrition` / `exercise`.
* Prompts (dossier `backend/app/prompts/`) : `COACH_PERSONA` + gabarits par intention (nutrition,
  technique, surcharge, journal d'entraînement, général), `SAFETY_DISCLAIMER`, `MEAL_SCAN_VISION_PROMPT`
  (sortie JSON stricte), prompts somatotype et suggestion de programme.
* Principe clé : **les nombres ne viennent jamais du LLM**. Calories, macros et charges cibles sont
  calculées en Python, et le modèle se contente de les expliquer.

## 5. Tests

`cd backend && .venv\Scripts\python -m pytest` : **138 tests** (dont 39 nouveaux dans `tests/test_auth.py`) :
inscription, connexion, jetons invalides ou falsifiés, isolation entre utilisateurs, suppression en
cascade, journal de repas, programme sauvegardé, masquage des données personnelles, validation des
sorties, classification des erreurs, budget de temps, mode dégradé et limitation de débit.
Les tests utilisent SQLite en mémoire et un faux LLM : ils ne touchent ni PostgreSQL ni l'API Gemini.

## 6. Limites et pistes

* Le jeton est stocké dans `localStorage` (simple, adapté à une démo). En production, on utiliserait un
  cookie `HttpOnly` + jeton CSRF, ou un couple access/refresh token.
* Le SDK `google-generativeai` est déprécié par Google : la migration vers `google-genai` est la prochaine
  étape côté IA.
* Pas encore de réinitialisation du mot de passe par email : il faudrait un service SMTP.
