# SonarQube (SonarCloud) code quality report

**Project:** [`dibyadyuti-bits_aceest-fitness-devops`](https://sonarcloud.io/summary/overall?id=dibyadyuti-bits_aceest-fitness-devops&branch=main)
**Branch:** `main` · **Version:** 2.0.0 · **Commit analysed:** `ff4bcae` (merge of PR #12)
**Analysed:** 2026-11-24 03:25 IST (2026-11-23 21:55 UTC)
**Raw data:** [`sonarqube-report.json`](sonarqube-report.json), fetched from the SonarCloud Web API

The analysis runs on every push and pull request (GitHub Actions, `sonarqube-scan-action@v6`) and in
every Jenkins build (`pysonar`). `sonar.qualitygate.wait=true` in `sonar-project.properties` makes
both pipelines fail when the quality gate fails. Jenkins also archives
`reports/sonarcloud-quality-gate.json` and `reports/sonarcloud-measures.json` with each build.

## Quality gate: **Passed**

| Condition (on new code) | Threshold | Actual | Status |
|---|---|---|---|
| Reliability rating | A | A | OK |
| Security rating | A | A | OK |
| Maintainability rating | A | A | OK |
| Security hotspots reviewed | 100% | 100% | OK |

## Overall code

| Measure | Value |
|---|---|
| Lines of code | 474 |
| Bugs | 0 (Reliability **A**) |
| Vulnerabilities | 0 (Security **A**) |
| Security hotspots | 0 open |
| Code smells | 0 (Maintainability **A**) |
| Coverage | 99.6% (78 Pytest tests) |
| Duplicated lines | 0.0% |
| Open issues | 0 |

## Scope and notes

- Analysed: `aceest/`, `app.py`, `ACEest_Fitness.py`; tests in `tests/`. The Tkinter prototypes in
  `legacy/`, the Kubernetes files and the CI configuration are excluded (`sonar.exclusions`, PR #10).
  Before that fix SonarCloud graded about 3.3k lines including the prototypes (Security D,
  Reliability E, 14.5% duplication).
- One rule (CSRF protection, `aceest/__init__.py`) was reviewed and marked **Accepted**: the app is
  a JSON API with no cookie sessions or HTML forms, so there is no CSRF attack surface.
- Screenshots: `screenshots/assignment-2/17-20` (quality gate, overall before and after the scope fix).
