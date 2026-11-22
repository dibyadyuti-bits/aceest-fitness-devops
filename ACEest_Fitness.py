"""ACEest Fitness & Gym - main application module named in the assignment brief.

Development:  python ACEest_Fitness.py
Production:   gunicorn --bind 0.0.0.0:5000 ACEest_Fitness:app
"""

import os

from app import app

__all__ = ["app"]

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
