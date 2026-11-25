import secrets
from datetime import datetime, timezone
from pathlib import Path

import qrcode
from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app import db
from app.certificates import certificates
from app.decorators import roles_required
from app.models import (
    Attendance,
    Certificate,
    Event,
    EventRegistration,
    VolunteerApplication,
)
from app.notifications.routes import notify


def certificate_filename(certificate_id):
    return f"{certificate_id}.pdf"


def make_certificate_pdf(certificate):
    folder = Path(current_app.config["UPLOAD_FOLDER"]) / "certificates"
    folder.mkdir(parents=True, exist_ok=True)
    filename = certificate_filename(certificate.certificate_id)
    path = folder / filename

    page = canvas.Canvas(str(path), pagesize=landscape(A4))
    width, height = landscape(A4)
    page.setFillColor(HexColor("#f8fbff"))
    page.rect(0, 0, width, height, fill=1, stroke=0)
    page.setStrokeColor(HexColor("#155eef"))
    page.setLineWidth(5)
    page.rect(24, 24, width - 48, height - 48, fill=0, stroke=1)
    page.setStrokeColor(HexColor("#087f8c"))
    page.setLineWidth(1)
    page.rect(34, 34, width - 68, height - 68, fill=0, stroke=1)

    page.setFillColor(HexColor("#0b1f3a"))
    page.setFont("Helvetica-Bold", 24)
    page.drawCentredString(width / 2, height - 100, "CAMPUS CONNECT")
    page.setFont("Helvetica-Bold", 13)
    page.setFillColor(HexColor("#087f8c"))
    page.drawCentredString(width / 2, height - 128, "COLLEGE EVENT & VOLUNTEER MANAGEMENT")

    page.setFillColor(HexColor("#667085"))
    page.setFont("Helvetica", 12)
    page.drawCentredString(width / 2, height - 190, "This is to certify that")
    page.setFillColor(HexColor("#0b1f3a"))
    page.setFont("Helvetica-Bold", 28)
    page.drawCentredString(width / 2, height - 230, certificate.recipient.full_name)

    description = (
        f"has successfully participated in {certificate.event.title}"
        if certificate.certificate_type == "participation"
        else f"has contributed as a volunteer for {certificate.event.title}"
        if certificate.certificate_type == "volunteer"
        else f"has provided event coordination for {certificate.event.title}"
    )
    page.setFillColor(HexColor("#344054"))
    page.setFont("Helvetica", 14)
    page.drawCentredString(width / 2, height - 268, description)
    page.setFont("Helvetica-Bold", 12)
    page.drawCentredString(
        width / 2,
        height - 300,
        f"Event date: {certificate.event.event_date.strftime('%d %B %Y')}",
    )

    verification_url = url_for(
        "certificates.verify",
        certificate_id=certificate.certificate_id,
        _external=True,
    )
    qr = qrcode.make(verification_url)
    qr_path = folder / f"{certificate.certificate_id}-verify.png"
    qr.save(qr_path)
    page.drawImage(str(qr_path), 70, 55, width=85, height=85)
    page.setFont("Helvetica", 9)
    page.drawString(70, 42, f"Certificate ID: {certificate.certificate_id}")

    page.setStrokeColor(HexColor("#98a2b3"))
    page.line(width - 260, 85, width - 75, 85)
    page.setFont("Helvetica-Bold", 11)
    page.drawCentredString(width - 167, 68, "Authorized Signature")
    page.setFont("Helvetica", 9)
    page.drawCentredString(
        width - 167,
        52,
        f"Issued: {certificate.issue_date.strftime('%d %B %Y')}",
    )
    page.save()
    return str(path)


def has_qr_attendance(event_id, student_id):
    """Return True if the student has a QR-scanned attendance record for the event."""
    return (
        Attendance.query.filter_by(
            event_id=event_id,
            student_id=student_id,
            method="qr",
        ).first()
        is not None
    )


def _issue_certificate_record(event, student_id, certificate_type, issuer_id):
    """Create a certificate PDF record and notify the recipient if not already issued."""
    existing = Certificate.query.filter_by(
        recipient_id=student_id,
        event_id=event.id,
        certificate_type=certificate_type,
    ).first()
    if existing:
        return None

    prefix = (
        "CPC"
        if certificate_type == "participation"
        else "CVC"
        if certificate_type == "volunteer"
        else "CCC"
    )
    certificate = Certificate(
        certificate_id=f"{prefix}-{event.id}-{student_id}-{secrets.token_hex(4).upper()}",
        recipient_id=student_id,
        event_id=event.id,
        certificate_type=certificate_type,
        issued_by=issuer_id,
    )
    db.session.add(certificate)
    db.session.flush()
    certificate.pdf_path = make_certificate_pdf(certificate)
    label = (
        "participation"
        if certificate_type == "participation"
        else "volunteer"
        if certificate_type == "volunteer"
        else "event coordination"
    )
    notify(
        student_id,
        "Certificate available",
        f"Your {label} certificate for {event.title} is ready.",
        url_for("certificates.history"),
    )
    return certificate


