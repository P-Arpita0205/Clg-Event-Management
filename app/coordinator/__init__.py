from flask import Blueprint


coordinator = Blueprint("coordinator", __name__, url_prefix="/coordinator")

from app.coordinator import routes  # noqa: E402,F401
