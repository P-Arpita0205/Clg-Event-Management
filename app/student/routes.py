from datetime import date, datetime
import secrets

from flask import render_template
from flask_login import current_user

from app.decorators import roles_required
from app.firestore_db import batch_write
from app.models import (
    Attendance,
    Certificate,
    Event,
    EventRegistration,
    VolunteerApplication,
    VolunteerAssignment,
    VolunteerTask,
)
from app.student import student


def _ensure_volunteer_qr_tokens(applications):
    """Ensure approved volunteer applications have a qr_token for QR & key display."""
    updates = []
    for application in applications:
        if application.status == "approved" and not application.qr_token:
            application.qr_token = secrets.token_urlsafe(32)
            updates.append(
                ("update", VolunteerApplication.collection_name, application.id, {"qr_token": application.qr_token})
            )
    if updates:
        batch_write(updates)


@student.route("/")
@roles_required("student")
def dashboard():
    from app.certificates.routes import sync_ended_event_certificates

    sync_ended_event_certificates(student_id=current_user.id)
    all_user_regs = EventRegistration.where(student_id=current_user.id)
    registrations = sorted(
        [reg for reg in all_user_regs if reg.status == "confirmed"],
        key=lambda reg: reg.registered_at,
        reverse=True,
    )
    all_user_apps = VolunteerApplication.where(student_id=current_user.id)
    approved_volunteers = sorted(
        [app_rec for app_rec in all_user_apps if app_rec.status == "approved"],
        key=lambda app_rec: app_rec.created_at,
        reverse=True,
    )
    _ensure_volunteer_qr_tokens(approved_volunteers)

    registered_event_ids = {reg.event_id for reg in registrations}
    now_naive = datetime.now()
    pending_compulsory_events = sorted(
        [
            event
            for event in Event.where(status="published", registration_compulsory=True)
            if event.id not in registered_event_ids
            and event.registration_deadline is not None
            and event.registration_deadline >= now_naive
            and (
                event.department_id is None
                or (current_user.department_id and event.department_id == current_user.department_id)
            )
        ],
        key=lambda e: (e.event_date, e.start_time),
    )

    today = date.today()
    upcoming_events = sum(
        1 for reg in registrations if reg.event and reg.event.event_date >= today
    )

    assignment_ids = {
        assignment.id
        for assignment in VolunteerAssignment.all()
        if any(a.id == assignment.application_id for a in all_user_apps)
    }
    assigned_tasks = (
        sum(
            1
            for task in VolunteerTask.all()
            if task.assignment_id in assignment_ids and task.status != "completed"
        )
        if assignment_ids
        else 0
    )

    stats = {
        "registered_events": len(registrations),
        "upcoming_events": upcoming_events,
        "volunteer_applications": len(all_user_apps),
        "assigned_tasks": assigned_tasks,
        "available_certificates": Certificate.count(recipient_id=current_user.id, is_valid=True),
        "participation": Attendance.count(student_id=current_user.id),
    }
    return render_template(
        "dashboards/student.html",
        stats=stats,
        user=current_user,
        registrations=registrations,
        approved_volunteers=approved_volunteers,
        pending_compulsory_events=pending_compulsory_events,
    )


@student.route("/registrations")
@roles_required("student")
def registrations():
    registration_list = sorted(
        EventRegistration.where(student_id=current_user.id),
        key=lambda r: r.registered_at,
        reverse=True,
    )
    return render_template("student/registrations.html", registration_list=registration_list)


@student.route("/volunteer-applications")
@roles_required("student")
def volunteer_applications():
    application_list = sorted(
        VolunteerApplication.where(student_id=current_user.id),
        key=lambda a: a.created_at,
        reverse=True,
    )
    _ensure_volunteer_qr_tokens(application_list)
    return render_template("student/applications.html", application_list=application_list)
