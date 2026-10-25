"""
backend/app/prompts/guidance.py
Prompt templates for somatotype and body type guidance, and the AI Somatotype Predictor.
"""

from typing import Any, Dict, List

SOMATOTYPE_EXERCISE_USER_TEMPLATE = "Summarize key training advice for an {somatotype}."

SOMATOTYPE_NUTRITION_USER_TEMPLATE = "Summarize key nutrition and macronutrient advice for an {somatotype}."

# ── AI Somatotype Prediction Prompts ──────────────────────────────────────────

SOMATOTYPE_PREDICTION_SYSTEM_PROMPT = """You are an expert sports scientist and anthropometry coach specializing in the Heath-Carter Somatotype method.
Analyze the user's answers to the somatotype diagnostic assessment.
Determine whether their primary physiological somatotype is 'ectomorph', 'mesomorph', or 'endomorph'.

Return ONLY a valid JSON object matching this schema exactly (no markdown formatting, no code blocks):
{
  "predicted_somatotype": "ectomorph" | "mesomorph" | "endomorph",
  "confidence": "high" | "medium" | "low",
  "secondary_traits": "Optional secondary classification if hybrid (e.g. Ecto-Mesomorph, Endo-Mesomorph)",
  "traits_summary": "Concise 2-sentence summary of their metabolic rate, bone structure, and physiological response to diet and resistance training.",
  "training_focus": "Key training advice tailored to this somatotype (e.g. heavy compound focus and long rest vs moderate-high volume hypertrophy).",
  "nutrition_focus": "Key nutritional strategy and macronutrient adaptation (e.g. high carb tolerance vs carb moderation with healthy fats)."
}"""

SOMATOTYPE_PREDICTION_USER_TEMPLATE = """User Anthropometric Assessment Responses:
1. Wrist & Bone Structure: {wrist_structure}
2. Natural Frame & Silhouette: {body_frame}
3. Weight Gain & Fat Storage Tendency: {weight_tendency}
4. Muscle Tone & Mass Distribution: {muscle_definition}
5. Carbohydrate & Post-Meal Energy Response: {carb_response}

Based on these validated physiological markers, determine the user's primary somatotype and return the required JSON object."""

# ── Validated Somatotype Diagnostic Questions ──────────────────────────────────

SOMATOTYPE_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "wrist_structure",
        "title": "Bone Structure & Wrist Circumference",
        "question": "When you wrap your thumb and middle finger around your opposite wrist:",
        "options": [
            {
                "value": "fingers_overlap",
                "label": "Fingers overlap easily",
                "detail": "Small, slender bone structure with narrow wrists and ankles",
                "archetype": "ectomorph",
            },
            {
                "value": "fingers_touch",
                "label": "Fingers just touch each other",
                "detail": "Medium, proportionate bone structure and joint size",
                "archetype": "mesomorph",
            },
            {
                "value": "fingers_do_not_touch",
                "label": "Fingers do not touch at all",
                "detail": "Large, thick bone structure with broad, heavy joints",
                "archetype": "endomorph",
            },
        ],
    },
    {
        "id": "body_frame",
        "title": "Natural Body Frame & Silhouette",
        "question": "What best describes your natural shoulder-to-waist shape and silhouette?",
        "options": [
            {
                "value": "narrow_linear",
                "label": "Narrow & Linear (Pencil build)",
                "detail": "Shoulders and hips are narrow and roughly the same width",
                "archetype": "ectomorph",
            },
            {
                "value": "broad_athletic",
                "label": "Athletic V-Taper",
                "detail": "Naturally broad shoulders tapering down to a narrower waist",
                "archetype": "mesomorph",
            },
            {
                "value": "broad_thick",
                "label": "Blocky or Oval Frame",
                "detail": "Broad shoulders with thicker waist and wider hips",
                "archetype": "endomorph",
            },
        ],
    },
    {
        "id": "weight_tendency",
        "title": "Weight Gain & Metabolic Tendency",
        "question": "How does your body typically respond when you try to change your weight?",
        "options": [
            {
                "value": "hardgainer",
                "label": "Hardgainer (Fast Metabolism)",
                "detail": "Struggle to gain weight or muscle even when eating in surplus",
                "archetype": "ectomorph",
            },
            {
                "value": "steady_gains",
                "label": "Adaptable & Steady",
                "detail": "Gain lean muscle readily with training and lose fat with moderate deficit",
                "archetype": "mesomorph",
            },
            {
                "value": "easy_fat_gain",
                "label": "Easy Weight Gain (Slower Metabolism)",
                "detail": "Gain weight and muscle easily, but hold onto body fat persistently",
                "archetype": "endomorph",
            },
        ],
    },
    {
        "id": "muscle_definition",
        "title": "Natural Muscle Tone & Definition",
        "question": "Without intensive weight training, what is your default muscle appearance?",
        "options": [
            {
                "value": "lean_low_muscle",
                "label": "Lean, Long & Slender",
                "detail": "Long limbs with stringy, flatter muscle bellies and low natural body fat",
                "archetype": "ectomorph",
            },
            {
                "value": "dense_defined",
                "label": "Dense, Firm & Athletic",
                "detail": "Naturally visible muscular contours and firm muscle tone",
                "archetype": "mesomorph",
            },
            {
                "value": "dense_softer",
                "label": "Thick & Solid with Softer Layer",
                "detail": "Dense strength foundation underneath a softer, thicker body fat layer",
                "archetype": "endomorph",
            },
        ],
    },
    {
        "id": "carb_response",
        "title": "Carbohydrate & Energy Response",
        "question": "How do you feel and react after eating a large, carbohydrate-rich meal (e.g. pasta, rice)?",
        "options": [
            {
                "value": "high_energy",
                "label": "Energetic & Thermogenic",
                "detail": "Feel warm and energized; rarely store extra carbs as body fat",
                "archetype": "ectomorph",
            },
            {
                "value": "fuel_workout",
                "label": "Well-Fueled for Training",
                "detail": "Utilize carbs efficiently for muscle fullness and gym performance",
                "archetype": "mesomorph",
            },
            {
                "value": "sluggish_bloated",
                "label": "Sluggish, Bloated or Lethargic",
                "detail": "Experience a quick blood sugar dip, water retention, and prone to fat storage",
                "archetype": "endomorph",
            },
        ],
    },
]

