# ACEest Fitness & Gym — Flask Service with CI/CD

![CI](https://github.com/dibyadyuti-bits/aceest-fitness-devops/actions/workflows/main.yml/badge.svg)

A Flask web service for gym management (client profiles, calorie estimates, BMI,
weekly adherence, workout and body-metric logs, and a workout-plan generator),
delivered through an automated pipeline: **Git/GitHub → Pytest → Docker →
Jenkins BUILD → GitHub Actions**.

The business rules were ported from the original Tkinter desktop prototypes
(v1.0 – v3.2.4), which are kept unchanged in [`legacy/`](legacy/) for reference.

---

## Project structure

```
aceest-fitness-devops/
├── app.py                    # Entry point (python app.py / gunicorn app:app)
├── aceest/
│   ├── __init__.py           # Application factory: create_app()
│   ├── fitness.py            # Pure business logic (programs, calories, BMI, generator)
│   ├── db.py                 # SQLite schema and per-request connection
│   └── routes.py             # HTTP endpoints and JSON error handling
├── tests/
│   ├── conftest.py           # Fixtures: fresh app + temp database per test
│   ├── test_fitness.py       # Unit tests for business logic
│   └── test_api.py           # Endpoint tests via Flask's test client
├── Dockerfile                # Multi-stage: base → test → runtime (non-root)
├── Jenkinsfile               # Jenkins BUILD pipeline
├── .github/workflows/main.yml# GitHub Actions CI pipeline
├── requirements.txt          # Runtime dependencies (pinned)
├── requirements-dev.txt      # + pytest, pytest-cov, flake8
└── legacy/                   # Original Tkinter prototypes
```

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | HTML overview of the three programs |
| GET | `/health` | Liveness check (also used by Docker `HEALTHCHECK`) |
| GET | `/api/programs` | List programs (`FL`, `MG`, `BG`) |
| GET | `/api/programs/<code>` | Workout, diet, calorie factor and focus for a program |
| GET | `/api/bmi?weight=70&height=175` | BMI, category and risk note |
| GET | `/api/calories?weight=70&program=MG` | Daily calorie estimate |
| GET / POST | `/api/clients` | List clients / create a client |
| GET / DELETE | `/api/clients/<name>` | Client profile with adherence summary / delete |
| GET / POST | `/api/clients/<name>/progress` | Weekly adherence (0–100) |
| GET / POST | `/api/clients/<name>/workouts` | Workout log (Strength, Hypertrophy, Cardio, Mobility) |
| POST | `/api/clients/<name>/metrics` | Body metrics (weight, waist, body fat) |
| POST | `/api/clients/<name>/generate-program` | Weekly plan by experience level |

Invalid input returns **400**, unknown resources **404**, duplicate clients **409**,
always as JSON: `{"error": "..."}`.

Example:

```bash
curl -X POST http://localhost:5000/api/clients \
     -H "Content-Type: application/json" \
     -d '{"name": "Ravi", "age": 28, "height": 175, "weight": 70, "program": "MG"}'
# → 201 {"name": "Ravi", "calories": 2450, "program": "MG", ...}
```

---

## Local setup and execution

Requires Python 3.9+ (the Docker image uses 3.12) and Git.

```bash
git clone https://github.com/dibyadyuti-bits/aceest-fitness-devops.git
cd aceest-fitness-devops

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

python app.py                      # http://localhost:5000
```

The SQLite file defaults to `aceest_fitness.db` in the working directory; set
`ACEEST_DB=/path/to/file.db` to change it.

## Running the tests manually

```bash
pytest                                             # all tests, verbose
pytest --cov=aceest --cov-report=term-missing      # with coverage
pytest tests/test_fitness.py                       # one file
pytest -k bmi                                      # tests matching a keyword
flake8 .                                           # lint
```

Each test gets a fresh temporary database, so tests are independent and leave
nothing behind. Current result: **69 tests, 99% line coverage**.

## Running with Docker

```bash
# Build and run the tests inside a container
docker build --target test -t aceest-fitness:test .
docker run --rm aceest-fitness:test

# Build and run the production image
docker build -t aceest-fitness .
docker run -d -p 5000:5000 -v aceest-data:/data --name aceest aceest-fitness
curl http://localhost:5000/health
```

Image design: `python:3.12-slim` base; dependencies installed in their own layer
so code changes don't reinstall them; test tools excluded from the runtime image;
`.dockerignore` keeps `.git`, tests caches and `legacy/` out of the build context;
runs as non-root user `aceest`; Gunicorn instead of the Flask dev server;
built-in `HEALTHCHECK`.

---

## CI/CD integration overview

```
 developer ── git push / pull request ──► GitHub
                                           │
               ┌───────────────────────────┴───────────────────────────┐
               ▼                                                       ▼
     GitHub Actions (main.yml)                              Jenkins (Jenkinsfile)
     1. Build & Lint                                        1. Checkout from GitHub
        compileall + flake8                                 2. Setup venv + deps
     2. Docker Build & Test  (needs 1)                      3. Lint
        build test image → pytest in container              4. Unit Tests (JUnit report)
        build runtime image → smoke test /health            5. Docker Build (test + runtime)
```

**GitHub Actions** runs on every `push` (any branch) and every `pull_request`.
Job 1 checks syntax and style on a clean runner; job 2 only starts if job 1
passes, builds the `test` image, runs Pytest inside it, then builds the runtime
image and smoke-tests the live container. A red job blocks the merge.

**Jenkins** is the secondary BUILD and quality gate in a controlled
environment. It pulls the latest code from GitHub (polling every ~5 minutes, or
via webhook), rebuilds a clean virtual environment, lints, runs the tests and
publishes JUnit results, then builds and tests the Docker images (skipped with a
message if the agent cannot reach the Docker daemon). The workspace
is wiped after every run so each build starts clean.

### Setting up the Jenkins job

1. Run Jenkins with Docker access, e.g.
   `docker run -d -p 8080:8080 -v jenkins_home:/var/jenkins_home -v /var/run/docker.sock:/var/run/docker.sock jenkins/jenkins:lts`,
   then install `python3`, `python3-venv` and the Docker CLI inside it.
2. Install the suggested plugins (includes Git, Pipeline and JUnit).
3. **New Item → Pipeline**. Under *Pipeline*, choose **Pipeline script from SCM**,
   SCM **Git**, repository URL of this repo, branch `*/main`, script path `Jenkinsfile`.
4. Save and click **Build Now**. After the first run, the `pollSCM` trigger
   builds automatically on new commits.

---

## Version control strategy

- `main` is always releasable; work happens on short-lived branches:
  `feature/*` (new capability), `test/*` (test suite), `infra/*`
  (Docker/CI/Jenkins), `fix/*` (bug fixes), `docs/*`.
- Branches merge into `main` with `--no-ff` so every feature is visible as one
  merge in the history.
- Commit messages follow Conventional Commits: `feat:`, `fix:`, `test:`,
  `ci:`, `build:`, `docs:`, `chore:`.

## Legacy prototypes

| Version | Adds |
|---|---|
| 1.0 | Three static programs with workout and diet charts |
| 1.1 | Client form, calorie estimate (weight × factor), adherence slider |
| 1.1.2 | Client table, CSV export, matplotlib chart *(file truncated in `reset()`)* |
| 2.0.1 | SQLite persistence for clients and weekly progress (identical to 2.1.2) |
| 2.2.1 | Adherence line chart |
| 2.2.4 | Workouts, exercises, body metrics, BMI with risk notes (identical to 3.0.1) |
| 3.1.2 | Login with roles, experience-based program generator, PDF report |
| 3.2.4 | Dashboard, membership status *(uses `tk.simpledialog` without importing it)* |
