from flask import render_template
from flask_login import current_user

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
    all_managed = sorted(
        Event.where(coordinator_id=current_user.id),
        key=lambda e: e.created_at,
        reverse=True,
    )
    event_ids = {event.id for event in all_managed}

    registrations_count = (
        sum(1 for r in EventRegistration.all() if r.event_id in event_ids)
        if event_ids
        else 0
    )
    apps = (
        [a for a in VolunteerApplication.all() if a.event_id in event_ids]
        if event_ids
        else []
    )
    completed_tasks = (
        sum(1 for t in VolunteerTask.where(status="completed") if t.event_id in event_ids)
        if event_ids
        else 0
    )
    attendance_count = (
        sum(1 for a in Attendance.all() if a.event_id in event_ids)
        if event_ids
        else 0
    )

    stats = {
        "managed_events": len(all_managed),
        "registrations": registrations_count,
        "applications": len(apps),
        "pending_approvals": sum(1 for a in apps if a.status == "pending"),
        "completed_tasks": completed_tasks,
        "attendance": attendance_count,
    }
    return render_template("dashboards/coordinator.html", stats=stats, recent_events=all_managed[:5])


@coordinator.route("/events")
@roles_required("coordinator")
def events():
    event_list = sorted(
        Event.where(coordinator_id=current_user.id),
        key=lambda e: e.created_at,
        reverse=True,
    )
    return render_template("coordinator/events.html", event_list=event_list)


@coordinator.route("/applications")
@roles_required("coordinator")
def applications():
    from app.certificates.routes import sync_ended_event_certificates

    sync_ended_event_certificates(coordinator_id=current_user.id)
    managed_events = Event.where(coordinator_id=current_user.id)
    event_ids = {event.id for event in managed_events}

    application_list = sorted(
        [a for a in VolunteerApplication.all() if a.event_id in event_ids],
        key=lambda a: a.created_at,
        reverse=True,
    )
    qr_attended_keys = (
        {
            (record.event_id, record.student_id)
            for record in Attendance.where(method="qr")
            if record.event_id in event_ids
        }
        if event_ids
        else set()
    )
    issued_volunteer_cert_keys = (
        {
            (cert.event_id, cert.recipient_id)
            for cert in Certificate.where(certificate_type="volunteer", is_valid=True)
            if cert.event_id in event_ids
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
