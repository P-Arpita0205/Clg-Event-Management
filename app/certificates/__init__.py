from flask import Blueprint


certificates = Blueprint("certificates", __name__, url_prefix="/certificates")

from app.certificates import routes  # noqa: E402,F401
