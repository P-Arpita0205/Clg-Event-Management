from flask import Blueprint


events = Blueprint("events", __name__, url_prefix="/events")

from app.events import routes  # noqa: E402,F401
