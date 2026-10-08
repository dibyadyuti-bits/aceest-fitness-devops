"""HTTP endpoints for ACEest Fitness & Gym."""

import sqlite3
from datetime import date

from flask import Blueprint, abort, jsonify, render_template_string, request

from . import fitness
from .db import get_db
from .fitness import ValidationError

bp = Blueprint("api", __name__)

HOME_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ACEest Fitness &amp; Gym</title>
<style>
 body{font-family:system-ui,sans-serif;background:#1a1a1a;color:#eee;
      margin:0;padding:2rem;max-width:960px;margin:auto}
 h1{color:#d4af37} .card{background:#262626;border-left:4px solid #d4af37;
      padding:1rem 1.25rem;margin:1rem 0;border-radius:6px}
 code{color:#d4af37}
</style></head><body>
<h1>ACEest Functional Fitness</h1>
<p>Gym management service. JSON API lives under <code>/api</code>.</p>
{% for code, p in programs.items() %}
<div class="card"><h2>{{ p.name }} ({{ code }})</h2>
<p>Calorie factor: {{ p.calorie_factor }} kcal per kg &middot;
Focus: {{ p.focus }}</p>
<ul>{% for line in p.workout %}<li>{{ line }}</li>{% endfor %}</ul></div>
{% endfor %}
</body></html>"""


# ---------- helpers ----------

def _json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("request body must be a JSON object")
    return data


def _client_or_404(name):
    row = get_db().execute(
        "SELECT * FROM clients WHERE name = ?", (name,)
    ).fetchone()
    if row is None:
        abort(404, description=f"client '{name}' not found")
    return row


def _client_to_dict(row):
    client = dict(row)
    client.pop("id")
    client["membership_status"] = fitness.membership_status(
        client["membership_end"]
    )
    return client


def _optional_positive(data, field):
    value = data.get(field)
    if value in (None, ""):
        return None
    return fitness._positive_number(value, field)


# ---------- general ----------

@bp.get("/")
def home():
    return render_template_string(HOME_PAGE, programs=fitness.PROGRAMS)


@bp.get("/health")
def health():
    get_db().execute("SELECT 1")
    return jsonify(status="ok")


# ---------- programs & calculators ----------

@bp.get("/api/programs")
def list_programs():
    return jsonify({code: p["name"] for code, p in fitness.PROGRAMS.items()})


@bp.get("/api/programs/<code>")
def program_detail(code):
    try:
        program = fitness.get_program(code)
    except ValidationError as exc:
        abort(404, description=str(exc))
    return jsonify(code=code.upper(), **program)


@bp.get("/api/bmi")
def bmi():
    result = fitness.calculate_bmi(
        request.args.get("weight"), request.args.get("height")
    )
    return jsonify(result)


@bp.get("/api/calories")
def calories():
    value = fitness.calculate_calories(
        request.args.get("weight"), request.args.get("program", "")
    )
    return jsonify(calories=value)


# ---------- clients ----------

@bp.get("/api/clients")
def list_clients():
    rows = get_db().execute("SELECT * FROM clients ORDER BY name").fetchall()
    return jsonify([_client_to_dict(r) for r in rows])


@bp.post("/api/clients")
def create_client():
    data = _json_body()
    name = str(data.get("name", "")).strip()
    if not name:
        raise ValidationError("name is required")
    program = str(data.get("program", "")).upper()
    fitness.get_program(program)

    weight = _optional_positive(data, "weight")
    age = _optional_positive(data, "age")
    target_adherence = data.get("target_adherence")
    if target_adherence is not None:
        target_adherence = fitness.validate_adherence(target_adherence)
    membership_end = data.get("membership_end")
    if membership_end:
        fitness.parse_date(membership_end, "membership_end")

    try:
        get_db().execute(
            """INSERT INTO clients (name, age, height, weight, program,
               calories, target_weight, target_adherence, membership_end)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                int(age) if age else None,
                _optional_positive(data, "height"),
                weight,
                program,
                fitness.calculate_calories(weight, program) if weight else None,
                _optional_positive(data, "target_weight"),
                target_adherence,
                membership_end,
            ),
        )
        get_db().commit()
    except sqlite3.IntegrityError:
        return jsonify(error=f"client '{name}' already exists"), 409

    return jsonify(_client_to_dict(_client_or_404(name))), 201


