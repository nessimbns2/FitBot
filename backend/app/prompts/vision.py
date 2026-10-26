"""
backend/app/prompts/vision.py
Multimodal prompt templates for AI Vision analysis (e.g. food plate macro logging).

Team Member: Hamza
Module: Nutrition Module
Functionality: Computer vision plate scanning, portion estimation, and macronutrient decomposition.
"""

# ==============================================================================
# DEVELOPER: Hamza
# MODULE: Nutrition Module
# FUNCTIONALITY: Multimodal prompt for Gemini Vision to analyze food plate photos,
#                identify meal components, estimate portion weights, and return
#                structured nutritional data (calories, protein, carbs, fat).
# ==============================================================================
MEAL_SCAN_VISION_PROMPT = """You are an elite sports nutritionist and computer vision food analyst.
Analyze this meal image{meal_slot_context}.
Identify each distinct food item on the plate, estimate realistic portion sizes (in grams or standard units), and calculate calories and macronutrients (protein, carbohydrates, dietary fat).

Return ONLY a valid JSON object matching this schema exactly (no markdown formatting, no code blocks):
{{
  "meal_name": "Short descriptive meal title (e.g., Grilled Chicken Breast with Brown Rice & Broccoli)",
  "confidence": "high" | "medium" | "low",
  "total_calories": 550,
  "protein_g": 48.0,
  "carbs_g": 52.0,
  "fat_g": 12.0,
  "food_items": [
    {{
      "name": "Grilled Chicken Breast",
      "portion_est": "200g (cooked)",
      "calories": 330,
      "protein_g": 42.0,
      "carbs_g": 0.0,
      "fat_g": 7.0
    }},
    {{
      "name": "Steamed Brown Rice",
      "portion_est": "1 cup (150g)",
      "calories": 180,
      "protein_g": 4.0,
      "carbs_g": 38.0,
      "fat_g": 1.5
    }},
    {{
      "name": "Steamed Broccoli Florets",
      "portion_est": "100g",
      "calories": 40,
      "protein_g": 2.0,
      "carbs_g": 7.0,
      "fat_g": 0.5
    }}
  ],
  "coaching_tip": "One concise evidence-based tip on how this meal aligns with fitness/recovery goals."
}}"""
