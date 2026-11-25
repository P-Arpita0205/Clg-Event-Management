import re
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from PIL import Image

from app import db
from app.decorators import roles_required
from app.events import events
from app.events.forms import EventForm, VolunteerApplicationForm
from app.models import (
    Club,
    Department,
    Event,
    EventCategory,
    EventRegistration,
    Role,
    User,
    VolunteerApplication,
    VolunteerAssignment,
)
from app.notifications.routes import notify


def slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:170] or "event"


def unique_slug(title, event_id=None):
    base = slugify(title)
    slug = base
    counter = 2
    while Event.query.filter(Event.slug == slug, Event.id != event_id).first():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def parse_deadline(value):
    return datetime.strptime(value.strip(), "%Y-%m-%dT%H:%M")


def save_poster(file):
    if not file or not file.filename:
        return None
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    extension = Path(secure_filename(file.filename)).suffix.lower()
    filename = f"{uuid.uuid4().hex}{extension}"
    extension = Path(filename).suffix.lower()
    destination = folder / filename
    file.save(destination)
    if extension in (".jpg", ".jpeg", ".png", ".webp"):
        try:
            with Image.open(destination) as image:
                image.thumbnail((1600, 1600))
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                image.save(destination, quality=82, optimize=True)
        except Exception:
            destination.unlink(missing_ok=True)
            return None
    return filename


