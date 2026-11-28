from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import uuid

from flask import abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user
from PIL import Image
from werkzeug.utils import secure_filename

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
from app.notifications.routes import notify_many


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
    event = Event.get(event_id)
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
        EventGallery(
            event_id=event_id,
            image_path=image_path,
            caption=request.form.get("caption", "").strip() or None,
            uploaded_by=current_user.id,
        ).save()
        flash("Gallery image uploaded.", "success")
    items = sorted(
        EventGallery.where(event_id=event_id),
        key=lambda item: item.created_at,
        reverse=True,
    )
    return render_template("advanced/gallery.html", event=event, items=items)


@advanced.route("/uploads/<path:filename>")
def gallery_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@advanced.route("/leaderboard")
def leaderboard():
    totals = defaultdict(Decimal)
    for record in VolunteerHours.all():
        totals[record.student_id] += Decimal(str(record.hours))

    rows = []
    for student_id, total_hours in totals.items():
        if total_hours > 0:
            user = User.get(student_id)
            if user:
                rows.append((user.id, user.full_name, user.student_id, total_hours))
    rows.sort(key=lambda r: (-r[3], r[1]))

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
        event = Event.get(event_id) if event_id else None
        student = User.get(student_id) if student_id else None
        if not event or not student:
            flash("Select a valid event and student.", "danger")
            return redirect(url_for("advanced.record_hours"))
        if current_user.role_name != "admin" and event.coordinator_id != current_user.id:
            abort(403)
        approved = VolunteerApplication.find_one(
            event_id=event.id,
            student_id=student.id,
            status="approved",
        )
        if not approved:
            flash("Volunteer hours can only be recorded for approved volunteers.", "danger")
            return redirect(url_for("advanced.record_hours"))
        VolunteerHours(
            student_id=student.id,
            event_id=event.id,
            hours=hours,
            note=request.form.get("note", "").strip() or None,
            recorded_by=current_user.id,
        ).save()
        flash("Volunteer hours recorded.", "success")

    event_list = sorted(Event.all(), key=lambda e: e.event_date, reverse=True)
    approved_student_ids = {
        app_rec.student_id for app_rec in VolunteerApplication.where(status="approved")
    }
    approved_students = sorted(
        [user for sid in approved_student_ids if (user := User.get(sid)) is not None],
        key=lambda u: u.full_name,
    )
    return render_template(
        "advanced/hours.html",
        event_list=event_list,
        approved_students=approved_students,
    )


@advanced.route("/student/hours")
@roles_required("student")
def student_hours():
    items = sorted(
        VolunteerHours.where(student_id=current_user.id),
        key=lambda item: item.recorded_at,
        reverse=True,
    )
    total = sum((Decimal(str(item.hours)) for item in items), Decimal("0"))
    return render_template("advanced/student_hours.html", items=items, total=total)


@advanced.route("/budget/event/<int:event_id>", methods=["GET", "POST"])
@roles_required("coordinator", "admin")
def event_budget(event_id):
    event = Event.get(event_id)
    if not event:
        abort(404)
    if current_user.role_name != "admin" and event.coordinator_id != current_user.id:
        abort(403)
    budget = EventBudget.find_one(event_id=event_id)
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
            budget.save()
            flash("Budget updated.", "success")
        else:
            budget = EventBudget(event_id=event_id, allocated_amount=amount).save()
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
            EventExpense(
                budget_id=budget.id,
                category=request.form.get("category", "").strip() or "Other",
                description=request.form.get("description", "").strip() or None,
                amount=amount,
                expense_date=expense_date,
            ).save()
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
        elif Resource.find_one(name=name):
            flash("A resource with that name already exists.", "danger")
        else:
            Resource(
                name=name,
                resource_type=resource_type,
                location=location,
                capacity=capacity or None,
            ).save()
            flash("Resource created.", "success")
    items = sorted(Resource.all(), key=lambda r: r.name)
    return render_template("advanced/resources.html", items=items)


@advanced.route("/resources/<int:resource_id>/toggle", methods=["POST"])
@roles_required("admin")
def toggle_resource(resource_id):
    resource = Resource.get(resource_id)
    if not resource:
        abort(404)
    resource.is_active = not resource.is_active
    resource.save()
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

        conflict = any(
            b.booking_date == booking_date
            and b.start_time < end_time
            and b.end_time > start_time
            for b in ResourceBooking.where(resource_id=resource_id, status="confirmed")
        )
        if conflict:
            flash("This resource is already booked during that time.", "danger")
            return redirect(url_for("advanced.book_resource"))

        resource = Resource.get(resource_id)
        if not resource or not resource.is_active:
            flash("Choose an active resource.", "danger")
            return redirect(url_for("advanced.book_resource"))

        event_id = request.form.get("event_id", type=int) or None
        department_id = request.form.get("department_id", type=int) or None
        purpose = request.form.get("purpose", "").strip()
        ResourceBooking(
            resource_id=resource_id,
            event_id=event_id,
            requester_id=current_user.id,
            purpose=purpose,
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_time,
        ).save()

        notified_count = 0
        department = Department.get(department_id) if department_id else None
        if department:
            student_role = Role.find_one(name="student")
            if student_role:
                students = [
                    u
                    for u in User.where(role_id=student_role.id, department_id=department.id)
                    if u.is_active
                ]
                date_str = booking_date.strftime("%d %b %Y")
                time_str = f"{start_time.strftime('%I:%M %p')}–{end_time.strftime('%I:%M %p')}"
                linked_event = Event.get(event_id) if event_id else None
                event_label = linked_event.title if linked_event else (purpose or resource.name)
                link = (
                    url_for("events.detail", event_id=linked_event.id)
                    if linked_event
                    else url_for("community.calendar_view")
                )
                notify_many([
                    (
                        student.id,
                        f"{department.name} event scheduled",
                        f"{event_label} is scheduled at {resource.name} on {date_str} ({time_str}).",
                        link,
                    )
                    for student in students
                ])
                notified_count = len(students)
        if department:
            flash(
                f"Resource booked. Notified {notified_count} student(s) in {department.name}.",
                "success",
            )
        else:
            flash("Resource booked.", "success")

    if Resource.count() == 0:
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
            Resource(
                name=res_name,
                resource_type=res_type,
                location=location,
                capacity=capacity,
                is_active=True,
            ).save()

    resources_list = sorted(Resource.where(is_active=True), key=lambda r: r.name)
    bookings = sorted(
        ResourceBooking.where(status="confirmed"),
        key=lambda b: (b.booking_date, b.start_time),
    )
    event_list = (
        Event.where(coordinator_id=current_user.id)
        if current_user.role_name == "coordinator"
        else Event.all()
    )
    departments = sorted(Department.all(), key=lambda d: d.name)
    return render_template(
        "advanced/bookings.html",
        resources=resources_list,
        bookings=bookings,
        event_list=event_list,
        departments=departments,
    )
