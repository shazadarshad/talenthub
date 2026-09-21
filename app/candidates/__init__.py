from flask import Blueprint

candidates_bp = Blueprint("candidates", __name__)

from app.candidates import routes  # noqa: E402,F401