# ── AI Athlete Blueprint & Profile Audit Prompts ─────────────────────────────

ATHLETE_BLUEPRINT_SYSTEM_PROMPT = """You are a friendly, encouraging fitness coach and sports scientist.
You are generating a personalized Athlete AI Blueprint & Body Audit.

CRITICAL INSTRUCTION - USE SIMPLE, EVERYDAY LANGUAGE:
- Avoid heavy academic jargon, medical terms, or overly complex biomechanical terms.
- Write in clear, motivating, and easy-to-understand conversational language that anyone can follow.
- Use plain terms: say "Weekly workout sets" instead of "volume landmarks", "Things to watch out for" instead of "blindspots and risks", "Minimum sets to grow" instead of "MEV", and "Max sets before tiring out" instead of "MRV".

Return ONLY a valid JSON object matching this schema exactly (no markdown formatting, no code blocks):
{
  "athlete_archetype": "Simple descriptive title (e.g., 'Athletic Build — Muscle Growth Plan' or 'Lean Hardgainer — Mass Building Plan')",
  "executive_summary": "2-3 friendly, encouraging sentences explaining their body type, daily fuel, and the clearest path to their goal.",
  "physiological_strengths": [
    "Simple strength 1 (e.g., 'Great metabolism that efficiently turns food into workout energy')",
    "Simple strength 2",
    "Simple strength 3"
  ],
  "blindspots_and_risks": [
    "Simple thing to watch out for 1 (e.g., 'Doing too many sets too fast can tire out your joints')",
    "Simple thing to watch out for 2 (e.g., 'Sleeping less than 7 hours will slow down your muscle repair')"
  ],
  "volume_landmarks": {
    "mev_sets_per_week": "e.g., 10-12 sets / muscle group (minimum to see progress)",
    "mrv_sets_per_week": "e.g., 18-20 sets / muscle group (max before overtraining)",
    "recommended_frequency": "e.g., 2 to 3 times a week per muscle",
    "recovery_capacity": "Fast" | "Normal" | "Needs Extra Rest"
  },
  "timeline_projection": {
    "rate_of_change": "e.g., +0.5 kg muscle per month (or -0.5 kg fat per week)",
    "milestone_12_weeks": "Simple description of what they can expect to achieve in 3 months (12 weeks)",
    "milestone_24_weeks": "Simple description of what their body will look and feel like in 6 months (24 weeks)"
  },
  "key_coaching_directives": [
    "Action step 1 (clear and practical)",
    "Action step 2",
    "Action step 3"
  ]
}"""

ATHLETE_BLUEPRINT_USER_TEMPLATE = """ATHLETE BIOMETRICS & AUDIT PROFILE:
- Age: {age} | Sex: {sex}
- Height: {height_cm} cm | Weight: {weight_kg} kg | BMI: {bmi:.1f}
- Body Fat: {body_fat_pct}
- Somatotype: {somatotype}
- Experience Level: {experience_level}
- Primary Goal: {goal}
- Activity Level: {activity_level}
- Daily Energy Target: {target_kcal} kcal (BMR: {bmr} kcal, TDEE: {tdee} kcal)
- Macro Distribution: {protein_g}g Protein, {carbs_g}g Carbs, {fat_g}g Fat

SCIENTIFIC LITERATURE CONTEXT:
{context}

Generate the comprehensive Athlete AI Blueprint in the specified JSON format."""
