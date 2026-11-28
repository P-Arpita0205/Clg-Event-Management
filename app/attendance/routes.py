from io import BytesIO
import re
import secrets

import qrcode
from flask import abort, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user

from app.attendance import attendance
from app.certificates.routes import (
    issue_eligible_certificates_for_event,
    sync_ended_event_certificates,
)
from app.decorators import roles_required
from app.models import Attendance, Certificate, Event, EventRegistration, VolunteerApplication
from app.notifications.routes import notify


def coordinator_owns_event(event):
    return current_user.role_name == "admin" or event.coordinator_id == current_user.id


@attendance.route("/qr/<int:registration_id>")
@roles_required("student")
def qr(registration_id):
    registration = EventRegistration.get(registration_id)
    if not registration or registration.student_id != current_user.id:
        abort(403)
    payload = url_for("attendance.validate", token=registration.qr_token, _external=True)
    image = qrcode.make(payload)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png", download_name=f"event-{registration.event_id}-attendance.png")


@attendance.route("/qr/volunteer/<int:application_id>")
@roles_required("student")
def volunteer_qr(application_id):
    application = VolunteerApplication.get(application_id)
    if (
        not application
        or application.student_id != current_user.id
        or application.status != "approved"
    ):
        abort(403)
    if not application.qr_token:
        application.qr_token = secrets.token_urlsafe(32)
        application.save()
    payload = url_for("attendance.validate", token=application.qr_token, _external=True)
    image = qrcode.make(payload)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="image/png",
        download_name=f"event-{application.event_id}-volunteer-attendance.png",
    )


def _record_qr_attendance(token, expected_event_id=None):
    """Validate a participant or volunteer QR token or unique key and record QR attendance."""
    raw = (token or "").strip()
    if not raw:
        return {
            "valid": False,
            "duplicate": False,
            "message": "Invalid QR attendance code or unique key.",
            "student": None,
            "event": None,
            "record": None,
            "roles": [],
        }

    registration = None
    application = None
    key_match = re.fullmatch(r"([PV])-(\d+)-([A-F0-9]{6})", raw.upper())
    if key_match:
        prefix, rec_id_str, _ = key_match.groups()
        candidate_key = raw.upper()
        if prefix == "P":
            reg = EventRegistration.get(int(rec_id_str))
            if (
                reg
                and reg.status == "confirmed"
                and reg.attendance_key
                and secrets.compare_digest(reg.attendance_key, candidate_key)
            ):
                registration = reg
        else:
            app_rec = VolunteerApplication.get(int(rec_id_str))
            if (
                app_rec
                and app_rec.status == "approved"
                and app_rec.attendance_key
                and secrets.compare_digest(app_rec.attendance_key, candidate_key)
            ):
                application = app_rec
    else:
        normalized_token = raw.rstrip("/").split("/")[-1]
        if normalized_token:
            registration = EventRegistration.find_one(qr_token=normalized_token)
            if not registration:
                application = VolunteerApplication.find_one(
                    qr_token=normalized_token,
                    status="approved",
                )

    if not registration and not application:
        return {
            "valid": False,
            "duplicate": False,
            "message": "Invalid QR attendance code or unique key.",
            "student": None,
            "event": None,
            "record": None,
            "roles": [],
        }

    if registration:
        event = registration.event
        student_id = registration.student_id
        student = registration.student
        application = VolunteerApplication.find_one(
            event_id=event.id,
            student_id=student_id,
            status="approved",
        )
    else:
        event = application.event
        student_id = application.student_id
        student = application.student
        registration = EventRegistration.find_one(
            event_id=event.id,
            student_id=student_id,
            status="confirmed",
        )

    if not coordinator_owns_event(event):
        abort(403)

    if expected_event_id is not None and event.id != expected_event_id:
        return {
            "valid": False,
            "duplicate": False,
            "message": f"This QR code is for '{event.title}', not this event.",
            "student": student,
            "event": event,
            "record": None,
            "roles": [],
        }

    roles = []
    if registration and registration.status == "confirmed":
        roles.append("Participant")
    if application and application.status == "approved":
        roles.append("Volunteer")

    existing = Attendance.find_one(event_id=event.id, student_id=student_id)
    if existing:
        if existing.method == "qr":
            return {
                "valid": True,
                "duplicate": True,
                "message": "Attendance has already been recorded.",
                "student": student,
                "event": event,
                "record": existing,
                "roles": roles,
            }
        existing.method = "qr"
        if registration and not existing.registration_id:
            existing.registration_id = registration.id
        if application and not existing.volunteer_application_id:
            existing.volunteer_application_id = application.id
        existing.save()
        notify(
            student_id,
            "Attendance recorded",
            f"Your QR attendance for {event.title} was recorded.",
            url_for("student.dashboard"),
        )
        record = existing
    else:
        record = Attendance(
            event_id=event.id,
            student_id=student_id,
            registration_id=registration.id if registration else None,
            volunteer_application_id=application.id if application else None,
            method="qr",
        ).save()
        notify(
            student_id,
            "Attendance recorded",
            f"Your attendance for {event.title} was recorded.",
            url_for("student.dashboard"),
        )

    if event.has_ended:
        issue_eligible_certificates_for_event(
            event,
            issuer_id=current_user.id,
            student_id=student_id,
        )

    return {
        "valid": True,
        "duplicate": False,
        "message": "Attendance recorded successfully.",
        "student": student,
        "event": event,
        "record": record,
        "roles": roles,
    }


