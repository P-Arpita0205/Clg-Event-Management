from flask import Blueprint


assistance = Blueprint("assistance", __name__, url_prefix="/assistance")

from app.assistance import routes  # noqa: E402,F401
