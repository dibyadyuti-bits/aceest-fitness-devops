# ACEest Fitness & Gym — Assignment Steps

Step-by-step guide to complete and submit **Introduction to DevOps
(CSIZG514/SEZG514) (S1-26), Assignment 1: Implementing Automated CI/CD Pipelines
for ACEest Fitness & Gym**. It is based on the brief
`Introduction to DevOps Assignment - 1 2026 (1).docx`.

**What you submit:** a link to a **publicly accessible GitHub repository**. The brief
asks for nothing else (no separate report), so the repo, its commit history, the
green GitHub Actions runs and a working Jenkins build are what get graded.

Commands are given for **Windows (PowerShell / Git Bash)**, which is this machine's setup.
Tools already installed here: Python 3.13, Git 2.46, Docker 29.6.

---

## Assignment phases → where they are in this repo

| # | Phase (from the brief) | Deliverable in this repo | Status |
|---|---|---|---|
| 1 | Application Development & Modularization: Flask app built from the baseline scripts | `app.py`, `aceest/` (factory, logic, DB, routes); baselines in `legacy/` | ✅ Done, runs locally |
| 2 | VCS Strategy: local Git repo synced to GitHub, descriptive commits, branches for features / fixes / infra | `setup_git_history.sh` → `feature/*`, `test/*`, `infra/*`, `docs/*` branches, `--no-ff` merges | ⬜ Step 3 |
| 3 | Unit Testing & Validation: Pytest suite validating the app's internal logic | `tests/test_fitness.py`, `tests/test_api.py`: 69 tests, 99% coverage | ✅ Done, passing |
| 4 | Containerization with Docker: app, environment and dependencies in a portable image | Multi-stage `Dockerfile`, `.dockerignore` | ✅ Written. Verify in Step 4 |
| 5 | Jenkins BUILD & Quality Gate: job pulls the latest code from GitHub and does a clean build | `Jenkinsfile` (checkout → fresh venv → lint → tests → Docker build) | ⬜ Step 6 |
| 6 | GitHub Actions on every `push` / `pull_request`: **Build & Lint**, **Docker Image Assembly**, **Automated Testing inside the container** | `.github/workflows/main.yml` | ✅ Written. Runs after push (Step 5) |

## Required deliverables checklist (from the brief)

| Deliverable | File(s) |
|---|---|
| Source code (`app.py`, `requirements.txt`) | `app.py`, `aceest/*.py`, `requirements.txt`, `requirements-dev.txt` |
| Test suite (all Pytest files) | `tests/`, `pytest.ini` |
| Infrastructure as Code: Dockerfile + GitHub Actions YAML | `Dockerfile`, `.dockerignore`, `.github/workflows/main.yml` (+ `Jenkinsfile`) |
| README: local setup and execution | `README.md` → *Local setup and execution* |
| README: steps to run tests manually | `README.md` → *Running the tests manually* |
| README: overview of the Jenkins + GitHub Actions integration | `README.md` → *CI/CD integration overview* |

## How each evaluation criterion is met

| Criterion | What the evaluator will see |
|---|---|
| **Application Integrity** | 13 working endpoints, JSON errors (400/404/409), SQLite persistence |
| **VCS Maturity** | Conventional-Commit messages (`feat:`, `test:`, `ci:`, `build:`, `docs:`), one branch per concern, `--no-ff` merges |
| **Testing Coverage** | 69 tests covering business logic and every endpoint, including error paths. 99% line coverage |
| **Docker Efficiency** | `python:3.12-slim`, multi-stage (test tools excluded from runtime), cached dependency layer, `.dockerignore`, non-root user, Gunicorn, `HEALTHCHECK` |
| **Pipeline Reliability** | Jenkins build green with JUnit results. GitHub Actions green on every push |
| **Documentation Clarity** | README with structure, API table, setup, tests, Docker, CI/CD diagram, branching strategy |