@attendance.route("/validate/<token>", methods=["GET", "POST"])
@roles_required("coordinator", "admin")
def validate(token):
    result = _record_qr_attendance(token)
    return render_template(
        "attendance/result.html",
        valid=result["valid"],
        duplicate=result["duplicate"],
        message=result["message"],
        student=result["student"],
        event=result["event"],
    )


@attendance.route("/event/<int:event_id>/scan", methods=["POST"])
@roles_required("coordinator", "admin")
def scan(event_id):
    event = Event.get(event_id)
    if not event:
        abort(404)
    if not coordinator_owns_event(event):
        abort(403)

    payload = request.get_json(silent=True) or {}
    qr_token = payload.get("qr_token") or request.form.get("qr_token") or ""
    result = _record_qr_attendance(qr_token, expected_event_id=event.id)

    student = result["student"]
    record = result["record"]
    issued_types = []
    if result["valid"] and student:
        issued_types = [
            cert.certificate_type
            for cert in Certificate.where(
                event_id=event.id,
                recipient_id=student.id,
                is_valid=True,
            )
        ]

    return jsonify(
        {
            "valid": result["valid"],
            "duplicate": result["duplicate"],
            "message": result["message"],
            "student_id": student.id if student else None,
            "student_name": student.full_name if student else None,
            "roles": result["roles"],
            "method": record.method if record else None,
            "checked_in_at": record.checked_in_at.strftime("%d %b, %I:%M %p") if record else None,
            "event_has_ended": event.has_ended,
            "issued_types": issued_types,
        }
    )


@attendance.route("/event/<int:event_id>", methods=["GET", "POST"])
@roles_required("coordinator", "admin")
def manage(event_id):
    event = Event.get(event_id)
    if not event:
        abort(404)
    if not coordinator_owns_event(event):
        abort(403)
    if request.method == "POST":
        qr_input = (request.form.get("qr_token") or "").strip()
        if qr_input:
            token = qr_input.rstrip("/").split("/")[-1]
            return redirect(url_for("attendance.validate", token=token))
        student_id = request.form.get("student_id", type=int)
        registration = EventRegistration.find_one(
            event_id=event.id,
            student_id=student_id,
            status="confirmed",
        )
        if not registration:
            return redirect(url_for("attendance.manage", event_id=event.id))
        existing = Attendance.find_one(event_id=event.id, student_id=student_id)
        if not existing:
            Attendance(
                event_id=event.id,
                student_id=student_id,
                registration_id=registration.id,
                method="manual",
            ).save()
            notify(
                student_id,
                "Attendance recorded",
                f"Your attendance for {event.title} was recorded manually.",
                url_for("student.dashboard"),
            )
    else:
        sync_ended_event_certificates(event_id=event.id)

    registrations = EventRegistration.where(event_id=event.id, status="confirmed")
    records = Attendance.where(event_id=event.id)
    participant_ids = {registration.student_id for registration in registrations}
    volunteer_ids = {
        app_rec.student_id
        for app_rec in VolunteerApplication.where(event_id=event.id, status="approved")
    }
    issued_certs = {
        (cert.recipient_id, cert.certificate_type)
        for cert in Certificate.where(event_id=event.id, is_valid=True)
    }
    return render_template(
        "attendance/manage.html",
        event=event,
        registrations=registrations,
        records=records,
        participant_ids=participant_ids,
        volunteer_ids=volunteer_ids,
        issued_certs=issued_certs,
    )


@attendance.route("/event/<int:event_id>/report")
@roles_required("coordinator", "admin")
def report(event_id):
    event = Event.get(event_id)
    if not event:
        abort(404)
    if not coordinator_owns_event(event):
        abort(403)
    records = sorted(
        Attendance.where(event_id=event.id),
        key=lambda r: r.checked_in_at,
    )
    return render_template("attendance/report.html", event=event, records=records)
