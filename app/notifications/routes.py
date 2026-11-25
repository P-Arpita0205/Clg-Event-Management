from flask import jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from app import db
from app.decorators import roles_required
from app.models import Notification
from app.notifications import notifications


def notify(user_id, title, message, link=None):
    db.session.add(
        Notification(
            user_id=user_id,
            title=title,
            message=message,
            link=link,
        )
    )


@notifications.route("/")
@roles_required("student", "coordinator", "admin")
def list_notifications():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).all()
    return render_template("notifications/list.html", items=items)


@notifications.route("/read/<int:notification_id>", methods=["POST"])
@roles_required("student", "coordinator", "admin")
def mark_read(notification_id):
    item = db.session.get(Notification, notification_id)
    if not item or item.user_id != current_user.id:
        return jsonify({"error": "Not found"}), 404
    item.is_read = True
    db.session.commit()
    return redirect(request.referrer or url_for("notifications.list_notifications"))


@notifications.route("/read-all", methods=["POST"])
@roles_required("student", "coordinator", "admin")
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update(
        {"is_read": True}
    )
    db.session.commit()
    return redirect(request.referrer or url_for("notifications.list_notifications"))
