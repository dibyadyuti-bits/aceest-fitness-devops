# ACEest Fitness & Gym — CI/CD Pipeline Report

**Course:** Introduction to DevOps (CSIZG514/SEZG514), Assignment 2
**Student:** Dibyadyuti Roy (2025TM93192)
**Repository:** <https://github.com/dibyadyuti-bits/aceest-fitness-devops>
**Docker Hub:** `https://hub.docker.com/r/dibyadyutibits/aceest-fitness`
**Cluster endpoint:** <https://cove-petersburg-red-addresses.trycloudflare.com/> (one path per strategy: `/rolling/`, `/blue-green/`, `/canary/`, `/ab-testing/`, `/shadow/`)

## 1. CI/CD architecture overview

The application is the Flask + SQLite gym-management service from Assignment 1
(release `v1.0.0`), extended for continuous delivery in release `v2.0.0`. Business logic
(`aceest/fitness.py`) is free of Flask and database code so it can be unit-tested on its
own. The HTTP layer is a single blueprint, and `ACEest_Fitness.py` is the entry point
Gunicorn serves. A `VERSION` file and the `/version` endpoint (version, deployment
variant, pod name) let every stage of the pipeline check which release is actually running.

```
 push / PR / tag ─► GitHub ─┬─► GitHub Actions: lint → Pytest + SonarCloud gate
                            │                    → Docker build, Pytest in container, smoke test
                            │                    → (v* tag) push image to Docker Hub
                            └─► Jenkins (pollSCM): lint → Pytest → SonarCloud gate
                                                 → Docker build + container tests → Docker Hub
                                                 → artifacts → deploy to Minikube (strategy)
                                                 → smoke test → automatic rollback
```

| Concern | Tool | Implementation |
|---|---|---|
| Version control | Git, GitHub | Feature/ci/docs branches, pull requests, Conventional Commits, tags `v1.0.0`, `v2.0.0` |
| Testing | Pytest, pytest-cov | 78 tests, 99% line coverage; run on the agent and again inside the Docker `test` image |
| Code quality | SonarCloud | `sonar-project.properties`; coverage and JUnit reports imported; `sonar.qualitygate.wait=true` fails the build on a red gate |
| Build server | Jenkins | Declarative `Jenkinsfile`, SCM polling every 5 minutes, parameters for strategy and demos, JUnit results and archived artifacts |
| Containerisation | Docker | Multi-stage `Dockerfile` (`base` → `test` → `runtime`), non-root user, Gunicorn, health check, version build argument |
| Registry | Docker Hub | Tags `<version>-b<build>`, `<version>`, `latest`, `v<version>`; `1.0.0` holds the Assignment 1 baseline |
| Orchestration | Kubernetes (Minikube) + ingress-nginx | One namespace per strategy, shared Deployment/Service templates, `k8s/release.sh` |

### Deployment strategies

All five strategies run side by side on one cluster, each in namespace `aceest-<strategy>`
and served at `/<strategy>/`. Pods set `SCRIPT_NAME=/<strategy>`, so Gunicorn serves the
app under that prefix and no ingress URL rewriting is needed.

- **Rolling update:** 3 replicas with `maxSurge: 1`, `maxUnavailable: 0`. A readiness
  probe on `/health` admits each new pod before an old one is removed, so capacity never
  drops. Rollback: `kubectl rollout undo`.
- **Blue-green:** the new image goes to the idle colour and is smoke-tested through its own
  Service. Only then is the `aceest-live` Service selector switched. The previous colour
  keeps running, so rollback is an instant selector switch.
- **Canary:** an NGINX canary ingress routes a configurable share (default 20%) of requests
  to the canary track. Promotion moves the stable track to the canary image; rollback
  deletes the canary ingress and scales the canary to zero.
- **A/B testing:** variant B is served only to a user segment (header `X-Variant: B` or
  cookie `variant=always`); everyone else gets variant A.
- **Shadow:** users are answered only by the primary track. NGINX mirrors every request to
  the shadow track, whose responses are discarded, so the new version is tested with real
  traffic at zero user risk.

**Rollback in the pipeline:** after deploying, Jenkins runs `release.sh smoke`, which calls
`/health` and `/version` of every track from inside the cluster and checks the expected
version. A failed deploy or smoke test triggers `release.sh rollback` for that strategy and
marks the build failed. The `SIMULATE_BAD_RELEASE` parameter demonstrates this on demand.

## 2. Challenges and mitigation

| Challenge | Mitigation |
|---|---|
| The shared Jenkins lab agent could not reach the Docker daemon, which failed the whole build (Assignment 1). | The pipeline detects Docker once at checkout and skips only the Docker stages with a clear message; GitHub Actions always builds and tests the image. A Jenkins instance next to Minikube runs the full pipeline. |
| Dependency pins required a newer Python than the lab agent's Python 3.9. | Pinned versions that support 3.9+ (fix released in Assignment 1); the Docker image fixes Python 3.12, so production does not depend on the agent. |
| One app had to sit behind five strategies on one ingress without the routes colliding. | Path prefix per strategy, with Gunicorn's `SCRIPT_NAME` support instead of regex rewrites. This also keeps the original URI intact, which shadow mirroring needs. |
| Knowing which version actually served a request during canary, A/B and shadow tests. | `/version` reports version, variant and pod; `release.sh traffic` tallies responses through the ingress. |
| SQLite is a per-pod file, so replicas do not share data. | Acceptable for demonstrating release mechanics (`emptyDir` per pod); documented that real persistence needs a shared database such as PostgreSQL. |
| Scripts written on Windows broke on Linux agents (CRLF line endings, Git Bash path conversion). | `.gitattributes` forces LF for scripts and manifests; `release.sh` disables MSYS path conversion and is linted by ShellCheck in CI. |
| Minikube is not reachable from the internet, but the brief asks for an endpoint URL. | `minikube tunnel` plus a Cloudflare quick tunnel publishes the ingress over HTTPS. |

## 3. Key automation outcomes

- Every push and pull request is linted, tested (78 tests, 99% coverage) and built into a
  container that is tested again, on both GitHub Actions and Jenkins.
- SonarCloud analysis with an enforced quality gate: gate **Passed** on
  `main`, 0 bugs, 0 vulnerabilities, 0 code smells (reliability, security and
  maintainability all rated A), 99.6% coverage and 0% duplication.
- Every Jenkins build produces a versioned image on Docker Hub, a source tarball and a
  build-info file (version, commit, tag, image) archived with the JUnit and SonarCloud
  reports.
- One parameterised Jenkins job deploys any of the five strategies to Kubernetes,
  verifies the release from inside the cluster and rolls back automatically on failure.
  The bad-release demo showed the previous version restored in Jenkins build #4
  (smoke test failed → `release.sh rollback` → previous ReplicaSet live again).
- Releases are traceable end to end: git tag → `VERSION` → image tag → `/version` in the
  running pod.

Screenshots of every step (CI runs, SonarCloud, Docker Hub tags, Jenkins builds #1–#10
including the #4 rollback, pods, traffic splits and the public endpoint) are in
`Screenshots/assignment-2/`.
