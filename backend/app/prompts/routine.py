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
    "You are an elite evidence-based fitness coach. Provide a concise 1-2 sentence "
    "rationale for adding an exercise to a routine."
)

# ==============================================================================
# DEVELOPER: Montassar
# MODULE: Routine Module
# FUNCTIONALITY: User prompt template formatting current muscle set counts vs target,
#                asking why the suggested exercise fits the user's specific goal.
# ==============================================================================
ROUTINE_SUGGESTION_USER_TEMPLATE = (
    "The user's routine currently has only {current_sets} weekly sets for {target_muscle} "
    "(target is {target_sets}-20 sets). "
    "Why is adding {exercise_name} (3 sets of {rep_range}) to {target_day_name} the ideal "
    "addition for their {goal} goal?"
)
