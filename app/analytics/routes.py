from collections import Counter

from flask import render_template

from app.analytics import analytics
from app.decorators import roles_required
from app.models import Event, EventCategory


@analytics.route("/admin")
@roles_required("admin")
def admin_analytics():
    categories = EventCategory.all()
    events = Event.all()
    category_counts = Counter(e.category_id for e in events if e.category_id is not None)
    status_counts = Counter(e.status for e in events if e.status)
    return render_template(
        "analytics/admin.html",
        category_labels=[cat.name for cat in categories],
        category_counts=[category_counts.get(cat.id, 0) for cat in categories],
        status_labels=[status.title() for status in status_counts.keys()],
        status_counts=list(status_counts.values()),
    )
