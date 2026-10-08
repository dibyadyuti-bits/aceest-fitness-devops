# syntax=docker/dockerfile:1
# Multi-stage build:
#   base    - slim Python + runtime dependencies only (shared layer)
#   test    - base + pytest/flake8 + tests; CI runs the suite in here
#   runtime - base + app code only, runs as a non-root user (default target)

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
# Dependencies first so this layer is cached until requirements.txt changes
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM base AS test
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY . .
CMD ["pytest", "--cov=aceest", "--cov-report=term-missing"]

FROM base AS runtime
RUN useradd --create-home --uid 1000 aceest \
    && mkdir /data && chown aceest:aceest /data
COPY aceest/ aceest/
COPY app.py .
ENV ACEEST_DB=/data/aceest_fitness.db
USER aceest
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')" || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