def issue_eligible_certificates_for_event(event, issuer_id=None, student_id=None):
    """Issue participation/volunteer certificates to QR-checked-in students after event end."""
    if not event or not event.has_ended:
        return 0

    effective_issuer_id = issuer_id or event.coordinator_id
    attendance_query = Attendance.query.filter_by(event_id=event.id, method="qr")
    if student_id is not None:
        attendance_query = attendance_query.filter_by(student_id=student_id)
    attended_ids = {record.student_id for record in attendance_query.all()}
    if not attended_ids:
        return 0

    participant_ids = {
        row[0]
        for row in db.session.query(EventRegistration.student_id)
        .filter(
            EventRegistration.event_id == event.id,
            EventRegistration.status == "confirmed",
            EventRegistration.student_id.in_(attended_ids),
        )
        .all()
    }
    volunteer_ids = {
        row[0]
        for row in db.session.query(VolunteerApplication.student_id)
        .filter(
            VolunteerApplication.event_id == event.id,
            VolunteerApplication.status == "approved",
            VolunteerApplication.student_id.in_(attended_ids),
        )
        .all()
    }

    created = 0
    for sid in attended_ids:
        if sid in participant_ids and _issue_certificate_record(
            event, sid, "participation", effective_issuer_id
        ):
            created += 1
        if sid in volunteer_ids and _issue_certificate_record(
            event, sid, "volunteer", effective_issuer_id
        ):
            created += 1

    if created:
        db.session.commit()
    return created


def sync_ended_event_certificates(student_id=None, coordinator_id=None, event_id=None):
    """Ensure all ended events have issued certificates for QR-checked-in attendees."""
    query = Event.query.filter(Event.status.in_(("published", "completed")))
    if event_id is not None:
        query = query.filter(Event.id == event_id)
    elif coordinator_id is not None:
        query = query.filter(Event.coordinator_id == coordinator_id)
    elif student_id is not None:
        query = (
            query.join(Attendance, Attendance.event_id == Event.id)
            .filter(Attendance.student_id == student_id, Attendance.method == "qr")
            .distinct()
        )
    else:
        query = (
            query.join(Attendance, Attendance.event_id == Event.id)
            .filter(Attendance.method == "qr")
            .distinct()
        )

    total_issued = 0
    for event in query.all():
        if event.has_ended:
            total_issued += issue_eligible_certificates_for_event(event, student_id=student_id)
    return total_issued


