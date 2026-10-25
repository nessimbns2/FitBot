import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("fitness.db")
c = conn.cursor()

# 1. Clean previous incline-dumbbell-press sets for User 1
c.execute("DELETE FROM workout_sets WHERE exercise_id = 'incline-dumbbell-press' AND user_id = 1")
print(f"Deleted {c.rowcount} old sets for incline-dumbbell-press.")

# 2. Seed 4 weekly sessions over 21 days with clear fatigue progression:
# Weight stays at 32 kg, but reps drop and RPE increases:
# Day -21: 32kg x 10, 10, 10 (RPE 7.5, 7.5, 8.0)
# Day -14: 32kg x 10, 9, 8 (RPE 8.5, 8.5, 9.0)
# Day -7:  32kg x 9, 8, 7 (RPE 9.0, 9.0, 9.5)
# Day 0:   32kg x 8, 7, 6 (RPE 9.5, 9.5, 9.5)
now = datetime.now()
sessions_data = [
    (now - timedelta(days=21), [(32.0, 10, 7.5), (32.0, 10, 7.5), (32.0, 10, 8.0)]),
    (now - timedelta(days=14), [(32.0, 10, 8.5), (32.0, 9, 8.5), (32.0, 8, 9.0)]),
    (now - timedelta(days=7),  [(32.0, 9, 9.0),  (32.0, 8, 9.0), (32.0, 7, 9.5)]),
    (now - timedelta(days=0),  [(32.0, 8, 9.5),  (32.0, 7, 9.5), (32.0, 6, 9.5)]),
]

for sess_date, sets in sessions_data:
    for set_idx, (weight, reps, rpe) in enumerate(sets, 1):
        c.execute("""
            INSERT INTO workout_sets (user_id, exercise_id, weight_kg, reps, rpe, performed_at, set_number)
            VALUES (1, 'incline-dumbbell-press', ?, ?, ?, ?, ?)
        """, (weight, reps, rpe, sess_date.isoformat(), set_idx))

conn.commit()
print("Successfully seeded 4 sessions over 21 days for incline-dumbbell-press.")
conn.close()
