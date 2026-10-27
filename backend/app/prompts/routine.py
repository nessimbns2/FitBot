"""
backend/app/prompts/routine.py
Prompt templates for the AI Routine Assistant and exercise suggestion rationale.

Team Member: Montassar
Module: Routine Module
Functionality: Recommending optimal exercises to fill weekly muscle volume gaps in user routines.
"""

# ==============================================================================
# DEVELOPER: Montassar
# MODULE: Routine Module
# FUNCTIONALITY: System prompt instructing the AI to provide concise exercise
#                addition rationale based on training volume needs.
# ==============================================================================
ROUTINE_SUGGESTION_SYSTEM_PROMPT = (
    "Explain the supplied computed workout suggestion in one or two concise English sentences. "
    "Do not change exercises, sets, repetition ranges or targets. Do not claim the suggestion is optimal, "
    "medically suitable or guaranteed to improve results. Give a brief practical note without inventing sources."
)

# ==============================================================================
# DEVELOPER: Montassar
# MODULE: Routine Module
# FUNCTIONALITY: User prompt template formatting current muscle set counts vs target,
#                asking why the suggested exercise fits the user's specific goal.
# ==============================================================================
ROUTINE_SUGGESTION_USER_TEMPLATE = (
    "The user's routine currently has only {current_sets} weekly sets for {target_muscle} "
    "(configured range is {target_sets}-{maximum_sets} sets). "
    "Explain adding {exercise_name} ({sets} sets of {rep_range}) to {target_day_name} "
    "for the {goal} goal using only these facts."
)
