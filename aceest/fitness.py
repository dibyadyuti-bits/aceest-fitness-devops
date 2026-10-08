"""Core fitness logic for ACEest Fitness & Gym.

Everything in this module is pure Python with no Flask or database
dependency, so it can be unit tested in isolation. The rules here are
ported from the legacy Tkinter prototypes (v1.0 - v3.2.4) kept in
the ``legacy/`` folder.
"""

from datetime import date
import random

PROGRAMS = {
    "FL": {
        "name": "Fat Loss",
        "calorie_factor": 22,
        "focus": "Conditioning",
        "workout": [
            "Mon: Back Squat 5x5 + Core",
            "Tue: EMOM 20min Assault Bike",
            "Wed: Bench Press + 21-15-9",
            "Thu: Deadlift + Box Jumps",
            "Fri: Zone 2 Cardio 30min",
        ],
        "diet": [
            "Breakfast: Egg Whites + Oats",
            "Lunch: Grilled Chicken + Brown Rice",
            "Dinner: Fish Curry + Millet Roti",
            "Target: ~2000 kcal",
        ],
    },
    "MG": {
        "name": "Muscle Gain",
        "calorie_factor": 35,
        "focus": "Hypertrophy",
        "workout": [
            "Mon: Squat 5x5",
            "Tue: Bench 5x5",
            "Wed: Deadlift 4x6",
            "Thu: Front Squat 4x8",
            "Fri: Incline Press 4x10",
            "Sat: Barbell Rows 4x10",
        ],
        "diet": [
            "Breakfast: Eggs + Peanut Butter Oats",
            "Lunch: Chicken Biryani",
            "Dinner: Mutton Curry + Rice",
            "Target: ~3200 kcal",
        ],
    },
    "BG": {
        "name": "Beginner",
        "calorie_factor": 26,
        "focus": "Full Body",
        "workout": [
            "Full Body Circuit: Air Squats, Ring Rows, Push-ups",
            "Focus: Technique & Consistency",
        ],
        "diet": [
            "Balanced Tamil Meals: Idli / Dosa / Rice + Dal",
            "Protein Target: 120g/day",
        ],
    },
}

EXERCISE_POOL = {
    "Strength": ["Squat", "Deadlift", "Bench Press", "Overhead Press",
                 "Pull-Up", "Barbell Row"],
    "Hypertrophy": ["Leg Press", "Incline Dumbbell Press", "Lat Pulldown",
                    "Lateral Raise", "Bicep Curl", "Tricep Extension"],
    "Conditioning": ["Running", "Cycling", "Rowing", "Burpees",
                     "Jump Rope", "Kettlebell Swings"],
    "Full Body": ["Push-Up", "Pull-Up", "Lunge", "Plank",
                  "Dumbbell Row", "Dumbbell Press"],
}

EXPERIENCE_LEVELS = {
    "beginner": {"sets": (2, 3), "reps": (8, 12), "days": 3},
    "intermediate": {"sets": (3, 4), "reps": (8, 15), "days": 4},
    "advanced": {"sets": (4, 5), "reps": (6, 15), "days": 5},
}

WEEK_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday"]

WORKOUT_TYPES = ["Strength", "Hypertrophy", "Cardio", "Mobility"]


class ValidationError(ValueError):
    """Raised when user input breaks a business rule."""


def get_program(code):
    """Return the program for a code such as 'FL', or raise ValidationError."""
    key = str(code).upper()
    if key not in PROGRAMS:
        raise ValidationError(
            f"Unknown program '{code}'. Valid codes: {', '.join(PROGRAMS)}"
        )
    return PROGRAMS[key]


def calculate_calories(weight_kg, program_code):
    """Estimated daily calories = body weight x the program's factor."""
    weight = _positive_number(weight_kg, "weight")
    return int(weight * get_program(program_code)["calorie_factor"])


def calculate_bmi(weight_kg, height_cm):
    """Return BMI (1 decimal), its WHO category and a short risk note."""
    weight = _positive_number(weight_kg, "weight")
    height = _positive_number(height_cm, "height")
    height_m = height / 100.0
    bmi = round(weight / (height_m * height_m), 1)

    if bmi < 18.5:
        category = "Underweight"
        risk = "Potential nutrient deficiency, low energy."
    elif bmi < 25:
        category = "Normal"
        risk = "Low risk if active and strong."
    elif bmi < 30:
        category = "Overweight"
        risk = "Moderate risk; focus on adherence and progressive activity."
    else:
        category = "Obese"
        risk = "Higher risk; prioritise fat loss, consistency and supervision."

    return {"bmi": bmi, "category": category, "risk": risk}


def validate_adherence(value):
    """Adherence must be a whole-number percentage between 0 and 100."""
    try:
        adherence = int(value)
    except (TypeError, ValueError):
        raise ValidationError("adherence must be an integer")
    if not 0 <= adherence <= 100:
        raise ValidationError("adherence must be between 0 and 100")
    return adherence


def generate_program(program_code, experience, seed=None):
    """Build a weekly plan from the exercise pool.

    The focus comes from the client's program and the volume from their
    experience level. Passing ``seed`` makes the output repeatable, which
    is what lets the tests check it.
    """
    focus = get_program(program_code)["focus"]
    level = str(experience).lower()
    if level not in EXPERIENCE_LEVELS:
        raise ValidationError(
            "experience must be beginner, intermediate or advanced"
        )
    rules = EXPERIENCE_LEVELS[level]
    rng = random.Random(seed)
    per_day = 3 if rules["days"] < 4 else 4

    plan = []
    for day in WEEK_DAYS[:rules["days"]]:
        for exercise in rng.sample(EXERCISE_POOL[focus], k=per_day):
            plan.append({
                "day": day,
                "exercise": exercise,
                "sets": rng.randint(*rules["sets"]),
                "reps": rng.randint(*rules["reps"]),
            })
    return plan


def membership_status(end_date, today=None):
    """Return 'Active', 'Expired' or 'None' for an ISO date string."""
    if not end_date:
        return "None"
    today = today or date.today()
    end = parse_date(end_date, "membership_end")
    return "Active" if end >= today else "Expired"


def parse_date(value, field):
    """Parse a YYYY-MM-DD string or raise ValidationError."""
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValidationError(f"{field} must be a date in YYYY-MM-DD format")


def _positive_number(value, field):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a number")
    if number <= 0:
        raise ValidationError(f"{field} must be greater than zero")
    return number
