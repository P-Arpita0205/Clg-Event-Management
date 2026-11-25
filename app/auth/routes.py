from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.auth import auth
from app.forms import LoginForm, RegistrationForm
from app.models import Department, Role, User
from app.notifications.routes import notify


def dashboard_endpoint(role_name):
    return {
        "admin": "admin.dashboard",
        "coordinator": "coordinator.dashboard",
        "student": "student.dashboard",
    }.get(role_name)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(dashboard_endpoint(current_user.role_name)))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash(
                    "Your account is pending administrator approval or has been deactivated.",
                    "warning",
                )
                return render_template("auth/login.html", form=form)
            login_user(user)
            return redirect(request.args.get("next") or url_for(dashboard_endpoint(user.role_name)))
        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html", form=form)


@auth.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(dashboard_endpoint(current_user.role_name)))

    form = RegistrationForm()
    form.department_id.choices = [
        (department.id, department.name) for department in Department.query.order_by(Department.name)
    ]
    if form.validate_on_submit():
        student_role = Role.query.filter_by(name="student").first()
        if not student_role:
            flash("The system is not initialized. Please contact the administrator.", "danger")
            return render_template("auth/register.html", form=form)

        user = User(
            full_name=form.full_name.data.strip(),
            email=form.email.data.strip().lower(),
            student_id=form.student_id.data.strip(),
            phone=form.phone.data.strip() or None if form.phone.data else None,
            department_id=form.department_id.data,
            role=student_role,
            is_active=False,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        admins = User.query.join(Role).filter(
            Role.name == "admin",
            User.is_active.is_(True),
        ).all()
        for admin_user in admins:
            notify(
                admin_user.id,
                "New student sign-up request",
                f"{user.full_name} ({user.student_id}) requested account approval.",
                url_for("admin.students"),
            )

        db.session.commit()
        flash(
            "Your registration request has been sent to the administrator for approval.",
            "info",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.index"))
