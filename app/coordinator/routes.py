from flask import render_template
from flask_login import current_user

from app import db
from app.coordinator import coordinator
from app.decorators import roles_required
from app.models import (
    Attendance,
    Certificate,
    Event,
    EventRegistration,
    VolunteerApplication,
    VolunteerTask,
)


@coordinator.route("/")
@roles_required("coordinator")
def dashboard():
    managed_events = Event.query.filter_by(coordinator_id=current_user.id).order_by(Event.created_at.desc())
    all_managed = managed_events.all()
    event_ids = [event.id for event in all_managed]
    stats = {
        "managed_events": len(all_managed),
        "registrations": EventRegistration.query.filter(
            EventRegistration.event_id.in_(event_ids)
        ).count() if event_ids else 0,
        "applications": VolunteerApplication.query.join(Event).filter(
            Event.coordinator_id == current_user.id
        ).count(),
        "pending_approvals": VolunteerApplication.query.join(Event).filter(
            Event.coordinator_id == current_user.id,
            VolunteerApplication.status == "pending",
        ).count(),
        "completed_tasks": VolunteerTask.query.join(Event).filter(
            Event.coordinator_id == current_user.id,
            VolunteerTask.status == "completed",
        ).count() if event_ids else 0,
        "attendance": Attendance.query.filter(
            Attendance.event_id.in_(event_ids)
        ).count() if event_ids else 0,
    }
    return render_template("dashboards/coordinator.html", stats=stats, recent_events=all_managed[:5])


@coordinator.route("/events")
@roles_required("coordinator")
def events():
    event_list = Event.query.filter_by(coordinator_id=current_user.id).order_by(
        Event.created_at.desc()
    ).all()
    return render_template("coordinator/events.html", event_list=event_list)


@coordinator.route("/applications")
@roles_required("coordinator")
def applications():
    from app.certificates.routes import sync_ended_event_certificates

    sync_ended_event_certificates(coordinator_id=current_user.id)
    application_list = (
        VolunteerApplication.query.join(Event)
        .filter(Event.coordinator_id == current_user.id)
        .order_by(VolunteerApplication.created_at.desc())
        .all()
    )
    event_ids = {application.event_id for application in application_list}
    qr_attended_keys = (
        {
            (row[0], row[1])
            for row in db.session.query(Attendance.event_id, Attendance.student_id)
            .filter(
                Attendance.event_id.in_(event_ids),
                Attendance.method == "qr",
            )
            .all()
        }
        if event_ids
        else set()
    )
    issued_volunteer_cert_keys = (
        {
            (row[0], row[1])
            for row in db.session.query(Certificate.event_id, Certificate.recipient_id)
            .filter(
                Certificate.event_id.in_(event_ids),
                Certificate.certificate_type == "volunteer",
                Certificate.is_valid.is_(True),
            )
            .all()
        }
        if event_ids
        else set()
    )
    return render_template(
        "coordinator/applications.html",
        application_list=application_list,
        qr_attended_keys=qr_attended_keys,
        issued_volunteer_cert_keys=issued_volunteer_cert_keys,
    )
