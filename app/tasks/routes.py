from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app import db
from app.decorators import roles_required
from app.models import Event, VolunteerApplication, VolunteerAssignment, VolunteerTask
from app.notifications.routes import notify
from app.tasks import tasks


def parse_task_deadline(value, date_value=None, time_value=None):
    if value:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    if date_value:
        combined = f"{date_value}T{time_value or '23:59'}"
        return datetime.strptime(combined, "%Y-%m-%dT%H:%M")
    return None


@tasks.route("/event/<int:event_id>", methods=["GET", "POST"])
@roles_required("coordinator", "admin")
def manage(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    if current_user.role_name != "admin" and event.coordinator_id != current_user.id:
        abort(403)

    if request.method == "POST":
        assignment_id = request.form.get("assignment_id", type=int)
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        deadline = parse_task_deadline(
            request.form.get("deadline", "").strip(),
            request.form.get("deadline_date", "").strip(),
            request.form.get("deadline_time", "").strip(),
        )
        assignment = db.session.get(VolunteerAssignment, assignment_id)
        if not assignment or assignment.application.event_id != event.id:
            flash("Choose a valid approved volunteer.", "danger")
        elif not title:
            flash("Task title is required.", "danger")
        else:
            task = VolunteerTask(
                event_id=event.id,
                assignment_id=assignment.id,
                title=title,
                description=description or None,
                deadline=deadline,
                status="assigned",
            )
            db.session.add(task)
            notify(
                assignment.application.student_id,
                "New task assigned",
                f"You were assigned '{title}' for {event.title}.",
                url_for("tasks.student_tasks"),
            )
            db.session.commit()
            flash("Task assigned and notification sent.", "success")

    assignments = (
        VolunteerAssignment.query.join(VolunteerAssignment.application)
        .filter(
            VolunteerAssignment.application.has(event_id=event.id),
            VolunteerAssignment.application.has(status="approved"),
        )
        .all()
    )
    task_list = VolunteerTask.query.filter_by(event_id=event.id).order_by(
        VolunteerTask.created_at.desc()
    ).all()
    return render_template(
        "tasks/manage.html",
        event=event,
        assignments=assignments,
        task_list=task_list,
    )


@tasks.route("/<int:task_id>/deadline", methods=["POST"])
@roles_required("coordinator", "admin")
def update_deadline(task_id):
    task = db.session.get(VolunteerTask, task_id)
    if not task:
        abort(404)
    if current_user.role_name != "admin" and task.event.coordinator_id != current_user.id:
        abort(403)
    try:
        task.deadline = parse_task_deadline(
            request.form.get("deadline", "").strip(),
            request.form.get("deadline_date", "").strip(),
            request.form.get("deadline_time", "").strip(),
        )
    except ValueError:
        flash("Please provide a valid deadline date and time.", "danger")
        return redirect(url_for("tasks.manage", event_id=task.event_id))

    db.session.commit()
    flash("Task deadline updated.", "success")
    return redirect(url_for("tasks.manage", event_id=task.event_id))


@tasks.route("/student")
@roles_required("student")
def student_tasks():
    task_list = (
        VolunteerTask.query.join(VolunteerAssignment)
        .join(VolunteerApplication, VolunteerAssignment.application_id == VolunteerApplication.id)
        .filter(VolunteerApplication.student_id == current_user.id)
        .order_by(VolunteerTask.deadline.asc(), VolunteerTask.created_at.desc())
        .all()
    )
    return render_template("tasks/student.html", task_list=task_list)


@tasks.route("/<int:task_id>/status", methods=["POST"])
@roles_required("student")
def update_status(task_id):
    task = db.session.get(VolunteerTask, task_id)
    if not task:
        abort(404)
    assignment = db.session.get(VolunteerAssignment, task.assignment_id)
    application = (
        db.session.get(VolunteerApplication, assignment.application_id)
        if assignment
        else None
    )
    if not application or application.student_id != current_user.id:
        abort(403)
    status = request.form.get("status")
    if status not in ("assigned", "in_progress", "completed"):
        abort(400)
    task.status = status
    db.session.commit()
    flash("Task status updated.", "success")
    return redirect(url_for("tasks.student_tasks"))