> ⚠️ Don't commit the assignment brief (`*.docx`) to the public repo. `setup_git_history.sh`
> only adds named files, so it's safe. Just don't run `git add .` while the `.docx` is in
> this folder. Moving it out is the simplest fix.

---

## Step 0 — Clean up the project folder

Delete the stray folder created by a failed `mkdir {a,b,c}` brace expansion:

```powershell
Remove-Item -Recurse -Force "D:\Assignment\aceest-fitness-devops\{aceest,tests,legacy,.github"
```

Delete any local SQLite file left over from manual testing (it's git-ignored, but keeps things tidy):

```powershell
Remove-Item -ErrorAction SilentlyContinue aceest_fitness.db
```

---

## Step 1 — Run the app locally

```powershell
cd D:\Assignment\aceest-fitness-devops
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python app.py
```

Open <http://localhost:5000>, then try the API from a second terminal:

```bash
curl http://localhost:5000/health
curl "http://localhost:5000/api/bmi?weight=70&height=175"
curl -X POST http://localhost:5000/api/clients -H "Content-Type: application/json" \
     -d '{"name": "Ravi", "age": 28, "height": 175, "weight": 70, "program": "MG"}'
curl -X POST http://localhost:5000/api/clients/Ravi/generate-program \
     -H "Content-Type: application/json" -d '{"experience": "beginner"}'
```

Stop the server with `Ctrl+C` before Step 4. Docker needs port 5000 free.

📸 **Screenshot for report:** browser on `/` and a terminal showing API responses.

---

## Step 2 — Run the tests and lint

```powershell
pytest                                          # 69 passed
pytest --cov=aceest --cov-report=term-missing   # coverage ~99%
flake8 .                                        # no output = clean
```

📸 **Screenshot:** the `69 passed` summary and the coverage table.

---

## Step 3 — Create the Git history and push to GitHub

1. Set your Git identity (if you haven't already):
   ```bash
   git config --global user.name  "Your Name"
   git config --global user.email "you@example.com"
   ```
2. Build the history from **Git Bash** in the project folder:
   ```bash
   bash setup_git_history.sh
   ```
   This creates `main` plus `legacy/prototypes`, `feature/flask-core`, `test/pytest-suite`,
   `infra/docker`, `infra/github-actions`, `infra/jenkins` and `docs/readme`.
   Each branch has Conventional-Commit messages and merges into `main` with `--no-ff`.
   The script excludes itself from the repo.
3. Commit this steps file too (optional):
   ```bash
   git add ASSIGNMENT_STEPS.md && git commit -m "docs: add assignment steps guide"
   ```
4. On GitHub, create an **empty public** repo named `aceest-fitness-devops`
   (no README, no .gitignore, no license).
5. Push all branches:
   ```bash
   git remote add origin git@github-aceest:dibyadyuti-bits/aceest-fitness-devops.git
   git push -u origin --all
   ```
6. Check the history:
   ```bash
   git log --oneline --graph --all
   ```

📸 **Screenshot:** `git log --graph` output and the GitHub branches page.

---

## Step 4 — Build and run with Docker

Start **Docker Desktop** first, then:

```powershell
# Run the test suite inside a container
docker build --target test -t aceest-fitness:test .
docker run --rm aceest-fitness:test

# Build and run the production image (Gunicorn, non-root user, healthcheck)
docker build -t aceest-fitness .
docker run -d -p 5000:5000 -v aceest-data:/data --name aceest aceest-fitness
curl http://localhost:5000/health
docker ps                      # STATUS should show "(healthy)" after ~30s
```

Clean up:

```powershell
docker rm -f aceest
```

📸 **Screenshots:** test run inside the container, `docker images`, and `docker ps` showing *healthy*.

---

## Step 5 — GitHub Actions CI

Nothing to configure. The push in Step 3 triggers `.github/workflows/main.yml`.

1. Open the repo's **Actions** tab, where the **CI** workflow should be running or done.
2. Confirm both jobs are green:
   - **Build & Lint**: `compileall` syntax check and `flake8`
   - **Docker Build & Test**: builds the test image, runs Pytest in it, builds the runtime image, and smoke-tests `/health` and `/api/programs`
3. Optional: show that the pipeline gates merges. Open a PR from a new branch and watch the check run on it.
   ```bash
   git checkout -b fix/demo
   # make a small change
   git commit -am "fix: demo change" && git push -u origin fix/demo
   ```
   Then open the pull request on GitHub.

📸 **Screenshot:** Actions run summary with both jobs passing.

---

## Step 6 — Jenkins BUILD pipeline

1. Run Jenkins in Docker with access to the host's Docker daemon:
   ```powershell
   docker run -d --name jenkins -p 8080:8080 -p 50000:50000 `
     -v jenkins_home:/var/jenkins_home `
     -v /var/run/docker.sock:/var/run/docker.sock `
     -u root jenkins/jenkins:lts
   ```
2. Install Python and the Docker CLI inside the container (the `Jenkinsfile` needs `python3`, `python3-venv` and `docker`):
   ```powershell
   docker exec -u root jenkins bash -c "apt-get update && apt-get install -y python3 python3-venv python3-pip docker.io"
   ```
3. Get the initial admin password and open <http://localhost:8080>:
   ```powershell
   docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
   ```
   Choose **Install suggested plugins** (includes Git, Pipeline and JUnit) and create an admin user.
4. **New Item → `aceest-fitness` → Pipeline → OK.**
   - *Pipeline → Definition:* **Pipeline script from SCM**
   - *SCM:* **Git**, Repository URL `https://github.com/dibyadyuti-bits/aceest-fitness-devops.git`
   - *Branch:* `*/main` · *Script Path:* `Jenkinsfile`
   - Save.
5. Click **Build Now**. The stages are **Checkout → Setup Environment → Lint → Unit Tests → Docker Build**.
6. After the first build, the `pollSCM('H/5 * * * *')` trigger rebuilds automatically on new commits.

📸 **Screenshots:** Stage View with all stages green, the **Test Result** page (69 tests),
and the console output's final `BUILD #n passed` line.

**Troubleshooting**
- `docker: permission denied`: the container must run with `-u root`, or the socket's group must include the jenkins user.
- `python3: not found`: re-run step 2. The packages are lost if the container is recreated without the volume.

---

## Step 7 — Final documentation touches

- `README.md` already points at `dibyadyuti-bits` (CI badge and clone URL). Once pushed, the badge shows the live CI status.
- Make sure the README covers local setup, running tests, and the CI/CD overview. It already does.

---

## Step 8 — Submission checklist

- [ ] Repository is **public**: open it in a private/incognito window to confirm
- [ ] `main` and all feature branches pushed. The brief `.docx` is **not** in the repo
- [ ] Commit history shows meaningful Conventional-Commit messages and `--no-ff` merges
- [ ] `pytest` passes locally (69 tests) and inside Docker
- [ ] Docker image builds and the container reports *healthy*
- [ ] GitHub Actions run is green (both jobs) on the latest push
- [ ] Jenkins pipeline build is green, pulling from the GitHub repo, with JUnit test results published
- [ ] README badge and URLs updated with your username
- [ ] Submit the repo link: `https://github.com/dibyadyuti-bits/aceest-fitness-devops`

The brief only asks for the repo link. The screenshots suggested above are optional
evidence, worth keeping in case the evaluator asks for proof of the Jenkins build,
since Jenkins runs locally and they can't see it.

---

## Quick reference

| Task | Command |
|---|---|
| Run app | `python app.py` |
| Tests | `pytest` |
| Coverage | `pytest --cov=aceest --cov-report=term-missing` |
| Lint | `flake8 .` |
| Docker tests | `docker build --target test -t aceest-fitness:test . && docker run --rm aceest-fitness:test` |
| Docker app | `docker build -t aceest-fitness . && docker run -d -p 5000:5000 aceest-fitness` |
| Git history | `bash setup_git_history.sh` |
