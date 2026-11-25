from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from pathlib import Path
import uuid

from flask import abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user
from werkzeug.utils import secure_filename
from PIL import Image

from app import db
from app.advanced import advanced
from app.decorators import roles_required
from app.models import (
    Department,
    Event,
    EventBudget,
    EventExpense,
    EventGallery,
    Resource,
    ResourceBooking,
    Role,
    User,
    VolunteerApplication,
    VolunteerHours,
)
from app.notifications.routes import notify


def save_gallery_image(file):
    if not file or not file.filename:
        return None
    folder = Path(current_app.config["UPLOAD_FOLDER"]) / "gallery"
    folder.mkdir(parents=True, exist_ok=True)
    extension = Path(secure_filename(file.filename)).suffix.lower()
    if extension not in (".jpg", ".jpeg", ".png", ".webp"):
        return None
    filename = f"{uuid.uuid4().hex}{extension}"
    destination = folder / filename
    file.save(destination)
    try:
        with Image.open(destination) as image:
            image.thumbnail((1800, 1800))
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            image.save(destination, quality=82, optimize=True)
    except Exception:
        destination.unlink(missing_ok=True)
        return None
    return f"gallery/{filename}"


@advanced.route("/gallery/event/<int:event_id>", methods=["GET", "POST"])
def event_gallery(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    if request.method == "POST":
        if not current_user.is_authenticated or current_user.role_name not in ("coordinator", "admin"):
            abort(403)
        if current_user.role_name != "admin" and event.coordinator_id != current_user.id:
            abort(403)
        image_path = save_gallery_image(request.files.get("image"))
        if not image_path:
            flash("Upload a JPG, PNG, or WebP image.", "danger")
            return redirect(url_for("advanced.event_gallery", event_id=event_id))
        db.session.add(
            EventGallery(
                event_id=event_id,
                image_path=image_path,
                caption=request.form.get("caption", "").strip() or None,
                uploaded_by=current_user.id,
            )
        )
        db.session.commit()
        flash("Gallery image uploaded.", "success")
    items = EventGallery.query.filter_by(event_id=event_id).order_by(
        EventGallery.created_at.desc()
    ).all()
    return render_template("advanced/gallery.html", event=event, items=items)


@advanced.route("/uploads/<path:filename>")
def gallery_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@advanced.route("/leaderboard")
def leaderboard():
    rows = (
        db.session.query(
            User.id,
            User.full_name,
            User.student_id,
            db.func.coalesce(db.func.sum(VolunteerHours.hours), 0),
        )
        .outerjoin(VolunteerHours, VolunteerHours.student_id == User.id)
        .group_by(User.id, User.full_name, User.student_id)
        .having(db.func.coalesce(db.func.sum(VolunteerHours.hours), 0) > 0)
        .order_by(db.func.sum(VolunteerHours.hours).desc(), User.full_name.asc())
        .all()
    )
    if current_user.is_authenticated:
        return render_template("advanced/leaderboard_dashboard.html", rows=rows)
    return render_template("advanced/leaderboard.html", rows=rows)


@advanced.route("/volunteer-hours", methods=["GET", "POST"])
@roles_required("coordinator", "admin")
def record_hours():
    if request.method == "POST":
        event_id = request.form.get("event_id", type=int)
        student_id = request.form.get("student_id", type=int)
        try:
            hours = Decimal(request.form.get("hours", ""))
        except (InvalidOperation, ValueError):
            flash("Enter a valid hour value.", "danger")
            return redirect(url_for("advanced.record_hours"))
        if hours < 0:
            flash("Hours cannot be negative.", "danger")
            return redirect(url_for("advanced.record_hours"))
        event = db.session.get(Event, event_id) if event_id else None
        student = db.session.get(User, student_id) if student_id else None
        if not event or not student:
            flash("Select a valid event and student.", "danger")
            return redirect(url_for("advanced.record_hours"))
        if current_user.role_name != "admin" and event.coordinator_id != current_user.id:
            abort(403)
        approved = VolunteerApplication.query.filter_by(
            event_id=event.id,
            student_id=student.id,
            status="approved",
        ).first()
        if not approved:
            flash("Volunteer hours can only be recorded for approved volunteers.", "danger")
            return redirect(url_for("advanced.record_hours"))
        db.session.add(
            VolunteerHours(
                student_id=student.id,
                event_id=event.id,
                hours=hours,
                note=request.form.get("note", "").strip() or None,
                recorded_by=current_user.id,
            )
        )
        db.session.commit()
        flash("Volunteer hours recorded.", "success")
    event_list = Event.query.order_by(Event.event_date.desc()).all()
    approved_students = (
        db.session.query(User)
        .join(VolunteerApplication, VolunteerApplication.student_id == User.id)
        .filter(VolunteerApplication.status == "approved")
        .distinct()
        .order_by(User.full_name)
        .all()
    )
    return render_template(
        "advanced/hours.html",
        event_list=event_list,
        approved_students=approved_students,
    )


@advanced.route("/student/hours")
@roles_required("student")
def student_hours():
    items = VolunteerHours.query.filter_by(student_id=current_user.id).order_by(
        VolunteerHours.recorded_at.desc()
    ).all()
    total = sum((Decimal(str(item.hours)) for item in items), Decimal("0"))
    return render_template("advanced/student_hours.html", items=items, total=total)


@advanced.route("/budget/event/<int:event_id>", methods=["GET", "POST"])
@roles_required("coordinator", "admin")
def event_budget(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    if current_user.role_name != "admin" and event.coordinator_id != current_user.id:
        abort(403)
    budget = EventBudget.query.filter_by(event_id=event_id).first()
    if request.method == "POST" and request.form.get("form_type") == "budget":
        try:
            amount = Decimal(request.form.get("allocated_amount", ""))
        except (InvalidOperation, ValueError):
            flash("Enter a valid allocated amount.", "danger")
            return redirect(url_for("advanced.event_budget", event_id=event_id))
        if amount < 0:
            flash("Budget cannot be negative.", "danger")
        elif budget:
            budget.allocated_amount = amount
            db.session.commit()
            flash("Budget updated.", "success")
        else:
            budget = EventBudget(event_id=event_id, allocated_amount=amount)
            db.session.add(budget)
            db.session.commit()
            flash("Budget created.", "success")
    if request.method == "POST" and request.form.get("form_type") == "expense":
        if not budget:
            flash("Create a budget before adding expenses.", "danger")
            return redirect(url_for("advanced.event_budget", event_id=event_id))
        try:
            amount = Decimal(request.form.get("amount", ""))
            expense_date = datetime.strptime(request.form.get("expense_date", ""), "%Y-%m-%d").date()
        except (InvalidOperation, ValueError):
            flash("Enter a valid amount and expense date.", "danger")
            return redirect(url_for("advanced.event_budget", event_id=event_id))
        if amount < 0:
            flash("Expense cannot be negative.", "danger")
        else:
            db.session.add(
                EventExpense(
                    budget_id=budget.id,
                    category=request.form.get("category", "").strip() or "Other",
                    description=request.form.get("description", "").strip() or None,
                    amount=amount,
                    expense_date=expense_date,
                )
            )
            db.session.commit()
            flash("Expense added.", "success")
    expenses = budget.expenses if budget else []
    spent = sum((Decimal(str(expense.amount)) for expense in expenses), Decimal("0"))
    remaining = (Decimal(str(budget.allocated_amount)) - spent) if budget else Decimal("0")
    return render_template(
        "advanced/budget.html",
        event=event,
        budget=budget,
        expenses=expenses,
        spent=spent,
        remaining=remaining,
    )


@advanced.route("/resources", methods=["GET", "POST"])
@roles_required("admin")
def resources():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        resource_type = request.form.get("resource_type", "").strip()
        location = request.form.get("location", "").strip() or None
        try:
            capacity = int(request.form.get("capacity", "") or 0)
        except ValueError:
            capacity = None
        if not name or not resource_type:
            flash("Resource name and type are required.", "danger")
        elif Resource.query.filter_by(name=name).first():
            flash("A resource with that name already exists.", "danger")
        else:
            db.session.add(
                Resource(
                    name=name,
                    resource_type=resource_type,
                    location=location,
                    capacity=capacity or None,
                )
            )
            db.session.commit()
            flash("Resource created.", "success")
    items = Resource.query.order_by(Resource.name).all()
    return render_template("advanced/resources.html", items=items)


@advanced.route("/resources/<int:resource_id>/toggle", methods=["POST"])
@roles_required("admin")
def toggle_resource(resource_id):
    resource = db.session.get(Resource, resource_id)
    if not resource:
        abort(404)
    resource.is_active = not resource.is_active
    db.session.commit()
    status = "activated" if resource.is_active else "deactivated"
    flash(f"Resource '{resource.name}' {status}.", "success")
    return redirect(url_for("advanced.resources"))


@advanced.route("/resources/book", methods=["GET", "POST"])
@roles_required("coordinator", "admin")
def book_resource():
    if request.method == "POST":
        try:
            resource_id = int(request.form.get("resource_id", ""))
            booking_date = datetime.strptime(request.form.get("booking_date", ""), "%Y-%m-%d").date()
            start_time = datetime.strptime(request.form.get("start_time", ""), "%H:%M").time()
            end_time = datetime.strptime(request.form.get("end_time", ""), "%H:%M").time()
        except (TypeError, ValueError):
            flash("Complete the resource and valid date/time fields.", "danger")
            return redirect(url_for("advanced.book_resource"))
        if end_time <= start_time:
            flash("End time must be after start time.", "danger")
            return redirect(url_for("advanced.book_resource"))
        conflict = ResourceBooking.query.filter(
            ResourceBooking.resource_id == resource_id,
            ResourceBooking.status == "confirmed",
            ResourceBooking.booking_date == booking_date,
            ResourceBooking.start_time < end_time,
            ResourceBooking.end_time > start_time,
        ).first()
        if conflict:
            flash("This resource is already booked during that time.", "danger")
            return redirect(url_for("advanced.book_resource"))
        resource = db.session.get(Resource, resource_id)
        if not resource or not resource.is_active:
            flash("Choose an active resource.", "danger")
            return redirect(url_for("advanced.book_resource"))
        event_id = request.form.get("event_id", type=int) or None
        department_id = request.form.get("department_id", type=int) or None
        purpose = request.form.get("purpose", "").strip()
        db.session.add(
            ResourceBooking(
                resource_id=resource_id,
                event_id=event_id,
                requester_id=current_user.id,
                purpose=purpose,
                booking_date=booking_date,
                start_time=start_time,
                end_time=end_time,
            )
        )
        notified_count = 0
        department = db.session.get(Department, department_id) if department_id else None
        if department:
            student_role = Role.query.filter_by(name="student").first()
            if student_role:
                students = User.query.filter_by(
                    role_id=student_role.id,
                    department_id=department.id,
                    is_active=True,
                ).all()
                date_str = booking_date.strftime("%d %b %Y")
                time_str = f"{start_time.strftime('%I:%M %p')}–{end_time.strftime('%I:%M %p')}"
                linked_event = db.session.get(Event, event_id) if event_id else None
                event_label = linked_event.title if linked_event else (purpose or resource.name)
                link = (
                    url_for("events.detail", event_id=linked_event.id)
                    if linked_event
                    else url_for("community.calendar_view")
                )
                for student in students:
                    notify(
                        student.id,
                        f"{department.name} event scheduled",
                        f"{event_label} is scheduled at {resource.name} on {date_str} ({time_str}).",
                        link=link,
                    )
                notified_count = len(students)
        db.session.commit()
        if department:
            flash(
                f"Resource booked. Notified {notified_count} student(s) in {department.name}.",
                "success",
            )
        else:
            flash("Resource booked.", "success")
    if Resource.query.count() == 0:
        default_resources = [
            ("Main Auditorium", "Auditorium", "Block A, Ground Floor", 500),
            ("Seminar Hall 1", "Seminar Hall", "Block B, 1st Floor", 120),
            ("Seminar Hall 2", "Seminar Hall", "Block B, 2nd Floor", 120),
            ("Computer Lab 1", "Laboratory", "Block C, Ground Floor", 60),
            ("Computer Lab 2", "Laboratory", "Block C, 1st Floor", 60),
            ("Conference Room", "Classroom", "Admin Block, 2nd Floor", 30),
            ("Sports Ground", "Sports Facility", "Campus Ground", 1000),
            ("Library Hall", "Seminar Hall", "Library Block, 1st Floor", 80),
        ]
        for res_name, res_type, location, capacity in default_resources:
            db.session.add(
                Resource(
                    name=res_name,
                    resource_type=res_type,
                    location=location,
                    capacity=capacity,
                    is_active=True,
                )
            )
        db.session.commit()

    resources = Resource.query.filter_by(is_active=True).order_by(Resource.name).all()
    bookings = ResourceBooking.query.filter_by(status="confirmed").order_by(
        ResourceBooking.booking_date,
        ResourceBooking.start_time,
    ).all()
    event_list = Event.query.filter_by(coordinator_id=current_user.id).all() if current_user.role_name == "coordinator" else Event.query.all()
    departments = Department.query.order_by(Department.name).all()
    return render_template(
        "advanced/bookings.html",
        resources=resources,
        bookings=bookings,
        event_list=event_list,
        departments=departments,
    )