@bp.get("/api/clients/<name>")
def get_client(name):
    client = _client_or_404(name)
    summary = get_db().execute(
        "SELECT COUNT(*) AS weeks, AVG(adherence) AS avg FROM progress "
        "WHERE client_id = ?", (client["id"],)
    ).fetchone()
    result = _client_to_dict(client)
    result["weeks_logged"] = summary["weeks"]
    result["average_adherence"] = (
        round(summary["avg"], 1) if summary["avg"] is not None else None
    )
    return jsonify(result)


@bp.delete("/api/clients/<name>")
def delete_client(name):
    client = _client_or_404(name)
    get_db().execute("DELETE FROM clients WHERE id = ?", (client["id"],))
    get_db().commit()
    return "", 204


# ---------- progress, workouts, metrics ----------

@bp.post("/api/clients/<name>/progress")
def add_progress(name):
    client = _client_or_404(name)
    adherence = fitness.validate_adherence(_json_body().get("adherence"))
    week = date.today().strftime("Week %U - %Y")
    get_db().execute(
        "INSERT INTO progress (client_id, week, adherence) VALUES (?, ?, ?)",
        (client["id"], week, adherence),
    )
    get_db().commit()
    return jsonify(week=week, adherence=adherence), 201


@bp.get("/api/clients/<name>/progress")
def list_progress(name):
    client = _client_or_404(name)
    rows = get_db().execute(
        "SELECT week, adherence FROM progress WHERE client_id = ? "
        "ORDER BY id", (client["id"],)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.post("/api/clients/<name>/workouts")
def add_workout(name):
    client = _client_or_404(name)
    data = _json_body()
    workout_date = data.get("date") or date.today().isoformat()
    fitness.parse_date(workout_date, "date")
    workout_type = data.get("workout_type")
    if workout_type not in fitness.WORKOUT_TYPES:
        raise ValidationError(
            f"workout_type must be one of {', '.join(fitness.WORKOUT_TYPES)}"
        )
    duration = int(fitness._positive_number(
        data.get("duration_min", 60), "duration_min"
    ))
    get_db().execute(
        "INSERT INTO workouts (client_id, date, workout_type, duration_min, "
        "notes) VALUES (?, ?, ?, ?, ?)",
        (client["id"], workout_date, workout_type, duration,
         data.get("notes", "")),
    )
    get_db().commit()
    return jsonify(date=workout_date, workout_type=workout_type,
                   duration_min=duration, notes=data.get("notes", "")), 201


@bp.get("/api/clients/<name>/workouts")
def list_workouts(name):
    client = _client_or_404(name)
    rows = get_db().execute(
        "SELECT date, workout_type, duration_min, notes FROM workouts "
        "WHERE client_id = ? ORDER BY date DESC", (client["id"],)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.post("/api/clients/<name>/metrics")
def add_metrics(name):
    client = _client_or_404(name)
    data = _json_body()
    metric_date = data.get("date") or date.today().isoformat()
    fitness.parse_date(metric_date, "date")
    values = {f: _optional_positive(data, f)
              for f in ("weight", "waist", "bodyfat")}
    if all(v is None for v in values.values()):
        raise ValidationError("provide at least one of weight, waist, bodyfat")
    get_db().execute(
        "INSERT INTO metrics (client_id, date, weight, waist, bodyfat) "
        "VALUES (?, ?, ?, ?, ?)",
        (client["id"], metric_date, values["weight"], values["waist"],
         values["bodyfat"]),
    )
    get_db().commit()
    return jsonify(date=metric_date, **values), 201


@bp.post("/api/clients/<name>/generate-program")
def generate_program(name):
    client = _client_or_404(name)
    data = _json_body()
    plan = fitness.generate_program(
        client["program"], data.get("experience"), seed=data.get("seed")
    )
    return jsonify(client=name, program=client["program"], plan=plan)


# ---------- errors ----------

@bp.app_errorhandler(ValidationError)
def handle_validation(exc):
    return jsonify(error=str(exc)), 400


@bp.app_errorhandler(404)
def handle_404(exc):
    return jsonify(error=exc.description), 404
