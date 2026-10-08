"""ACEest Fitness & Gym Flask application package."""

import os

from flask import Flask


def create_app(config=None):
    """Application factory. Tests pass their own config (e.g. a temp DB)."""
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("ACEEST_DB", "aceest_fitness.db"),
    )
    if config:
        app.config.update(config)

    from . import db, routes
    db.init_app(app)
    app.register_blueprint(routes.bp)
    return app
