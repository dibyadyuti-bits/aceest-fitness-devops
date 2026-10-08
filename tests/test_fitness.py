"""Unit tests for the pure business logic in aceest/fitness.py."""

from datetime import date

import pytest

from aceest import fitness
from aceest.fitness import ValidationError


# ---------- programs ----------

def test_three_programs_defined():
    assert set(fitness.PROGRAMS) == {"FL", "MG", "BG"}


@pytest.mark.parametrize("code", ["FL", "fl", "Mg", "bg"])
def test_get_program_is_case_insensitive(code):
    assert fitness.get_program(code) is fitness.PROGRAMS[code.upper()]


def test_get_program_rejects_unknown_code():
    with pytest.raises(ValidationError, match="Unknown program"):
        fitness.get_program("XX")


def test_every_program_has_workout_diet_and_focus():
    for program in fitness.PROGRAMS.values():
        assert program["workout"] and program["diet"]
        assert program["focus"] in fitness.EXERCISE_POOL


# ---------- calories ----------

@pytest.mark.parametrize("code, expected", [("FL", 1540), ("MG", 2450), ("BG", 1820)])
def test_calories_use_program_factor(code, expected):
    assert fitness.calculate_calories(70, code) == expected


def test_calories_truncate_to_int():
    assert fitness.calculate_calories(70.5, "FL") == 1551  # 1551.0


@pytest.mark.parametrize("weight", [0, -5, "abc", None])
def test_calories_reject_bad_weight(weight):
    with pytest.raises(ValidationError):
        fitness.calculate_calories(weight, "FL")


# ---------- BMI ----------

@pytest.mark.parametrize("weight, height, category", [
    (50, 180, "Underweight"),
    (70, 175, "Normal"),
    (85, 175, "Overweight"),
    (110, 175, "Obese"),
])
def test_bmi_categories(weight, height, category):
    assert fitness.calculate_bmi(weight, height)["category"] == category


def test_bmi_value_is_rounded():
    assert fitness.calculate_bmi(70, 175)["bmi"] == 22.9


def test_bmi_boundary_25_is_overweight():
    # 25.0 exactly sits in the Overweight band (bmi < 25 is Normal)
    assert fitness.calculate_bmi(62.5, 158.1139)["category"] == "Overweight"


def test_bmi_rejects_zero_height():
    with pytest.raises(ValidationError, match="height"):
        fitness.calculate_bmi(70, 0)


# ---------- adherence ----------

@pytest.mark.parametrize("value", [0, 50, 100, "75"])
def test_valid_adherence(value):
    assert fitness.validate_adherence(value) == int(value)


@pytest.mark.parametrize("value", [-1, 101, "high", None])
def test_invalid_adherence(value):
    with pytest.raises(ValidationError):
        fitness.validate_adherence(value)


# ---------- program generator ----------

@pytest.mark.parametrize("level, days, per_day", [
    ("beginner", 3, 3), ("intermediate", 4, 4), ("advanced", 5, 4),
])
def test_generator_volume_matches_experience(level, days, per_day):
    plan = fitness.generate_program("BG", level, seed=1)
    assert len({item["day"] for item in plan}) == days
    assert len(plan) == days * per_day


def test_generator_uses_program_focus():
    plan = fitness.generate_program("FL", "beginner", seed=7)
    assert all(i["exercise"] in fitness.EXERCISE_POOL["Conditioning"] for i in plan)


def test_generator_sets_and_reps_in_range():
    rules = fitness.EXPERIENCE_LEVELS["advanced"]
    for item in fitness.generate_program("MG", "advanced", seed=3):
        assert rules["sets"][0] <= item["sets"] <= rules["sets"][1]
        assert rules["reps"][0] <= item["reps"] <= rules["reps"][1]


def test_generator_no_duplicate_exercise_in_a_day():
    plan = fitness.generate_program("MG", "intermediate", seed=5)
    for day in {i["day"] for i in plan}:
        names = [i["exercise"] for i in plan if i["day"] == day]
        assert len(names) == len(set(names))


def test_generator_is_repeatable_with_seed():
    first = fitness.generate_program("MG", "advanced", seed=42)
    assert first == fitness.generate_program("MG", "advanced", seed=42)


def test_generator_rejects_bad_experience():
    with pytest.raises(ValidationError, match="experience"):
        fitness.generate_program("MG", "expert")


# ---------- membership ----------

def test_membership_active_expired_none():
    today = date(2026, 6, 1)
    assert fitness.membership_status("2026-12-31", today) == "Active"
    assert fitness.membership_status("2026-06-01", today) == "Active"
    assert fitness.membership_status("2026-01-01", today) == "Expired"
    assert fitness.membership_status(None, today) == "None"


def test_membership_rejects_bad_date():
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        fitness.membership_status("31/12/2026")
