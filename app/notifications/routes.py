from datetime import datetime, timezone

from flask import jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from app.decorators import roles_required
from app.firestore_db import batch_write, next_id
from app.models import Notification
from app.notifications import notifications


def notify(user_id, title, message, link=None):
    Notification(
        user_id=user_id,
        title=title,
        message=message,
        link=link,
    ).save()


def notify_many(items):
    """Persist multiple notifications in Firestore using batched writes."""
    if not items:
        return
    now = datetime.now(timezone.utc)
    ops = []
    for user_id, title, message, link in items:
        doc_id = next_id(Notification.collection_name)
        ops.append((
            "set",
            Notification.collection_name,
            doc_id,
            {
                "id": doc_id,
                "user_id": user_id,
                "title": title,
                "message": message,
                "link": link,
                "is_read": False,
                "created_at": now,
            },
        ))
    batch_write(ops)


@notifications.route("/")
@roles_required("student", "coordinator", "admin")
def list_notifications():
    items = sorted(
        Notification.where(user_id=current_user.id),
        key=lambda item: item.created_at,
        reverse=True,
    )
    return render_template("notifications/list.html", items=items)


@notifications.route("/read/<int:notification_id>", methods=["POST"])
@roles_required("student", "coordinator", "admin")
def mark_read(notification_id):
    item = Notification.get(notification_id)
    if not item or item.user_id != current_user.id:
        return jsonify({"error": "Not found"}), 404
    item.is_read = True
    item.save()
    return redirect(request.referrer or url_for("notifications.list_notifications"))


@notifications.route("/read-all", methods=["POST"])
@roles_required("student", "coordinator", "admin")
def mark_all_read():
    unread = Notification.where(user_id=current_user.id, is_read=False)
    if unread:
        batch_write([
            ("update", Notification.collection_name, item.id, {"is_read": True})
            for item in unread
        ])
    return redirect(request.referrer or url_for("notifications.list_notifications"))
