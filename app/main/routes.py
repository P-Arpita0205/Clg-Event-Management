from flask import render_template
from flask_login import current_user

from app.main import main


@main.route("/")
def index():
    if current_user.is_authenticated:
        destination = {
            "admin": "admin.dashboard",
            "coordinator": "coordinator.dashboard",
            "student": "student.dashboard",
        }.get(current_user.role_name)
        if destination:
            return render_template("redirect_dashboard.html", destination=destination)
    return render_template("home.html")
