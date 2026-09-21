from flask import Blueprint

employer_bp = Blueprint("employer", __name__)

from app.employer import routes  # noqa: E402,F401
