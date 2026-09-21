"""
Entry point for running the app locally.
Usage: python run.py  (or, in production: gunicorn run:app)
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
