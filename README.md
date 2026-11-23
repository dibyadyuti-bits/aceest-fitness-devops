# ACEest Fitness & Gym — Flask Service with CI/CD

![CI](https://github.com/dibyadyuti-bits/aceest-fitness-devops/actions/workflows/main.yml/badge.svg)

A Flask web service for gym management (client profiles, calorie estimates, BMI,
weekly adherence, workout and body-metric logs, and a workout-plan generator),
delivered through an automated pipeline:

**Git/GitHub → Pytest → SonarCloud quality gate → Docker → Docker Hub → Jenkins →
Kubernetes (Minikube) with rolling, blue-green, canary, A/B and shadow releases and
automatic rollback.**

The business rules were ported from the original Tkinter desktop prototypes
(v1.0 – v3.2.4), which are kept unchanged in [`legacy/`](legacy/) for reference.

| Release | Content |
|---|---|
| `v1.0.0` | Assignment 1: Flask app, Pytest suite, Docker, GitHub Actions, Jenkins BUILD |
| `v2.0.0` | Assignment 2: `/version` endpoint, `ACEest_Fitness.py` entry point, SonarCloud, Docker Hub, Kubernetes release strategies with rollback |

---

## Project structure

```
aceest-fitness-devops/
├── ACEest_Fitness.py         # Main module (python ACEest_Fitness.py / gunicorn ACEest_Fitness:app)
├── app.py                    # Creates the app object from the factory
├── VERSION                   # Release version, reported by /version and used for image tags
├── aceest/
│   ├── __init__.py           # Application factory: create_app(), read_version()
│   ├── fitness.py            # Pure business logic (programs, calories, BMI, generator)
│   ├── db.py                 # SQLite schema and per-request connection
│   └── routes.py             # HTTP endpoints and JSON error handling
├── tests/                    # Pytest: business logic, API, versioning, entry point
├── Dockerfile                # Multi-stage: base → test → runtime (non-root, Gunicorn)
├── Jenkinsfile               # Jenkins CI/CD pipeline
├── .github/workflows/main.yml# GitHub Actions pipeline
├── sonar-project.properties  # SonarCloud project and quality-gate settings
├── k8s/
│   ├── release.sh            # deploy / smoke / promote / rollback / status / traffic
│   ├── templates/            # Deployment and Service shared by every strategy
│   └── <strategy>/           # Ingress rules for rolling, blue-green, canary, ab-testing, shadow
├── docs/REPORT.md            # Assignment report
└── legacy/                   # Original Tkinter prototypes
```

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | HTML overview of the three programs, with the running version |
| GET | `/health` | Liveness/readiness check (Docker `HEALTHCHECK`, Kubernetes probes) |
| GET | `/version` | `{"version", "variant", "pod"}`: which release and deployment track answered |
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

---

## Local setup and execution

Requires Python 3.9+ (the Docker image uses 3.12) and Git.

```bash
git clone https://github.com/dibyadyuti-bits/aceest-fitness-devops.git
cd aceest-fitness-devops

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

python ACEest_Fitness.py           # http://localhost:5000
```

Environment variables: `ACEEST_DB` (SQLite path, default `aceest_fitness.db`),
`APP_VERSION` (overrides the `VERSION` file), `APP_VARIANT` (deployment track name),
`PORT`.

## Running the tests

```bash
pytest                                  # all tests, verbose
pytest --cov --cov-report=term-missing  # with coverage (.coveragerc)
pytest -k version                       # tests matching a keyword
flake8 .                                # lint
```

Each test gets a fresh temporary database. Current result: **78 tests, 99% line coverage**.

## Docker

```bash
docker build --target test -t aceest-fitness:test . && docker run --rm aceest-fitness:test
docker build --build-arg APP_VERSION=2.0.0 -t aceest-fitness:2.0.0 .
docker run -d -p 5000:5000 -v aceest-data:/data aceest-fitness:2.0.0
curl http://localhost:5000/version
```

Image design: `python:3.12-slim`; dependencies in their own cached layer; test tools
only in the `test` stage; runs as non-root user `aceest`; Gunicorn; `HEALTHCHECK`;
version baked in with `--build-arg APP_VERSION`.

### Docker Hub

Images are pushed to `docker.io/<dockerhub-user>/aceest-fitness` with these tags:

| Tag | Pushed by | When |
|---|---|---|
| `2.0.0-b<build>` | Jenkins | every build |
| `2.0.0`, `latest` | Jenkins, GitHub Actions | every build / every `v*` git tag |
| `v2.0.0` | Jenkins | build of a tagged commit |
| `1.0.0` | manual, once | Assignment 1 baseline (see below) |

The Assignment 1 release has no publish step, so push it once by hand:

```bash
docker build -t <dockerhub-user>/aceest-fitness:1.0.0 \
  https://github.com/dibyadyuti-bits/aceest-fitness-devops.git#v1.0.0
docker push <dockerhub-user>/aceest-fitness:1.0.0
```

---

## CI/CD overview

```
developer ── push / PR / tag ──► GitHub
                                   │
         ┌─────────────────────────┴──────────────────────────┐
         ▼                                                    ▼
 GitHub Actions (main.yml)                          Jenkins (Jenkinsfile, polls SCM)
 1. Build & Lint: compileall, flake8, shellcheck    1. Checkout, read VERSION
 2. Pytest + coverage → SonarCloud quality gate     2. Clean venv, lint
 3. Docker: Pytest in container, runtime image,     3. Pytest (JUnit + coverage XML)
    smoke test /health and /version                 4. SonarCloud analysis + quality gate
 4. v* tag: push image to Docker Hub                5. Docker build, Pytest in container,
                                                       runtime container version check
                                                    6. Push to Docker Hub
                                                    7. Build artifacts (source tarball, build info)
                                                    8. Deploy to Minikube with the chosen strategy
                                                    9. Smoke test → automatic rollback on failure
```

### SonarCloud setup

1. Sign in at <https://sonarcloud.io> with GitHub and import the
   `dibyadyuti-bits/aceest-fitness-devops` repository (organization `dibyadyuti-bits`,
   project key `dibyadyuti-bits_aceest-fitness-devops`, as in `sonar-project.properties`).
2. *Administration → Analysis Method*: turn **off** Automatic Analysis (CI sends the
   coverage report instead).
3. *My Account → Security*: generate a token. Save it as the GitHub repository secret
   `SONAR_TOKEN` and as the Jenkins credential `sonarcloud-token` (Secret text).

`sonar.qualitygate.wait=true` makes both pipelines fail when the quality gate fails.

### Jenkins setup

1. Jenkins needs `git`, `python3` + `python3-venv`, the Docker CLI with access to the
   daemon, and `kubectl` for the deploy stages. Running Jenkins on the same machine as
   Minikube is simplest:
   ```bash
   docker run -d --name jenkins -p 8080:8080 -v jenkins_home:/var/jenkins_home \
     -v /var/run/docker.sock:/var/run/docker.sock jenkins/jenkins:lts
   ```
   then install `python3 python3-venv docker.io kubectl` inside the container.
2. Plugins: Pipeline, Git, JUnit, Credentials Binding, Timestamper.
3. Credentials (*Manage Jenkins → Credentials*):
   - `sonarcloud-token`: Secret text
   - `dockerhub-creds`: Username with password (Docker Hub user + access token)
   - `kubeconfig`: Secret file. Export it with `kubectl config view --flatten --minify`
     and change the server address so Jenkins can reach the Minikube API.
4. *New Item → Pipeline → Pipeline script from SCM*, Git, this repository, branch
   `*/main`, script path `Jenkinsfile`. Run **Build with Parameters** once so the
   parameters appear; after that `pollSCM` builds on every new commit.

Parameters: `DEPLOY_STRATEGY` (none / rolling / blue-green / canary / ab-testing / shadow),
`BASELINE_TAG`, `CANARY_WEIGHT`, `RUN_SONAR`, `PUSH_IMAGE` and `SIMULATE_BAD_RELEASE`,
which makes the smoke test fail on purpose to show the automatic rollback.

---

## Kubernetes deployment (Minikube)

### Cluster setup

```bash
minikube start --cpus 2 --memory 4096
minikube addons enable ingress
minikube tunnel            # separate terminal: exposes the ingress on 127.0.0.1:80
```

Each strategy runs in its own namespace (`aceest-<strategy>`) and is served under
`http://127.0.0.1/<strategy>/`. Pods set `SCRIPT_NAME=/<strategy>`, so Gunicorn serves
the app under that prefix and the ingress needs no URL rewriting.

### Strategies

```bash
IMG=<dockerhub-user>/aceest-fitness
k8s/release.sh deploy rolling     $IMG:2.0.0
k8s/release.sh deploy blue-green  $IMG:2.0.0
k8s/release.sh deploy canary      $IMG:2.0.0 $IMG:1.0.0   # 1.0.0 = stable baseline
k8s/release.sh deploy ab-testing  $IMG:2.0.0 $IMG:1.0.0
k8s/release.sh deploy shadow      $IMG:2.0.0 $IMG:1.0.0
k8s/release.sh status
```

| Strategy | How it works | Promote | Rollback |
|---|---|---|---|
| Rolling update | 3 replicas replaced one at a time (`maxSurge 1`, `maxUnavailable 0`), readiness probe gates each pod | — | `kubectl rollout undo` |
| Blue-green | New version goes to the idle colour, is smoke-tested, then the `aceest-live` Service selector switches to it; the old colour keeps running | old colour scaled to 0 | selector switched back (instant) |
| Canary | NGINX canary ingress sends `CANARY_WEIGHT`% (default 20) to the canary; `X-Canary: always` forces it | stable takes the canary image | canary ingress removed, canary scaled to 0 |
| A/B testing | Variant B only for `X-Variant: B` header or `variant=always` cookie; everyone else gets A | A takes the B image | B ingress removed, B scaled to 0 |
| Shadow | Users are answered by the primary; NGINX mirrors every request to the shadow (responses discarded) | primary takes the shadow image | mirroring stopped, shadow scaled to 0 |

```bash
k8s/release.sh smoke    canary 2.0.0     # /health and /version of every track
k8s/release.sh traffic  canary 50        # count versions answering through the ingress
AB_GROUP=B k8s/release.sh traffic ab-testing 10
k8s/release.sh promote  canary
k8s/release.sh rollback blue-green
```

Images built only locally can be loaded with `minikube image load <image>`.

### Public endpoint

Minikube is only reachable from this machine. To give reviewers a URL, port-forward the
ingress controller and publish it with a Cloudflare quick tunnel (no account needed). Keep
both commands running; the URL changes on every run.

```bash
kubectl -n ingress-nginx port-forward --address 0.0.0.0 svc/ingress-nginx-controller 8081:80
cloudflared tunnel --url http://localhost:8081
# https://<random>.trycloudflare.com/rolling/  /blue-green/  /canary/  /ab-testing/  /shadow/
```

---

## Version control strategy

- `main` is always releasable; work happens on short-lived branches: `feature/*`,
  `fix/*`, `test/*`, `ci/*`, `infra/*`, `docs/*`, merged through pull requests.
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `test:`, `ci:`, `build:`,
  `docs:`, `chore:`).
- Releases are annotated tags `vX.Y.Z` matching the `VERSION` file; a tag push publishes
  the Docker image.

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