@certificates.route("/issue/participant/<int:event_id>/<int:student_id>", methods=["POST"])
@roles_required("coordinator", "admin")
def issue_participant(event_id, student_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    if current_user.role_name != "admin" and event.coordinator_id != current_user.id:
        abort(403)
    if not event.has_ended:
        flash("Certificates can only be issued after the event has ended.", "warning")
        return redirect(request.referrer or url_for("certificates.history"))
    registration = EventRegistration.query.filter_by(
        event_id=event_id,
        student_id=student_id,
        status="confirmed",
    ).first()
    if not registration:
        flash("Participation certificate can only be issued to confirmed event participants.", "danger")
        return redirect(request.referrer or url_for("certificates.history"))
    if not has_qr_attendance(event_id, student_id):
        flash("QR code attendance must be scanned before issuing a participation certificate.", "danger")
        return redirect(request.referrer or url_for("certificates.history"))
    existing = Certificate.query.filter_by(
        recipient_id=student_id,
        event_id=event_id,
        certificate_type="participation",
    ).first()
    if existing:
        flash("Participation certificate was already issued.", "info")
        return redirect(url_for("certificates.history"))

    _issue_certificate_record(event, student_id, "participation", current_user.id)
    db.session.commit()
    flash("Participation certificate issued.", "success")
    return redirect(url_for("certificates.history"))


@certificates.route("/issue/volunteer/<int:event_id>/<int:student_id>", methods=["POST"])
@roles_required("coordinator", "admin")
def issue_volunteer(event_id, student_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    if current_user.role_name != "admin" and event.coordinator_id != current_user.id:
        abort(403)
    if not event.has_ended:
        flash("Certificates can only be issued after the event has ended.", "warning")
        return redirect(request.referrer or url_for("certificates.history"))
    application = VolunteerApplication.query.filter_by(
        event_id=event_id,
        student_id=student_id,
        status="approved",
    ).first()
    if not application:
        flash("Volunteer certificate can only be issued to approved volunteers.", "danger")
        return redirect(request.referrer or url_for("certificates.history"))
    if not has_qr_attendance(event_id, student_id):
        flash("QR code attendance must be scanned before issuing a volunteer certificate.", "danger")
        return redirect(request.referrer or url_for("certificates.history"))
    existing = Certificate.query.filter_by(
        recipient_id=student_id,
        event_id=event_id,
        certificate_type="volunteer",
    ).first()
    if existing:
        flash("Volunteer certificate was already issued.", "info")
        return redirect(url_for("certificates.history"))

    _issue_certificate_record(event, student_id, "volunteer", current_user.id)
    db.session.commit()
    flash("Volunteer certificate issued.", "success")
    return redirect(url_for("certificates.history"))


@certificates.route("/issue/event/<int:event_id>", methods=["POST"])
@roles_required("coordinator", "admin")
def issue_event(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    if current_user.role_name != "admin" and event.coordinator_id != current_user.id:
        abort(403)
    if not event.has_ended:
        flash("Certificates can only be issued after the event has ended.", "warning")
        return redirect(request.referrer or url_for("certificates.history"))

    issued = issue_eligible_certificates_for_event(event, issuer_id=current_user.id)
    if issued > 0:
        flash(f"Issued {issued} certificate(s) to QR-verified attendees.", "success")
    else:
        flash(
            "No new certificates to issue. Only QR-checked-in participants and volunteers are eligible.",
            "info",
        )
    return redirect(request.referrer or url_for("certificates.history"))


@certificates.route("/issue/coordinator/<int:event_id>", methods=["POST"])
@roles_required("admin")
def issue_coordinator(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    existing = Certificate.query.filter_by(
        recipient_id=event.coordinator_id,
        event_id=event_id,
        certificate_type="coordination",
    ).first()
    if existing:
        flash("Coordinator certificate was already issued.", "info")
        return redirect(url_for("certificates.history"))

    certificate = Certificate(
        certificate_id=f"CCC-{event_id}-{event.coordinator_id}-{secrets.token_hex(4).upper()}",
        recipient_id=event.coordinator_id,
        event_id=event_id,
        certificate_type="coordination",
        issued_by=current_user.id,
    )
    db.session.add(certificate)
    db.session.flush()
    certificate.pdf_path = make_certificate_pdf(certificate)
    notify(
        event.coordinator_id,
        "Certificate available",
        f"Your event coordination certificate for {event.title} is ready.",
        url_for("certificates.history"),
    )
    db.session.commit()
    flash("Coordinator certificate issued.", "success")
    return redirect(url_for("certificates.history"))


@certificates.route("/history")
@roles_required("student", "coordinator", "admin")
def history():
    if current_user.role_name == "admin":
        sync_ended_event_certificates()
        items = Certificate.query.order_by(Certificate.created_at.desc()).all()
    elif current_user.role_name == "coordinator":
        sync_ended_event_certificates(coordinator_id=current_user.id)
        items = (
            Certificate.query.join(Event)
            .filter(
                db.or_(
                    Certificate.recipient_id == current_user.id,
                    Event.coordinator_id == current_user.id,
                )
            )
            .order_by(Certificate.created_at.desc())
            .all()
        )
    else:
        sync_ended_event_certificates(student_id=current_user.id)
        items = Certificate.query.filter_by(recipient_id=current_user.id).order_by(
            Certificate.created_at.desc()
        ).all()
    return render_template("certificates/history.html", items=items)


@certificates.route("/download/<int:certificate_id>")
@roles_required("student", "coordinator", "admin")
def download(certificate_id):
    certificate = db.session.get(Certificate, certificate_id)
    if not certificate:
        abort(404)
    if (
        current_user.role_name != "admin"
        and certificate.recipient_id != current_user.id
        and certificate.event.coordinator_id != current_user.id
    ):
        abort(403)
    path = Path(certificate.pdf_path)
    if not certificate.is_valid or not path.exists():
        abort(404)
    return send_file(path, as_attachment=True, download_name=certificate_filename(certificate.certificate_id))


@certificates.route("/verify/<certificate_id>")
def verify(certificate_id):
    certificate = Certificate.query.filter_by(certificate_id=certificate_id).first()
    if not certificate or not certificate.is_valid:
        return render_template(
            "certificates/verify.html",
            certificate=None,
            valid=False,
        )
    return render_template(
        "certificates/verify.html",
        certificate=certificate,
        valid=True,
    )
