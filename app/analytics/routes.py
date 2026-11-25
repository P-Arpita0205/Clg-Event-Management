from flask import render_template

from app import db
from app.analytics import analytics
from app.decorators import roles_required
from app.models import Attendance, Event, EventCategory, EventRegistration, VolunteerApplication


@analytics.route("/admin")
@roles_required("admin")
def admin_analytics():
    category_rows = (
        db.session.query(EventCategory.name, db.func.count(Event.id))
        .outerjoin(Event, Event.category_id == EventCategory.id)
        .group_by(EventCategory.id, EventCategory.name)
        .all()
    )
    status_rows = (
        db.session.query(Event.status, db.func.count(Event.id))
        .group_by(Event.status)
        .all()
    )
    return render_template(
        "analytics/admin.html",
        category_labels=[row[0] for row in category_rows],
        category_counts=[row[1] for row in category_rows],
        status_labels=[row[0].title() for row in status_rows],
        status_counts=[row[1] for row in status_rows],
    )
