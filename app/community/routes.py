import calendar
from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.community import community
from app.decorators import roles_required
from app.models import Club, Department, Event, ResourceBooking


@community.route("/departments")
@roles_required("admin")
def departments():
    items = sorted(Department.all(), key=lambda d: d.name)
    return render_template("community/departments.html", items=items)


@community.route("/departments/create", methods=["POST"])
@roles_required("admin")
def create_department():
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()
    if not name or not code:
        flash("Department name and code are required.", "danger")
        return redirect(url_for("community.departments"))
    if Department.find_one(name=name) or Department.find_one(code=code):
        flash("A department with that name or code already exists.", "danger")
        return redirect(url_for("community.departments"))
    Department(name=name, code=code).save()
    flash("Department created.", "success")
    return redirect(url_for("community.departments"))


@community.route("/departments/<int:department_id>/delete", methods=["POST"])
@roles_required("admin")
def delete_department(department_id):
    department = Department.get(department_id)
    if not department:
        abort(404)
    if department.users:
        flash("Departments assigned to users cannot be deleted.", "danger")
        return redirect(url_for("community.departments"))
    department.delete()
    flash("Department deleted.", "success")
    return redirect(url_for("community.departments"))


@community.route("/clubs")
@roles_required("admin")
def clubs():
    items = sorted(Club.all(), key=lambda c: c.name)
    return render_template("community/clubs.html", items=items)


@community.route("/clubs/create", methods=["POST"])
@roles_required("admin")
def create_club():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    if not name:
        flash("Club name is required.", "danger")
        return redirect(url_for("community.clubs"))
    if Club.find_one(name=name):
        flash("A club with that name already exists.", "danger")
        return redirect(url_for("community.clubs"))
    Club(name=name, description=description or None, is_active=True).save()
    flash("Club created.", "success")
    return redirect(url_for("community.clubs"))


@community.route("/clubs/<int:club_id>/toggle", methods=["POST"])
@roles_required("admin")
def toggle_club(club_id):
    club = Club.get(club_id)
    if not club:
        abort(404)
    club.is_active = not club.is_active
    club.save()
    flash("Club status updated.", "success")
    return redirect(url_for("community.clubs"))


@community.route("/calendar")
def calendar_view():
    year = request.args.get("year", type=int) or date.today().year
    month = request.args.get("month", type=int) or date.today().month
    if month < 1 or month > 12:
        month = date.today().month
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    event_list = sorted(
        [
            event
            for event in Event.where(status="published")
            if event.event_date and start <= event.event_date < end
        ],
        key=lambda e: (e.event_date, e.start_time),
    )
    events_by_date = {}
    for event in event_list:
        events_by_date.setdefault(event.event_date, []).append(event)

    bookings_by_date = {}
    if current_user.is_authenticated and current_user.role_name in ("admin", "coordinator"):
        booking_list = sorted(
            [
                booking
                for booking in ResourceBooking.where(status="confirmed")
                if booking.booking_date and start <= booking.booking_date < end
            ],
            key=lambda b: (b.booking_date, b.start_time),
        )
        for booking in booking_list:
            bookings_by_date.setdefault(booking.booking_date, []).append(booking)

    month_days = calendar.monthcalendar(year, month)
    month_cells = [
        [(day_number, date(year, month, day_number) if day_number else None) for day_number in week]
        for week in month_days
    ]
    month_name = calendar.month_name[month]

    template_name = (
        "community/calendar_dashboard.html"
        if current_user.is_authenticated
        else "community/calendar.html"
    )
    return render_template(
        template_name,
        year=year,
        month=month,
        month_name=month_name,
        month_days=month_days,
        month_cells=month_cells,
        events_by_date=events_by_date,
        bookings_by_date=bookings_by_date,
    )
