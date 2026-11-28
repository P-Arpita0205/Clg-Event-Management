from collections import Counter

from flask import flash, redirect, render_template, url_for

from app.admin import admin
from app.decorators import roles_required
from app.models import Department, Event, EventCategory, Role, User, VolunteerApplication
from app.notifications.routes import notify


@admin.route("/")
@roles_required("admin")
def dashboard():
    departments = Department.all()
    users = User.all()
    events = Event.all()
    categories = EventCategory.all()

    student_role = Role.find_one(name="student")
    student_role_id = student_role.id if student_role else None

    dept_user_counts = Counter(
        u.department_id
        for u in users
        if student_role_id is not None and u.role_id == student_role_id and u.department_id is not None
    )
    category_event_counts = Counter(e.category_id for e in events if e.category_id is not None)
    status_counts = Counter(e.status for e in events if e.status)

    stats = {
        "students": sum(1 for u in users if u.role_id == student_role_id),
        "events": len(events),
        "upcoming_events": sum(1 for e in events if e.status == "published"),
        "volunteers": VolunteerApplication.count(status="approved"),
        "pending_approvals": sum(1 for e in events if e.status == "draft"),
        "departments": len(departments),
    }

    return render_template(
        "dashboards/admin.html",
        stats=stats,
        department_labels=[dept.name for dept in departments],
        department_counts=[dept_user_counts.get(dept.id, 0) for dept in departments],
        category_labels=[cat.name for cat in categories],
        category_counts=[category_event_counts.get(cat.id, 0) for cat in categories],
        status_labels=[status.title() for status in status_counts.keys()],
        status_counts=list(status_counts.values()),
    )


@admin.route("/events")
@roles_required("admin")
def events():
    event_list = sorted(Event.all(), key=lambda e: e.created_at, reverse=True)
    return render_template("admin/events.html", event_list=event_list)


@admin.route("/students")
@roles_required("admin")
def students():
    student_role = Role.find_one(name="student")
    all_students = (
        sorted(
            User.where(role_id=student_role.id),
            key=lambda u: u.created_at,
            reverse=True,
        )
        if student_role
        else []
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
    student_user = User.get(user_id)
    if not student_user or student_user.role_name != "student":
        flash("Student account not found.", "warning")
        return redirect(url_for("admin.students"))

    student_user.is_active = True
    student_user.save()
    notify(
        student_user.id,
        "Account approved",
        "Your student account has been approved. Welcome to Campus Connect.",
        url_for("student.dashboard"),
    )
    flash(f"Approved sign-up request for {student_user.full_name}.", "success")
    return redirect(url_for("admin.students"))


@admin.route("/students/<int:user_id>/reject", methods=["POST"])
@roles_required("admin")
def reject_student(user_id):
    student_user = User.get(user_id)
    if not student_user or student_user.role_name != "student" or student_user.is_active:
        flash("Pending student request not found.", "warning")
        return redirect(url_for("admin.students"))

    full_name = student_user.full_name
    student_user.delete()
    flash(f"Rejected and removed sign-up request for {full_name}.", "warning")
    return redirect(url_for("admin.students"))


@admin.route("/students/<int:user_id>/toggle", methods=["POST"])
@roles_required("admin")
def toggle_student(user_id):
    student_user = User.get(user_id)
    if not student_user or student_user.role_name != "student":
        flash("Student account not found.", "warning")
        return redirect(url_for("admin.students"))

    student_user.is_active = not student_user.is_active
    student_user.save()
    status_label = "activated" if student_user.is_active else "deactivated"
    flash(f"Student account {status_label}.", "success")
    return redirect(url_for("admin.students"))
