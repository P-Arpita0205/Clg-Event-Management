from flask import flash, redirect, render_template, url_for

from app.admin import admin
from app.decorators import roles_required
from app import db
from app.models import Attendance, Department, Event, EventCategory, Role, User, VolunteerApplication
from app.notifications.routes import notify


@admin.route("/")
@roles_required("admin")
def dashboard():
    department_rows = (
        db.session.query(Department.name, db.func.count(User.id))
        .outerjoin(User, User.department_id == Department.id)
        .group_by(Department.id, Department.name)
        .all()
    )
    stats = {
        "students": User.query.join(Role).filter(Role.name == "student").count(),
        "events": Event.query.count(),
        "upcoming_events": Event.query.filter(Event.status == "published").count(),
        "volunteers": VolunteerApplication.query.filter_by(status="approved").count(),
        "pending_approvals": Event.query.filter_by(status="draft").count(),
        "departments": Department.query.count(),
    }
    category_rows = (
        db.session.query(EventCategory.name, db.func.count(Event.id))
        .outerjoin(Event, Event.category_id == EventCategory.id)
        .group_by(EventCategory.id, EventCategory.name)
        .all()
    )
    status_rows = (
        db.session.query(Event.status, db.func.count(Event.id))
        .group_by(Event.status)
        .all()
    )
    return render_template(
        "dashboards/admin.html",
        stats=stats,
        department_labels=[row[0] for row in department_rows],
        department_counts=[row[1] for row in department_rows],
        category_labels=[row[0] for row in category_rows],
        category_counts=[row[1] for row in category_rows],
        status_labels=[row[0].title() for row in status_rows],
        status_counts=[row[1] for row in status_rows],
    )


@admin.route("/events")
@roles_required("admin")
def events():
    event_list = Event.query.order_by(Event.created_at.desc()).all()
    return render_template("admin/events.html", event_list=event_list)


@admin.route("/students")
@roles_required("admin")
def students():
    all_students = (
        User.query.join(Role)
        .filter(Role.name == "student")
        .order_by(User.created_at.desc())
        .all()
    )
    pending_students = [u for u in all_students if not u.is_active]
    active_students = [u for u in all_students if u.is_active]
    return render_template(
        "admin/students.html",
        pending_students=pending_students,
        student_list=active_students,
    )


@admin.route("/students/<int:user_id>/approve", methods=["POST"])
@roles_required("admin")
def approve_student(user_id):
    student_user = db.session.get(User, user_id)
    if not student_user or student_user.role_name != "student":
        flash("Student account not found.", "warning")
        return redirect(url_for("admin.students"))

    student_user.is_active = True
    notify(
        student_user.id,
        "Account approved",
        "Your student account has been approved. Welcome to Campus Connect.",
        url_for("student.dashboard"),
    )
    db.session.commit()
    flash(f"Approved sign-up request for {student_user.full_name}.", "success")
    return redirect(url_for("admin.students"))


@admin.route("/students/<int:user_id>/reject", methods=["POST"])
@roles_required("admin")
def reject_student(user_id):
    student_user = db.session.get(User, user_id)
    if not student_user or student_user.role_name != "student" or student_user.is_active:
        flash("Pending student request not found.", "warning")
        return redirect(url_for("admin.students"))

    full_name = student_user.full_name
    db.session.delete(student_user)
    db.session.commit()
    flash(f"Rejected and removed sign-up request for {full_name}.", "warning")
    return redirect(url_for("admin.students"))


@admin.route("/students/<int:user_id>/toggle", methods=["POST"])
@roles_required("admin")
def toggle_student(user_id):
    student_user = db.session.get(User, user_id)
    if not student_user or student_user.role_name != "student":
        flash("Student account not found.", "warning")
        return redirect(url_for("admin.students"))

    student_user.is_active = not student_user.is_active
    db.session.commit()
    status_label = "activated" if student_user.is_active else "deactivated"
    flash(f"Student account {status_label}.", "success")
    return redirect(url_for("admin.students"))
