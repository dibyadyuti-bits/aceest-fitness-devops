"""ACEest Fitness & Gym Flask application package."""

import os
from pathlib import Path

from flask import Flask

VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def read_version():
    """Release version: APP_VERSION env var first, then the VERSION file."""
    env_version = os.environ.get("APP_VERSION", "").strip()
    if env_version:
        return env_version
    try:
        return VERSION_FILE.read_text().strip() or "unknown"
    except OSError:
        return "unknown"


def create_app(config=None):
    """Application factory. Tests pass their own config (e.g. a temp DB)."""
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("ACEEST_DB", "aceest_fitness.db"),
        APP_VERSION=read_version(),
        # Which side of a blue-green / canary / A/B / shadow deployment this pod is.
        APP_VARIANT=os.environ.get("APP_VARIANT", "default"),
    )
    if config:
        app.config.update(config)

    from . import db, routes
    db.init_app(app)
    app.register_blueprint(routes.bp)
    return app
