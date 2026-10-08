"""Integration tests for the Flask endpoints, using Flask's test client."""


# ---------- general ----------

def test_home_page_lists_programs(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"ACEest" in response.data and b"Muscle Gain" in response.data


def test_health(client):
    assert client.get("/health").get_json() == {"status": "ok"}


def test_unknown_route_returns_json_404(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert "error" in response.get_json()


# ---------- programs & calculators ----------

def test_list_programs(client):
    assert client.get("/api/programs").get_json() == {
        "FL": "Fat Loss", "MG": "Muscle Gain", "BG": "Beginner",
    }


def test_program_detail(client):
    data = client.get("/api/programs/fl").get_json()
    assert data["code"] == "FL" and data["calorie_factor"] == 22


def test_program_detail_unknown(client):
    assert client.get("/api/programs/ZZ").status_code == 404


def test_bmi_endpoint(client):
    data = client.get("/api/bmi?weight=70&height=175").get_json()
    assert data["bmi"] == 22.9 and data["category"] == "Normal"


def test_bmi_endpoint_missing_params(client):
    response = client.get("/api/bmi?weight=70")
    assert response.status_code == 400


def test_calories_endpoint(client):
    assert client.get("/api/calories?weight=80&program=FL").get_json() == {"calories": 1760}


# ---------- clients ----------

def test_create_client_calculates_calories(ravi):
    assert ravi["calories"] == 2450
    assert ravi["program"] == "MG"
    assert ravi["membership_status"] == "None"


def test_create_client_requires_name(client):
    response = client.post("/api/clients", json={"program": "FL"})
    assert response.status_code == 400
    assert "name" in response.get_json()["error"]


def test_create_client_rejects_bad_program(client):
    response = client.post("/api/clients", json={"name": "A", "program": "XX"})
    assert response.status_code == 400


def test_create_client_rejects_non_json(client):
    response = client.post("/api/clients", data="name=A")
    assert response.status_code == 400


def test_duplicate_client_conflict(client, ravi):
    response = client.post("/api/clients", json={"name": "Ravi", "program": "FL"})
    assert response.status_code == 409


def test_client_without_weight_has_no_calories(client):
    data = client.post("/api/clients", json={"name": "Asha", "program": "BG"}).get_json()
    assert data["calories"] is None


def test_membership_on_create(client):
    data = client.post("/api/clients", json={
        "name": "Kiran", "program": "FL", "membership_end": "2099-01-01",
    }).get_json()
    assert data["membership_status"] == "Active"


def test_list_and_get_client(client, ravi):
    assert [c["name"] for c in client.get("/api/clients").get_json()] == ["Ravi"]
    data = client.get("/api/clients/Ravi").get_json()
    assert data["weeks_logged"] == 0 and data["average_adherence"] is None


def test_get_missing_client(client):
    assert client.get("/api/clients/Ghost").status_code == 404


def test_delete_client_removes_history(client, ravi):
    client.post("/api/clients/Ravi/progress", json={"adherence": 80})
    assert client.delete("/api/clients/Ravi").status_code == 204
    assert client.get("/api/clients/Ravi").status_code == 404


# ---------- progress ----------

def test_progress_updates_average(client, ravi):
    for value in (60, 90):
        assert client.post("/api/clients/Ravi/progress",
                           json={"adherence": value}).status_code == 201
    assert len(client.get("/api/clients/Ravi/progress").get_json()) == 2
    data = client.get("/api/clients/Ravi").get_json()
    assert data["weeks_logged"] == 2 and data["average_adherence"] == 75.0


def test_progress_rejects_out_of_range(client, ravi):
    response = client.post("/api/clients/Ravi/progress", json={"adherence": 150})
    assert response.status_code == 400


def test_progress_for_missing_client(client):
    response = client.post("/api/clients/Ghost/progress", json={"adherence": 50})
    assert response.status_code == 404


# ---------- workouts & metrics ----------

def test_log_and_list_workouts(client, ravi):
    client.post("/api/clients/Ravi/workouts", json={
        "date": "2026-03-01", "workout_type": "Strength", "duration_min": 45,
    })
    client.post("/api/clients/Ravi/workouts", json={
        "date": "2026-03-03", "workout_type": "Cardio", "duration_min": 30,
    })
    workouts = client.get("/api/clients/Ravi/workouts").get_json()
    assert [w["date"] for w in workouts] == ["2026-03-03", "2026-03-01"]


def test_workout_rejects_bad_type(client, ravi):
    response = client.post("/api/clients/Ravi/workouts", json={"workout_type": "Yoga"})
    assert response.status_code == 400


def test_workout_rejects_bad_date(client, ravi):
    response = client.post("/api/clients/Ravi/workouts", json={
        "workout_type": "Strength", "date": "01-03-2026",
    })
    assert response.status_code == 400


def test_log_metrics(client, ravi):
    response = client.post("/api/clients/Ravi/metrics", json={"weight": 69.5, "waist": 82})
    assert response.status_code == 201
    assert response.get_json()["bodyfat"] is None


def test_metrics_need_a_value(client, ravi):
    assert client.post("/api/clients/Ravi/metrics", json={}).status_code == 400


# ---------- program generator ----------

def test_generate_program_for_client(client, ravi):
    data = client.post("/api/clients/Ravi/generate-program",
                       json={"experience": "beginner", "seed": 1}).get_json()
    assert data["program"] == "MG"
    assert len(data["plan"]) == 9  # 3 days x 3 exercises


def test_generate_program_bad_experience(client, ravi):
    response = client.post("/api/clients/Ravi/generate-program",
                           json={"experience": "pro"})
    assert response.status_code == 400
