from datetime import date, datetime
import secrets

from flask import render_template
from flask_login import current_user

from app import db
from app.decorators import roles_required
from app.student import student
from app.models import (
    Attendance,
    Event,
    EventRegistration,
    VolunteerApplication,
    VolunteerAssignment,
    VolunteerTask,
    Certificate,
)


def _ensure_volunteer_qr_tokens(applications):
    """Ensure approved volunteer applications have a qr_token for QR & key display."""
    changed = False
    for application in applications:
        if application.status == "approved" and not application.qr_token:
            application.qr_token = secrets.token_urlsafe(32)
            changed = True
    if changed:
        db.session.commit()


@student.route("/")
@roles_required("student")
def dashboard():
    from app.certificates.routes import sync_ended_event_certificates

    sync_ended_event_certificates(student_id=current_user.id)
    registrations = (
        EventRegistration.query.filter_by(
            student_id=current_user.id,
            status="confirmed",
        )
        .order_by(EventRegistration.registered_at.desc())
        .all()
    )
    approved_volunteers = (
        VolunteerApplication.query.filter_by(
            student_id=current_user.id,
            status="approved",
        )
        .order_by(VolunteerApplication.created_at.desc())
        .all()
    )
    _ensure_volunteer_qr_tokens(approved_volunteers)

    registered_event_ids = {reg.event_id for reg in registrations}
    compulsory_query = Event.query.filter(
        Event.status == "published",
        Event.registration_compulsory.is_(True),
        Event.registration_deadline >= datetime.now(),
    )
    if current_user.department_id:
        compulsory_query = compulsory_query.filter(
            db.or_(
                Event.department_id.is_(None),
                Event.department_id == current_user.department_id,
            )
        )
    else:
        compulsory_query = compulsory_query.filter(Event.department_id.is_(None))
    if registered_event_ids:
        compulsory_query = compulsory_query.filter(~Event.id.in_(registered_event_ids))
    pending_compulsory_events = compulsory_query.order_by(
        Event.event_date.asc(),
        Event.start_time.asc(),
    ).all()

    registered_events = len(registrations)
    applications = VolunteerApplication.query.filter_by(student_id=current_user.id).count()
    upcoming_events = (
        EventRegistration.query.join(Event)
        .filter(
            EventRegistration.student_id == current_user.id,
            EventRegistration.status == "confirmed",
            Event.event_date >= date.today(),
        )
        .count()
    )
    stats = {
        "registered_events": registered_events,
        "upcoming_events": upcoming_events,
        "volunteer_applications": applications,
        "assigned_tasks": VolunteerTask.query.join(VolunteerAssignment).join(VolunteerApplication).filter(
            VolunteerApplication.student_id == current_user.id,
            VolunteerTask.status != "completed",
        ).count(),
        "available_certificates": Certificate.query.filter_by(
            recipient_id=current_user.id,
            is_valid=True,
        ).count(),
        "participation": Attendance.query.filter_by(student_id=current_user.id).count(),
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
    registration_list = (
        EventRegistration.query.filter_by(student_id=current_user.id)
        .order_by(EventRegistration.registered_at.desc())
        .all()
    )
    return render_template("student/registrations.html", registration_list=registration_list)


@student.route("/volunteer-applications")
@roles_required("student")
def volunteer_applications():
    application_list = (
        VolunteerApplication.query.filter_by(student_id=current_user.id)
        .order_by(VolunteerApplication.created_at.desc())
        .all()
    )
    _ensure_volunteer_qr_tokens(application_list)
    return render_template("student/applications.html", application_list=application_list)
