from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from app import db
from app.decorators import roles_required
from app.feedback import feedback
from app.models import Attendance, Event, Feedback


@feedback.route("/event/<int:event_id>", methods=["GET", "POST"])
@roles_required("student")
def submit(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    existing = Feedback.query.filter_by(
        event_id=event_id,
        student_id=current_user.id,
    ).first()
    anonymous_key = f"anonymous_feedback_{event_id}"
    if session.get(anonymous_key):
        existing = True
    if existing:
        flash("You have already submitted feedback for this event.", "warning")
        return redirect(url_for("events.detail", event_id=event_id))

    if request.method == "POST":
        try:
            rating = int(request.form.get("rating", ""))
        except ValueError:
            flash("Select a rating from 1 to 5.", "danger")
            return redirect(url_for("feedback.submit", event_id=event_id))
        if rating < 1 or rating > 5:
            flash("Select a rating from 1 to 5.", "danger")
            return redirect(url_for("feedback.submit", event_id=event_id))
        suggestions = request.form.get("suggestions", "").strip()
        is_anonymous = request.form.get("is_anonymous") == "on"
        db.session.add(
            Feedback(
                event_id=event_id,
                student_id=None if is_anonymous else current_user.id,
                rating=rating,
                suggestions=suggestions or None,
                is_anonymous=is_anonymous,
            )
        )
        if is_anonymous:
            session[anonymous_key] = True
        db.session.commit()
        flash("Thank you. Your feedback has been submitted.", "success")
        return redirect(url_for("events.detail", event_id=event_id))
    return render_template("feedback/form.html", event=event)


@feedback.route("/event/<int:event_id>/review")
@roles_required("coordinator", "admin")
def review(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    if current_user.role_name != "admin" and event.coordinator_id != current_user.id:
        abort(403)
    items = Feedback.query.filter_by(event_id=event_id).order_by(
        Feedback.created_at.desc()
    ).all()
    ratings = [item.rating for item in items]
    average = round(sum(ratings) / len(ratings), 2) if ratings else None
    return render_template(
        "feedback/review.html",
        event=event,
        items=items,
        average=average,
        response_count=len(items),
    )
