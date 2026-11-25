from flask import Blueprint


feedback = Blueprint("feedback", __name__, url_prefix="/feedback")

from app.feedback import routes  # noqa: E402,F401