@events.route("/uploads/<path:filename>")
def poster(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


def populate_event_form(form):
    form.category_id.choices = [
        (category.id, category.name) for category in EventCategory.query.order_by(EventCategory.name)
    ]
    form.department_id.choices = [(0, "All Departments")] + [
        (department.id, department.name) for department in Department.query.order_by(Department.name)
    ]
    form.club_id.choices = [(0, "None")] + [
        (club.id, club.name) for club in Club.query.filter_by(is_active=True).order_by(Club.name)
    ]


def _notify_department_students_for_event(event):
    """Notify active students in the event's department that an event is published."""
    student_role = Role.query.filter_by(name="student").first()
    if not student_role:
        return 0
    query = User.query.filter_by(role_id=student_role.id, is_active=True)
    if event.department_id:
        query = query.filter_by(department_id=event.department_id)
    students = query.all()
    dept_label = f" ({event.department.name})" if event.department else " (All Departments)"
    volunteer_info = (
        f" Volunteers needed: {event.volunteer_requirement}."
        if event.volunteer_requirement > 0
        else ""
    )
    compulsory_info = (
        " Registration is compulsory for eligible students."
        if event.registration_compulsory
        else ""
    )
    message = (
        f"{event.title}{dept_label} is scheduled on "
        f"{event.event_date.strftime('%d %b %Y')} at {event.venue}.{volunteer_info}{compulsory_info}"
    )
    title_prefix = "Compulsory event" if event.registration_compulsory else "New event"
    link = url_for("events.detail", event_id=event.id)
    for student in students:
        notify(student.id, f"{title_prefix}: {event.title}", message, link=link)
    return len(students)


@events.route("/")
def browse():
    category = request.args.get("category", type=str)
    department_id = request.args.get("department", type=int)
    q = (request.args.get("q") or "").strip()
    query = Event.query.filter(Event.status == "published")
    if category:
        query = query.join(EventCategory).filter(EventCategory.name == category)
    if department_id:
        query = query.filter(Event.department_id == department_id)
    if q:
        like_term = f"%{q}%"
        query = query.filter(
            (Event.title.ilike(like_term))
            | (Event.description.ilike(like_term))
            | (Event.venue.ilike(like_term))
        )
    event_list = query.order_by(Event.event_date.asc(), Event.start_time.asc()).all()
    categories = EventCategory.query.order_by(EventCategory.name).all()
    departments = Department.query.order_by(Department.name).all()
    template_name = (
        "events/browse_dashboard.html"
        if current_user.is_authenticated
        else "events/browse.html"
    )
    return render_template(
        template_name,
        event_list=event_list,
        categories=categories,
        departments=departments,
        category=category,
        department_id=department_id,
        q=q,
    )


@events.route("/<int:event_id>")
def detail(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    if event.status not in ("published", "completed") and (
        not current_user.is_authenticated
        or (event.coordinator_id != current_user.id and current_user.role_name not in ("admin",))
    ):
        abort(404)

    registration = None
    application = None
    if current_user.is_authenticated:
        registration = EventRegistration.query.filter_by(
            event_id=event.id, student_id=current_user.id
        ).first()
        application = VolunteerApplication.query.filter_by(
            event_id=event.id, student_id=current_user.id
        ).first()
        if application and application.status == "approved" and not application.qr_token:
            application.qr_token = secrets.token_urlsafe(32)
            db.session.commit()
    template_name = (
        "events/detail_dashboard.html"
        if current_user.is_authenticated
        else "events/detail.html"
    )
    return render_template(
        template_name,
        event=event,
        registration=registration,
        application=application,
        volunteer_form=VolunteerApplicationForm(),
    )


@events.route("/create", methods=["GET", "POST"])
@roles_required("coordinator", "admin")
def create():
    form = EventForm()
    populate_event_form(form)
    if form.validate_on_submit():
        try:
            deadline = parse_deadline(form.registration_deadline.data)
        except ValueError:
            form.registration_deadline.errors.append("Use YYYY-MM-DDTHH:MM format.")
            return render_template("events/form.html", form=form, event=None)
        if form.end_date.data and form.end_date.data < form.event_date.data:
            form.end_date.errors.append("End date cannot be before start date.")
            return render_template("events/form.html", form=form, event=None)
        same_day = not form.end_date.data or form.end_date.data == form.event_date.data
        if same_day and form.end_time.data and form.end_time.data <= form.start_time.data:
            form.end_time.errors.append("End time must be after start time.")
            return render_template("events/form.html", form=form, event=None)
        if deadline.date() > form.event_date.data:
            form.registration_deadline.errors.append("Deadline cannot be after the event date.")
            return render_template("events/form.html", form=form, event=None)

        is_admin = current_user.role_name == "admin"
        event = Event(
            title=form.title.data.strip(),
            slug=unique_slug(form.title.data),
            description=form.description.data.strip(),
            category_id=form.category_id.data,
            department_id=form.department_id.data if form.department_id.data else None,
            club_id=form.club_id.data if form.club_id.data else None,
            coordinator_id=current_user.id,
            venue=form.venue.data.strip(),
            organizer=form.organizer.data.strip(),
            event_date=form.event_date.data,
            end_date=form.end_date.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data or form.start_time.data,
            registration_deadline=deadline,
            capacity=100000,
            volunteer_requirement=form.volunteer_requirement.data,
            registration_compulsory=bool(form.registration_compulsory.data),
            status="published" if is_admin else "draft",
        )
        event.poster = save_poster(form.poster.data)
        db.session.add(event)
        db.session.flush()
        if is_admin:
            notified = _notify_department_students_for_event(event)
            db.session.commit()
            flash(f"Event created and published. Notified {notified} department student(s).", "success")
            return redirect(url_for("admin.events"))
        db.session.commit()
        flash("Event created as a draft and sent for admin approval.", "success")
        return redirect(url_for("coordinator.events"))
    if request.method == "POST":
        flash("Please fix the highlighted errors below.", "danger")
    return render_template("events/form.html", form=form, event=None)


@events.route("/<int:event_id>/edit", methods=["GET", "POST"])
@roles_required("coordinator", "admin")
def edit(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    if current_user.role_name != "admin" and event.coordinator_id != current_user.id:
        abort(403)
    if current_user.role_name != "admin" and event.status not in ("draft", "rejected"):
        flash("Published or cancelled events cannot be edited.", "warning")
        return redirect(url_for("coordinator.events"))

    form = EventForm(obj=event)
    populate_event_form(form)
    if request.method == "GET":
        form.registration_deadline.data = event.registration_deadline.strftime("%Y-%m-%dT%H:%M")
        form.department_id.data = event.department_id or 0
        form.club_id.data = event.club_id or 0
        if event.end_time == event.start_time:
            form.end_time.data = None

    if form.validate_on_submit():
        try:
            deadline = parse_deadline(form.registration_deadline.data)
        except ValueError:
            form.registration_deadline.errors.append("Use YYYY-MM-DDTHH:MM format.")
            return render_template("events/form.html", form=form, event=event)
        if form.end_date.data and form.end_date.data < form.event_date.data:
            form.end_date.errors.append("End date cannot be before start date.")
            return render_template("events/form.html", form=form, event=event)
        same_day = not form.end_date.data or form.end_date.data == form.event_date.data
        if same_day and form.end_time.data and form.end_time.data <= form.start_time.data:
            form.end_time.errors.append("End time must be after start time.")
            return render_template("events/form.html", form=form, event=event)

        event.title = form.title.data.strip()
        event.slug = unique_slug(form.title.data, event.id)
        event.description = form.description.data.strip()
        event.category_id = form.category_id.data
        event.department_id = form.department_id.data if form.department_id.data else None
        event.club_id = form.club_id.data if form.club_id.data else None
        event.venue = form.venue.data.strip()
        event.organizer = form.organizer.data.strip()
        event.event_date = form.event_date.data
        event.end_date = form.end_date.data
        event.start_time = form.start_time.data
        event.end_time = form.end_time.data or form.start_time.data
        event.registration_deadline = deadline
        event.volunteer_requirement = form.volunteer_requirement.data
        event.registration_compulsory = bool(form.registration_compulsory.data)
        if current_user.role_name != "admin":
            event.status = "draft"
            event.approval_note = None
        poster = save_poster(form.poster.data)
        if poster:
            event.poster = poster
        db.session.commit()
        if current_user.role_name == "admin":
            flash("Event updated.", "success")
            return redirect(url_for("admin.events"))
        flash("Event updated and returned to draft for approval.", "success")
        return redirect(url_for("coordinator.events"))
    return render_template("events/form.html", form=form, event=event)


@events.route("/<int:event_id>/delete", methods=["POST"])
@roles_required("admin")
def delete(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    title = event.title
    db.session.delete(event)
    db.session.commit()
    flash(f"Event '{title}' deleted.", "warning")
    return redirect(url_for("admin.events"))


@events.route("/<int:event_id>/cancel", methods=["POST"])
@roles_required("coordinator", "admin")
def cancel(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    if current_user.role_name != "admin" and event.coordinator_id != current_user.id:
        abort(403)
    event.status = "cancelled"
    db.session.commit()
    flash("Event cancelled.", "warning")
    return redirect(request.referrer or url_for("events.browse"))


@events.route("/<int:event_id>/complete", methods=["POST"])
@roles_required("coordinator", "admin")
def complete(event_id):
    from app.certificates.routes import issue_eligible_certificates_for_event

    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    if current_user.role_name != "admin" and event.coordinator_id != current_user.id:
        abort(403)
    if event.status not in ("published", "completed"):
        flash("Only published events can be marked as ended.", "warning")
        return redirect(
            request.referrer
            or (
                url_for("admin.events")
                if current_user.role_name == "admin"
                else url_for("coordinator.events")
            )
        )
    event.status = "completed"
    db.session.commit()
    issued = issue_eligible_certificates_for_event(event, issuer_id=current_user.id)
    flash(
        f"Event marked as ended. Issued {issued} certificate(s) to QR-verified attendees.",
        "success",
    )
    return redirect(
        request.referrer
        or (
            url_for("admin.events")
            if current_user.role_name == "admin"
            else url_for("coordinator.events")
        )
    )


@events.route("/<int:event_id>/approve", methods=["POST"])
@roles_required("admin")
def approve(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    event.status = "published"
    event.approval_note = request.form.get("note", "").strip() or None
    notified = _notify_department_students_for_event(event)
    db.session.commit()
    flash(f"Event approved and published. Notified {notified} department student(s).", "success")
    return redirect(url_for("admin.events"))


@events.route("/<int:event_id>/reject", methods=["POST"])
@roles_required("admin")
def reject(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    event.status = "rejected"
    event.approval_note = request.form.get("note", "").strip() or None
    db.session.commit()
    flash("Event rejected.", "warning")
    return redirect(url_for("admin.events"))


@events.route("/<int:event_id>/register", methods=["POST"])
@roles_required("student")
def register(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    if event.status != "published":
        abort(400)
    if datetime.now(timezone.utc).replace(tzinfo=None) > event.registration_deadline:
        flash("The registration deadline has passed.", "danger")
        return redirect(url_for("events.detail", event_id=event.id))
    if event.approved_registration_count >= event.capacity:
        flash("This event has reached capacity.", "danger")
        return redirect(url_for("events.detail", event_id=event.id))
    if EventRegistration.query.filter_by(event_id=event.id, student_id=current_user.id).first():
        flash("You are already registered for this event.", "warning")
        return redirect(url_for("events.detail", event_id=event.id))

    db.session.add(
        EventRegistration(
            event_id=event.id,
            student_id=current_user.id,
            status="confirmed",
        )
    )
    notify(
        current_user.id,
        "Registration confirmed",
        f"You are registered for {event.title}.",
        url_for("student.registrations"),
    )
    db.session.commit()
    flash("Registration confirmed.", "success")
    return redirect(url_for("events.detail", event_id=event.id))


@events.route("/<int:event_id>/registration/cancel", methods=["POST"])
@roles_required("student")
def cancel_registration(event_id):
    registration = EventRegistration.query.filter_by(
        event_id=event_id,
        student_id=current_user.id,
    ).first()
    if not registration:
        abort(404)
    if registration.event.registration_compulsory:
        flash("Registration for this event is compulsory and cannot be cancelled.", "warning")
        return redirect(url_for("events.detail", event_id=event_id))
    db.session.delete(registration)
    db.session.commit()
    flash("Your registration has been cancelled.", "info")
    return redirect(url_for("student.dashboard"))


@events.route("/<int:event_id>/volunteer", methods=["POST"])
@roles_required("student")
def apply_volunteer(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    if event.status != "published":
        abort(400)
    if VolunteerApplication.query.filter_by(event_id=event.id, student_id=current_user.id).first():
        flash("You have already applied to volunteer for this event.", "warning")
        return redirect(url_for("events.detail", event_id=event.id))
    if event.volunteer_limit_reached:
        flash("Number limit of volunteers reached.", "warning")
        return redirect(url_for("events.detail", event_id=event.id))

    form = VolunteerApplicationForm()
    if form.validate_on_submit():
        db.session.add(
            VolunteerApplication(
                event_id=event.id,
                student_id=current_user.id,
                availability="Flexible",
                experience=form.experience.data.strip() if form.experience.data else None,
                preferred_role=form.preferred_role.data,
                status="pending",
            )
        )
        db.session.commit()
        flash("Volunteer application submitted.", "success")
    else:
        flash("Please complete the required fields.", "danger")
    return redirect(url_for("events.detail", event_id=event.id))


@events.route("/<int:event_id>/participants")
@roles_required("coordinator", "admin")
def participants(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    if current_user.role_name != "admin" and event.coordinator_id != current_user.id:
        abort(403)
    registrations = EventRegistration.query.filter_by(event_id=event.id).order_by(
        EventRegistration.registered_at.desc()
    ).all()
    unregistered_students = []
    if event.registration_compulsory:
        registered_ids = {
            reg.student_id for reg in registrations if reg.status == "confirmed"
        }
        student_role = Role.query.filter_by(name="student").first()
        if student_role:
            student_query = User.query.filter_by(
                role_id=student_role.id,
                is_active=True,
            )
            if event.department_id:
                student_query = student_query.filter_by(department_id=event.department_id)
            if registered_ids:
                student_query = student_query.filter(~User.id.in_(registered_ids))
            unregistered_students = student_query.order_by(User.full_name.asc()).all()
    return render_template(
        "events/participants.html",
        event=event,
        registrations=registrations,
        unregistered_students=unregistered_students,
    )


@events.route("/applications/<int:application_id>/approve", methods=["POST"])
@roles_required("coordinator", "admin")
def approve_volunteer(application_id):
    application = db.session.get(VolunteerApplication, application_id)
    if not application:
        abort(404)
    if current_user.role_name != "admin" and application.event.coordinator_id != current_user.id:
        abort(403)
    if application.status != "approved" and application.event.volunteer_limit_reached:
        flash("Number limit of volunteers reached for this event.", "warning")
        return redirect(url_for("coordinator.applications"))
    application.status = "approved"
    application.reviewed_at = datetime.now(timezone.utc)
    application.reviewer_note = request.form.get("note", "").strip() or None
    notify(
        application.student_id,
        "Volunteer application approved",
        f"Your volunteer application for {application.event.title} was approved.",
        url_for("student.volunteer_applications"),
    )
    db.session.commit()
    flash("Volunteer application approved.", "success")
    return redirect(url_for("coordinator.applications"))


@events.route("/applications/<int:application_id>/reject", methods=["POST"])
@roles_required("coordinator", "admin")
def reject_volunteer(application_id):
    application = db.session.get(VolunteerApplication, application_id)
    if not application:
        abort(404)
    if current_user.role_name != "admin" and application.event.coordinator_id != current_user.id:
        abort(403)
    application.status = "rejected"
    application.reviewed_at = datetime.now(timezone.utc)
    application.reviewer_note = request.form.get("note", "").strip() or None
    notify(
        application.student_id,
        "Volunteer application rejected",
        f"Your volunteer application for {application.event.title} was not approved.",
        url_for("student.volunteer_applications"),
    )
    db.session.commit()
    flash("Volunteer application rejected.", "warning")
    return redirect(url_for("coordinator.applications"))


@events.route("/applications/<int:application_id>/assign", methods=["POST"])
@roles_required("coordinator", "admin")
def assign_volunteer(application_id):
    application = db.session.get(VolunteerApplication, application_id)
    if not application:
        abort(404)
    if current_user.role_name != "admin" and application.event.coordinator_id != current_user.id:
        abort(403)
    if application.status != "approved":
        flash("Approve the application before assigning it.", "warning")
        return redirect(url_for("coordinator.applications"))

    role = request.form.get("volunteer_role", "").strip()
    responsibilities = request.form.get("responsibilities", "").strip()
    if not role:
        flash("A volunteer role is required.", "danger")
        return redirect(url_for("coordinator.applications"))
    if application.assignment:
        application.assignment.volunteer_role = role
        application.assignment.responsibilities = responsibilities or None
    else:
        db.session.add(
            VolunteerAssignment(
                application=application,
                volunteer_role=role,
                responsibilities=responsibilities or None,
            )
        )
    notify(
        application.student_id,
        "Volunteer role assigned",
        f"You have been assigned to {role} for {application.event.title}.",
        url_for("student.volunteer_applications"),
    )
    db.session.commit()
    flash("Volunteer role assigned.", "success")
    return redirect(url_for("coordinator.applications"))
