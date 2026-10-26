"""
backend/app/prompts/__init__.py
Centralized repository for all system and user prompt templates across FitBot.

================================================================================
FITBOT DEVELOPMENT TEAM — PROMPT OWNERSHIP DIRECTORY
================================================================================
1. Nessim (RAG Core & Athlete Profile Module)
   - COACH_PERSONA                        : Base evidence-based coaching persona
   - SAFETY_DISCLAIMER                    : Mandatory legal & medical advice disclaimer
   - EXERCISE_TECHNIQUE_PROMPT_TEMPLATE   : Biomechanics, form cues & injury safeguards
   - WORKOUT_LOGGING_PROMPT_TEMPLATE      : Logging confirmation & consistency feedback
   - GENERAL_PROMPT_TEMPLATE              : General fitness inquiries grounded in guides
   - INTENT_PROMPT_MAP                    : Intent classification dispatch map
   - SOMATOTYPE_EXERCISE_USER_TEMPLATE    : Somatotype training summary prompt
   - SOMATOTYPE_NUTRITION_USER_TEMPLATE   : Somatotype nutrition summary prompt
   - SOMATOTYPE_PREDICTION_SYSTEM_PROMPT  : Heath-Carter anthropometric classification
   - SOMATOTYPE_PREDICTION_USER_TEMPLATE  : 5-point body assessment user input format
   - SOMATOTYPE_QUESTIONS                 : Validated diagnostic assessment question bank
   - ATHLETE_BLUEPRINT_SYSTEM_PROMPT     : Comprehensive AI Athlete Blueprint generator
   - ATHLETE_BLUEPRINT_USER_TEMPLATE     : Biometric profile + context prompt for blueprint

2. Montassar (Routine Module)
   - ROUTINE_SUGGESTION_SYSTEM_PROMPT     : Volume-gap exercise recommendation system prompt
   - ROUTINE_SUGGESTION_USER_TEMPLATE     : Exercise placement rationale template

3. Hamza (Nutrition Module)
   - NUTRITION_PROMPT_TEMPLATE            : Dietary coaching & exact macro guidance
   - MEAL_SCAN_VISION_PROMPT              : Computer vision food plate calorie/macro scanning

4. Mahdi (Progressive Overload Module)
   - OVERLOAD_ADVICE_PROMPT_TEMPLATE      : Progressive overload, double progression & deload advice
================================================================================
"""

# ── 1. RAG Core & Coaching Prompts (Nessim / Hamza / Mahdi) ───────────────────
from app.prompts.coach import (
    COACH_PERSONA,                         # Nessim (RAG Core)
    SAFETY_DISCLAIMER,                     # Nessim (RAG Core)
    NUTRITION_PROMPT_TEMPLATE,             # Hamza (Nutrition Module)
    EXERCISE_TECHNIQUE_PROMPT_TEMPLATE,    # Nessim (RAG Core)
    OVERLOAD_ADVICE_PROMPT_TEMPLATE,       # Mahdi (Progressive Overload Module)
    WORKOUT_LOGGING_PROMPT_TEMPLATE,       # Nessim (RAG Core)
    GENERAL_PROMPT_TEMPLATE,               # Nessim (RAG Core)
    INTENT_PROMPT_MAP,                     # Nessim (RAG Core)
)

# ── 2. Nutrition Computer Vision Prompts (Hamza) ──────────────────────────────
from app.prompts.vision import MEAL_SCAN_VISION_PROMPT  # Hamza (Nutrition Module)

# ── 3. Routine Assistant Prompts (Montassar) ──────────────────────────────────
from app.prompts.routine import (
    ROUTINE_SUGGESTION_SYSTEM_PROMPT,      # Montassar (Routine Module)
    ROUTINE_SUGGESTION_USER_TEMPLATE,      # Montassar (Routine Module)
)

# ── 4. Athlete Profile & Somatotype Prompts (Nessim) ──────────────────────────
from app.prompts.guidance import (
    SOMATOTYPE_EXERCISE_USER_TEMPLATE,     # Nessim (Athlete Profile Module)
    SOMATOTYPE_NUTRITION_USER_TEMPLATE,    # Nessim (Athlete Profile Module)
    SOMATOTYPE_PREDICTION_SYSTEM_PROMPT,   # Nessim (Athlete Profile Module)
    SOMATOTYPE_PREDICTION_USER_TEMPLATE,   # Nessim (Athlete Profile Module)
    SOMATOTYPE_QUESTIONS,                  # Nessim (Athlete Profile Module)
    ATHLETE_BLUEPRINT_SYSTEM_PROMPT,       # Nessim (Athlete Profile Module)
    ATHLETE_BLUEPRINT_USER_TEMPLATE,       # Nessim (Athlete Profile Module)
)

__all__ = [
    # Nessim (RAG Core)
    "COACH_PERSONA",
    "SAFETY_DISCLAIMER",
    "EXERCISE_TECHNIQUE_PROMPT_TEMPLATE",
    "WORKOUT_LOGGING_PROMPT_TEMPLATE",
    "GENERAL_PROMPT_TEMPLATE",
    "INTENT_PROMPT_MAP",
    # Nessim (Athlete Profile Module)
    "SOMATOTYPE_EXERCISE_USER_TEMPLATE",
    "SOMATOTYPE_NUTRITION_USER_TEMPLATE",
    "SOMATOTYPE_PREDICTION_SYSTEM_PROMPT",
    "SOMATOTYPE_PREDICTION_USER_TEMPLATE",
    "SOMATOTYPE_QUESTIONS",
    "ATHLETE_BLUEPRINT_SYSTEM_PROMPT",
    "ATHLETE_BLUEPRINT_USER_TEMPLATE",
    # Montassar (Routine Module)
    "ROUTINE_SUGGESTION_SYSTEM_PROMPT",
    "ROUTINE_SUGGESTION_USER_TEMPLATE",
    # Hamza (Nutrition Module)
    "NUTRITION_PROMPT_TEMPLATE",
    "MEAL_SCAN_VISION_PROMPT",
    # Mahdi (Progressive Overload Module)
    "OVERLOAD_ADVICE_PROMPT_TEMPLATE",
]
