from collections import Counter
from datetime import date

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from app import db
from app.assistance import assistance
from app.decorators import roles_required
from app.models import (
    Event,
    EventCategory,
    EventRegistration,
    Feedback,
    StudentInterest,
    VolunteerApplication,
)


THEME_KEYWORDS = {
    "Venue and facilities": ("venue", "room", "hall", "seating", "projector", "parking"),
    "Organization and scheduling": ("schedule", "late", "timing", "organized", "coordination"),
    "Food and refreshments": ("food", "lunch", "snack", "refreshment", "catering"),
    "Technical quality": ("audio", "sound", "microphone", "network", "internet", "technical"),
    "Session content": ("content", "speaker", "workshop", "session", "learning"),
    "Communication": ("message", "notice", "communication", "announcement", "email"),
}


def recommend_events(student_id, limit=6):
    registered_ids = [
        registration.event_id
        for registration in EventRegistration.query.filter_by(student_id=student_id).all()
    ]
    interest_ids = [
        interest.category_id
        for interest in StudentInterest.query.filter_by(student_id=student_id).all()
    ]
    attended_category_ids = [
        registration.event.category_id
        for registration in EventRegistration.query.filter_by(student_id=student_id).all()
        if registration.event
    ]
    query = Event.query.filter(
        Event.status == "published",
        Event.event_date >= date.today(),
    )
    if registered_ids:
        query = query.filter(~Event.id.in_(registered_ids))
    events = query.order_by(Event.event_date.asc()).all()

    scored = []
    for event in events:
        score = 0
        if event.category_id in interest_ids:
            score += 5
        if event.category_id in attended_category_ids:
            score += 3
        if event.department_id == getattr(current_user, "department_id", None):
            score += 2
        scored.append((score, event))
    scored.sort(key=lambda item: (-item[0], item[1].event_date))
    return [event for _, event in scored[:limit]]


@assistance.route("/recommendations")
@roles_required("student")
def recommendations():
    recommendations = recommend_events(current_user.id)
    interests = StudentInterest.query.filter_by(student_id=current_user.id).all()
    categories = EventCategory.query.order_by(EventCategory.name).all()
    return render_template(
        "assistance/recommendations.html",
        recommendations=recommendations,
        interests=interests,
        categories=categories,
    )


@assistance.route("/interests", methods=["POST"])
@roles_required("student")
def save_interests():
    category_ids = [
        int(value)
        for value in request.form.getlist("category_ids")
        if value.isdigit()
    ]
    StudentInterest.query.filter_by(student_id=current_user.id).delete()
    valid_ids = {
        category.id
        for category in EventCategory.query.filter(EventCategory.id.in_(category_ids)).all()
    } if category_ids else set()
    db.session.add_all([
        StudentInterest(student_id=current_user.id, category_id=category_id)
        for category_id in valid_ids
    ])
    db.session.commit()
    flash("Your event interests were updated.", "success")
    return redirect(url_for("assistance.recommendations"))


@assistance.route("/volunteer-role/<int:event_id>")
@roles_required("student")
def volunteer_role(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        return render_template("assistance/role.html", event=None, role="No event found", reasons=[], event_id=event_id)

    applications = (
        VolunteerApplication.query.filter_by(student_id=current_user.id)
        .filter(VolunteerApplication.status.in_(("approved", "rejected")))
        .all()
    )
    role_counts = Counter(
        application.preferred_role
        for application in applications
        if application.preferred_role
    )
    role = role_counts.most_common(1)[0][0] if role_counts else "Registration Desk"
    reasons = []
    if role_counts:
        reasons.append(f"Your previous activity suggests: {role}")
    else:
        reasons.append("Registration Desk is the best general starting role")

    return render_template(
        "assistance/role.html",
        event=event,
        role=role,
        reasons=reasons,
        event_id=event_id,
    )


@assistance.route("/feedback-analysis/<int:event_id>")
@roles_required("coordinator", "admin")
def feedback_analysis(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        return render_template("assistance/feedback.html", event=None, themes=[], average=None)
    if current_user.role_name != "admin" and event.coordinator_id != current_user.id:
        return render_template("assistance/feedback.html", event=None, themes=[], average=None), 403

    items = Feedback.query.filter_by(event_id=event_id).all()
    ratings = [item.rating for item in items]
    theme_counts = Counter()
    for item in items:
        text = (item.suggestions or "").lower()
        for theme, keywords in THEME_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                theme_counts[theme] += 1
    themes = theme_counts.most_common()
    average = round(sum(ratings) / len(ratings), 2) if ratings else None
    return render_template(
        "assistance/feedback.html",
        event=event,
        themes=themes,
        average=average,
        response_count=len(items),
    )


@assistance.route("/event-description", methods=["POST"])
@roles_required("coordinator")
def event_description():
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    venue = request.form.get("venue", "").strip()
    if not title:
        flash("Enter an event title before generating a description draft.", "warning")
        return redirect(request.referrer or url_for("events.create"))
    draft = (
        f"{title} is a {category.lower() if category else 'campus'} event designed to engage "
        f"students through active participation and learning"
        f"{' at ' + venue if venue else ''}. "
        "Join the campus community for scheduled activities, student collaboration, "
        "and a well-organized event experience."
    )
    flash("A description draft was prepared. Review and edit it before submission.", "info")
    return render_template("assistance/description.html", draft=draft)
