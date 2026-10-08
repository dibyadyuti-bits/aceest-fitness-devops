"""Entry point for ACEest Fitness & Gym.

Development:  python app.py
Production:   gunicorn --bind 0.0.0.0:5000 app:app
"""

import os

from aceest import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
