from flask import Blueprint


advanced = Blueprint("advanced", __name__)

from app.advanced import routes  # noqa: E402,F401
